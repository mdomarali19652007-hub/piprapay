import os
import subprocess
import threading
import requests
import time
import re
from http.server import BaseHTTPRequestHandler, HTTPServer

# ==========================================
# 🔧 CONFIGURATION (YOUR TIDB DETAILS)
# ==========================================
TIDB_HOST = "gateway01.eu-central-1.prod.aws.tidbcloud.com"
TIDB_PORT = 4000
TIDB_USER = "467VfcbbnoxchaS.root"
TIDB_PASSWORD = "U1O54Xyee6M4gR8u"
DB_NAME = "test"
# ==========================================

PHP_PORT = 8000
LOCAL_DB_PORT = 3306
REPO_URL = "https://github.com/ShovonSheikh/PipraPay.git"
PROJECT_FOLDER = "project"

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status": "ok"}')
            return
        self.proxy()

    def do_POST(self):
        self.proxy()

    def proxy(self):
        url = f"http://127.0.0.1:{PHP_PORT}{self.path}"
        try:
            if self.command == "POST":
                content_length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_length) if content_length else None
                response = requests.post(url, data=body, headers=self.headers)
            else:
                response = requests.get(url, headers=self.headers)

            self.send_response(response.status_code)
            for key, value in response.headers.items():
                if key.lower() != "content-encoding":
                    self.send_header(key, value)
            self.end_headers()
            self.wfile.write(response.content)

        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(str(e).encode())

def set_permissions():
    print("Setting file permissions...", flush=True)
    directories = [
        f"{PROJECT_FOLDER}/invoice",
        f"{PROJECT_FOLDER}/payment",
        f"{PROJECT_FOLDER}/admin",
        f"{PROJECT_FOLDER}/pp-include"
    ]
    for directory in directories:
        if os.path.exists(directory):
            os.system(f"chmod -R 777 {directory}")

# ==============================================================================
# 🔌 SOCAT SSL PROXY (Properly handles MySQL protocol + SSL)
# ==============================================================================
def start_socat_proxy():
    """
    Socat properly handles MySQL protocol handshake + SSL upgrade.
    This is the reliable solution for TiDB connections.
    """
    print(f"✓ Starting socat SSL proxy on 127.0.0.1:{LOCAL_DB_PORT}", flush=True)
    
    # Enhanced socat command with better SSL options and debugging
    cmd = [
        "socat",
        "-d", "-d",  # Verbose logging
        f"TCP-LISTEN:{LOCAL_DB_PORT},bind=127.0.0.1,reuseaddr,fork",
        f"OPENSSL:{TIDB_HOST}:{TIDB_PORT},verify=0,openssl-commonname={TIDB_HOST},openssl-no-sni=0"
    ]
    
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        bufsize=1
    )
    
    print(f"✓ Socat proxy started (PID: {process.pid})", flush=True)
    
    # Log socat output in background for debugging
    def log_socat_output():
        for line in process.stdout:
            print(f"[SOCAT] {line.strip()}", flush=True)
    
    threading.Thread(target=log_socat_output, daemon=True).start()
    
    # Monitor socat in background
    def monitor_socat():
        while True:
            if process.poll() is not None:
                print("⚠️ Socat proxy died, restarting...", flush=True)
                start_socat_proxy()
                break
            time.sleep(5)
    
    threading.Thread(target=monitor_socat, daemon=True).start()
    
    return process

# ==============================================================================

def start_php():
    print(f"Starting PHP server on port {PHP_PORT}...", flush=True)
    os.chdir(PROJECT_FOLDER)
    process = subprocess.Popen(
        ["php", "-S", f"0.0.0.0:{PHP_PORT}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    print(f"✓ PHP server started (PID: {process.pid})", flush=True)

def patch_installer_for_ssl():
    """
    Patch the installer to automatically use SSL connections
    """
    installer_file = f"{PROJECT_FOLDER}/install/index.php"
    
    if not os.path.exists(installer_file):
        print(f"⚠ Installer not found at {installer_file}", flush=True)
        return
    
    print("Checking if installer needs SSL patch...", flush=True)
    
    with open(installer_file, 'r') as f:
        content = f.read()
    
    # Check if already patched
    if 'isrgrootx1.pem' in content or 'ssl_set' in content:
        print("✓ Installer already patched for SSL", flush=True)
        return
    
    # Create a simple patch that wraps mysqli connections
    patch_code = """
// TiDB SSL Connection Patch - Auto-injected
if (!function_exists('tidb_ssl_connect')) {
    function tidb_ssl_connect($host, $username, $password, $database, $port) {
        $mysqli = mysqli_init();
        if (!$mysqli) {
            die('mysqli_init failed');
        }
        $ssl_ca = '/app/isrgrootx1.pem';
        if (file_exists($ssl_ca)) {
            $mysqli->ssl_set(NULL, NULL, $ssl_ca, NULL, NULL);
            $mysqli->options(MYSQLI_OPT_SSL_VERIFY_SERVER_CERT, false);
            if (!$mysqli->real_connect($host, $username, $password, $database, $port, NULL, MYSQLI_CLIENT_SSL)) {
                die('Connect Error (' . mysqli_connect_errno() . ') ' . mysqli_connect_error());
            }
        } else {
            if (!$mysqli->real_connect($host, $username, $password, $database, $port)) {
                die('Connect Error (' . mysqli_connect_errno() . ') ' . mysqli_connect_error());
            }
        }
        return $mysqli;
    }
}
"""
    
    # Insert after <?php tag
    if '<?php' in content:
        content = content.replace('<?php', '<?php\n' + patch_code, 1)
        
        # Replace new mysqli() calls with our function
        import re
        content = re.sub(
            r'new\s+mysqli\s*\(\s*\$([^,]+),\s*\$([^,]+),\s*\$([^,]+),\s*\$([^,]+),\s*\$([^)]+)\s*\)',
            r'tidb_ssl_connect($\1, $\2, $\3, $\4, $\5)',
            content
        )
        
        # Backup and save
        backup_file = installer_file + '.backup'
        if not os.path.exists(backup_file):
            with open(backup_file, 'w') as f:
                f.write(content)
        
        with open(installer_file, 'w') as f:
            f.write(content)
        
        print("✓ Installer patched for SSL connections", flush=True)
    else:
        print("⚠ Could not patch installer automatically", flush=True)

def main():
    print("=" * 60, flush=True)
    print("=== PipraPay Deployment (Direct TiDB + SSL) ===", flush=True)
    print("=" * 60, flush=True)
    
    # Clone project
    if not os.path.exists(PROJECT_FOLDER):
        print(f"Cloning repository...", flush=True)
        os.system(f"git clone {REPO_URL} {PROJECT_FOLDER}")
    
    set_permissions()
    
    # Patch installer to support SSL
    patch_installer_for_ssl()
    
    # Patch installer to support SSL
    patch_installer_for_ssl()
    
    # Start PHP (No proxy needed - direct connection)
    threading.Thread(target=start_php, daemon=True).start()
    time.sleep(2)

    print("\n" + "=" * 60)
    print("📋 INSTALLER CONFIGURATION (Direct TiDB with SSL)")
    print("=" * 60)
    print(f"Database Host:     {TIDB_HOST}")
    print(f"Database Port:     {TIDB_PORT}")
    print(f"Database Name:     {DB_NAME}")
    print(f"Database Username: {TIDB_USER}")
    print(f"Database Password: {TIDB_PASSWORD}")
    print(f"SSL Certificate:   /app/isrgrootx1.pem (auto-configured)")
    print("=" * 60 + "\n")

    port = int(os.getenv("PORT", 5000))
    print(f"🚀 Proxy server running on port {port}")
    server = HTTPServer(("0.0.0.0", port), Handler)
    server.serve_forever()

if __name__ == "__main__":
    main()

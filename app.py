import os
import subprocess
import threading
import requests
import time
import platform
import psutil
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

PHP_PORT = 8001
REPO_URL = "https://github.com/ShovonSheikh/PipraPay.git"
PROJECT_FOLDER = "project"

def print_system_info():
    """Print detailed system information"""
    print("\n" + "=" * 60)
    print("💻 SYSTEM INFORMATION")
    print("=" * 60)
    
    print(f"OS:              {platform.system()} {platform.release()}")
    print(f"OS Version:      {platform.version()}")
    print(f"Architecture:    {platform.machine()}")
    print(f"Processor:       {platform.processor()}")
    print(f"CPU Cores:       {psutil.cpu_count(logical=False)} physical, {psutil.cpu_count(logical=True)} logical")
    
    memory = psutil.virtual_memory()
    print(f"Total RAM:       {memory.total / (1024**3):.2f} GB")
    print(f"Available RAM:   {memory.available / (1024**3):.2f} GB")
    print(f"Used RAM:        {memory.used / (1024**3):.2f} GB ({memory.percent}%)")
    
    disk = psutil.disk_usage('/')
    print(f"Total Disk:      {disk.total / (1024**3):.2f} GB")
    print(f"Available Disk:  {disk.free / (1024**3):.2f} GB")
    print(f"Used Disk:       {disk.used / (1024**3):.2f} GB ({disk.percent}%)")
    
    print(f"Python Version:  {platform.python_version()}")
    print("=" * 60 + "\n")

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

def patch_database_config():
    """
    Patch the PipraPay database configuration to enable SSL/TLS for TiDB
    """
    print("Patching database configuration for TiDB SSL...", flush=True)
    
    config_files = [
        f"{PROJECT_FOLDER}/pp-include/config.php",
        f"{PROJECT_FOLDER}/pp-include/db-config.php",
        f"{PROJECT_FOLDER}/config.php",
        f"{PROJECT_FOLDER}/includes/config.php",
        f"{PROJECT_FOLDER}/includes/db.php",
    ]
    
    # Find the actual config file
    config_file = None
    for cf in config_files:
        if os.path.exists(cf):
            config_file = cf
            print(f"✓ Found config file: {cf}", flush=True)
            break
    
    if not config_file:
        print("⚠️ No config file found yet (will be created during installation)", flush=True)
        return
    
    # Read the config file
    with open(config_file, 'r') as f:
        content = f.read()
    
    # Check if SSL is already configured
    if 'MYSQLI_CLIENT_SSL' in content or 'ssl_set' in content:
        print("✓ SSL already configured in config file", flush=True)
        return
    
    # Add SSL configuration after mysqli connection
    # Look for mysqli connection patterns and add SSL
    ssl_patch = """
// TiDB SSL/TLS Configuration - Auto-injected
if (isset($connection) && $connection instanceof mysqli) {
    $ssl_ca = '/etc/ssl/certs/ca-certificates.crt';
    if (!file_exists($ssl_ca)) {
        $ssl_ca = '/app/ca-certificates.crt';
    }
    if (file_exists($ssl_ca)) {
        $connection->ssl_set(NULL, NULL, $ssl_ca, NULL, NULL);
        $connection->options(MYSQLI_OPT_SSL_VERIFY_SERVER_CERT, false);
    }
}
"""
    
    # Add the patch at the end before closing PHP tag
    if content.strip().endswith('?>'):
        content = content.rsplit('?>', 1)[0] + ssl_patch + "\n?>"
    else:
        content = content + "\n" + ssl_patch
    
    # Write back
    with open(config_file, 'w') as f:
        f.write(content)
    
    print(f"✓ Patched {config_file} with SSL configuration", flush=True)

def create_custom_php_ini():
    """
    Create a custom PHP INI file with MySQLi SSL defaults
    """
    print("Creating custom PHP configuration...", flush=True)
    
    php_ini_content = """
; Custom PHP configuration for TiDB SSL connections
mysqli.allow_local_infile = On
mysqli.allow_persistent = On
mysqli.max_persistent = -1
mysqli.max_links = -1
mysqli.default_port = 4000
mysqli.default_socket =
mysqli.default_host =
mysqli.default_user =
mysqli.default_pw =
mysqli.reconnect = Off

; Enable SSL for MySQL connections
mysqlnd.net_cmd_buffer_size = 4096
mysqlnd.collect_statistics = On
mysqlnd.collect_memory_statistics = On

; Error reporting
display_errors = On
error_reporting = E_ALL
log_errors = On
"""
    
    php_ini_file = "/tmp/custom_php.ini"
    with open(php_ini_file, 'w') as f:
        f.write(php_ini_content)
    
    print(f"✓ Created custom PHP INI at {php_ini_file}", flush=True)
    return php_ini_file

def start_php(php_ini_file):
    print(f"Starting PHP server on internal port {PHP_PORT}...", flush=True)
    
    project_abs_path = os.path.abspath(PROJECT_FOLDER)
    
    print(f"✓ Project path: {project_abs_path}", flush=True)
    print(f"✓ Using PHP INI: {php_ini_file}", flush=True)
    
    # Start PHP server
    process = subprocess.Popen(
        [
            "php",
            "-S", f"127.0.0.1:{PHP_PORT}",
            "-t", project_abs_path,
            "-c", php_ini_file
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        bufsize=1,
        cwd=project_abs_path
    )
    
    print(f"✓ PHP server started (PID: {process.pid})", flush=True)
    
    # Log PHP output
    def log_php_output():
        for line in process.stdout:
            print(f"[PHP] {line.strip()}", flush=True)
    
    threading.Thread(target=log_php_output, daemon=True).start()

def monitor_and_patch_config():
    """
    Monitor for config file creation and patch it when it appears
    """
    print("Starting config file monitor...", flush=True)
    
    config_paths = [
        f"{PROJECT_FOLDER}/pp-include/config.php",
        f"{PROJECT_FOLDER}/config.php",
    ]
    
    checked = set()
    
    while True:
        for config_path in config_paths:
            if config_path not in checked and os.path.exists(config_path):
                print(f"✓ Config file created: {config_path}", flush=True)
                time.sleep(1)  # Wait a bit for file to be fully written
                patch_database_config()
                checked.add(config_path)
        
        time.sleep(5)

def main():
    print("=" * 60, flush=True)
    print("=== PipraPay Deployment (TiDB with SSL) ===", flush=True)
    print("=" * 60, flush=True)
    
    print_system_info()
    
    # Clone project
    if not os.path.exists(PROJECT_FOLDER):
        print(f"Cloning repository...", flush=True)
        os.system(f"git clone {REPO_URL} {PROJECT_FOLDER}")
    
    set_permissions()
    
    # Try to patch existing config
    patch_database_config()
    
    # Create custom PHP INI
    php_ini_file = create_custom_php_ini()
    
    # Start config file monitor in background
    threading.Thread(target=monitor_and_patch_config, daemon=True).start()
    
    # Start PHP
    threading.Thread(target=start_php, args=(php_ini_file,), daemon=True).start()
    time.sleep(3)

    print("\n" + "=" * 60)
    print("📋 INSTALLER CONFIGURATION (TiDB with SSL/TLS)")
    print("=" * 60)
    print(f"Database Host:     {TIDB_HOST}")
    print(f"Database Port:     {TIDB_PORT}")
    print(f"Database Name:     {DB_NAME}")
    print(f"Database Username: {TIDB_USER}")
    print(f"Database Password: {TIDB_PASSWORD}")
    print(f"")
    print(f"⚠️  IMPORTANT - Installation Steps:")
    print(f"   1. During installation, use the credentials above")
    print(f"   2. TiDB connection will be automatically configured with SSL")
    print(f"   3. If connection fails, the config will be auto-patched")
    print(f"")
    print(f"   SSL Certificate: /etc/ssl/certs/ca-certificates.crt")
    print("=" * 60 + "\n")

    port = int(os.getenv("PORT", 8000))
    print(f"🚀 Starting proxy server on 0.0.0.0:{port}")
    print(f"   Forwarding to PHP on 127.0.0.1:{PHP_PORT}")
    print(f"   Visit: https://piprapay.onrender.com\n")
    
    server = HTTPServer(("0.0.0.0", port), Handler)
    server.serve_forever()

if __name__ == "__main__":
    main()

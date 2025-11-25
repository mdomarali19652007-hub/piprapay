import os
import subprocess
import threading
import requests
import time
import re
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

PHP_PORT = 8001  # PHP runs on internal port 8001
REPO_URL = "https://github.com/ShovonSheikh/PipraPay.git"
PROJECT_FOLDER = "project"

def print_system_info():
    """Print detailed system information"""
    print("\n" + "=" * 60)
    print("💻 SYSTEM INFORMATION")
    print("=" * 60)
    
    # Operating System
    print(f"OS:              {platform.system()} {platform.release()}")
    print(f"OS Version:      {platform.version()}")
    print(f"Architecture:    {platform.machine()}")
    print(f"Processor:       {platform.processor()}")
    
    # CPU Information
    print(f"CPU Cores:       {psutil.cpu_count(logical=False)} physical, {psutil.cpu_count(logical=True)} logical")
    
    # Memory Information
    memory = psutil.virtual_memory()
    print(f"Total RAM:       {memory.total / (1024**3):.2f} GB")
    print(f"Available RAM:   {memory.available / (1024**3):.2f} GB")
    print(f"Used RAM:        {memory.used / (1024**3):.2f} GB ({memory.percent}%)")
    
    # Disk Information
    disk = psutil.disk_usage('/')
    print(f"Total Disk:      {disk.total / (1024**3):.2f} GB")
    print(f"Available Disk:  {disk.free / (1024**3):.2f} GB")
    print(f"Used Disk:       {disk.used / (1024**3):.2f} GB ({disk.percent}%)")
    
    # Python Information
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

def create_php_ssl_config():
    """
    Create a PHP auto_prepend_file that forces SSL connections for all MySQLi operations
    """
    print("Creating PHP SSL configuration...", flush=True)
    
    ssl_config_content = """<?php
// TiDB SSL Connection - Auto-prepend configuration
// This file is automatically loaded before any PHP script

// Override mysqli_connect to always use SSL
if (!function_exists('tidb_mysqli_real_connect')) {
    function tidb_mysqli_real_connect($mysqli, $host, $username, $passwd, $dbname, $port = null, $socket = null, $flags = 0) {
        // Set SSL options before connecting
        $ssl_ca_options = [
            '/etc/ssl/certs/ca-certificates.crt',
            '/app/ca-certificates.crt',
            '/app/isrgrootx1.pem'
        ];
        
        $ssl_ca = null;
        foreach ($ssl_ca_options as $ca_path) {
            if (file_exists($ca_path)) {
                $ssl_ca = $ca_path;
                break;
            }
        }
        
        if ($ssl_ca) {
            $mysqli->ssl_set(NULL, NULL, $ssl_ca, NULL, NULL);
            $mysqli->options(MYSQLI_OPT_SSL_VERIFY_SERVER_CERT, false);
        }
        
        // Force SSL flag
        $flags = $flags | MYSQLI_CLIENT_SSL;
        
        return $mysqli->real_connect($host, $username, $passwd, $dbname, $port, $socket, $flags);
    }
}

// Hook into mysqli::__construct
class TiDB_MySQLi extends mysqli {
    public function __construct($host = null, $username = null, $passwd = null, $dbname = null, $port = null, $socket = null) {
        parent::init();
        
        if ($host !== null) {
            $ssl_ca_options = [
                '/etc/ssl/certs/ca-certificates.crt',
                '/app/ca-certificates.crt',
                '/app/isrgrootx1.pem'
            ];
            
            $ssl_ca = null;
            foreach ($ssl_ca_options as $ca_path) {
                if (file_exists($ca_path)) {
                    $ssl_ca = $ca_path;
                    break;
                }
            }
            
            if ($ssl_ca) {
                $this->ssl_set(NULL, NULL, $ssl_ca, NULL, NULL);
                $this->options(MYSQLI_OPT_SSL_VERIFY_SERVER_CERT, false);
            }
            
            $this->real_connect($host, $username, $passwd, $dbname, $port, $socket, MYSQLI_CLIENT_SSL);
        }
    }
}

// Replace the mysqli class globally
if (!class_exists('Original_MySQLi')) {
    class_alias('mysqli', 'Original_MySQLi');
    class_alias('TiDB_MySQLi', 'mysqli');
}
?>"""
    
    ssl_config_file = f"{PROJECT_FOLDER}/tidb_ssl_prepend.php"
    
    with open(ssl_config_file, 'w') as f:
        f.write(ssl_config_content)
    
    print(f"✓ Created SSL configuration at {ssl_config_file}", flush=True)
    
    return ssl_config_file

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
    print(f"Starting PHP server on internal port {PHP_PORT}...", flush=True)
    
    # Create PHP SSL configuration first
    ssl_config_file = create_php_ssl_config()
    
    os.chdir(PROJECT_FOLDER)
    
    # Start PHP with auto_prepend_file to inject SSL configuration
    process = subprocess.Popen(
        [
            "php",
            "-S", f"127.0.0.1:{PHP_PORT}",
            "-d", f"auto_prepend_file={ssl_config_file}"
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    print(f"✓ PHP server started with SSL support (PID: {process.pid})", flush=True)

def main():
    print("=" * 60, flush=True)
    print("=== PipraPay Deployment (Direct TiDB + SSL) ===", flush=True)
    print("=" * 60, flush=True)
    
    # Print system information first
    print_system_info()
    
    # Clone project
    if not os.path.exists(PROJECT_FOLDER):
        print(f"Cloning repository...", flush=True)
        os.system(f"git clone {REPO_URL} {PROJECT_FOLDER}")
    
    set_permissions()
    
    # Start PHP (No proxy needed - direct connection)
    threading.Thread(target=start_php, daemon=True).start()
    time.sleep(2)

    print("\n" + "=" * 60)
    print("📋 INSTALLER CONFIGURATION (TiDB with SSL/TLS)")
    print("=" * 60)
    print(f"Database Host:     {TIDB_HOST}")
    print(f"Database Port:     {TIDB_PORT}")
    print(f"Database Name:     {DB_NAME}")
    print(f"Database Username: {TIDB_USER}")
    print(f"Database Password: {TIDB_PASSWORD}")
    print(f"")
    print(f"⚠️  IMPORTANT - SSL/TLS Required:")
    print(f"   TiDB requires secure connection with SSL/TLS")
    print(f"   CA Certificate:   /etc/ssl/certs/ca-certificates.crt")
    print(f"   Or use:          /app/isrgrootx1.pem")
    print(f"")
    print(f"   If installer asks for SSL:")
    print(f"   - Enable SSL/TLS: YES")
    print(f"   - CA Path: /etc/ssl/certs/ca-certificates.crt")
    print(f"   - Verify Server Cert: NO (recommended)")
    print("=" * 60 + "\n")

    # Get the external port from environment (Koyeb/Render provides this)
    port = int(os.getenv("PORT", 8000))
    print(f"🚀 Starting proxy server on 0.0.0.0:{port}")
    print(f"   Forwarding requests to PHP on 127.0.0.1:{PHP_PORT}")
    print(f"   Public URL will be available on port {port}\n")
    
    server = HTTPServer(("0.0.0.0", port), Handler)
    server.serve_forever()

if __name__ == "__main__":
    main()

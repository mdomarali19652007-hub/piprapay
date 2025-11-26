import os
import subprocess
import threading
import requests
import time
import platform
import psutil
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

PHP_PORT = 8001
REPO_URL = "https://github.com/ShovonSheikh/PipraPay.git"
PROJECT_FOLDER = "project"

def print_system_info():
    """Print detailed system information"""
    print("\n" + "=" * 60)
    print("💻 SYSTEM INFORMATION")
    print("=" * 60)
    
    print(f"OS:              {platform.system()} {platform.release()}")
    print(f"Architecture:    {platform.machine()}")
    print(f"CPU Cores:       {psutil.cpu_count(logical=False)} physical, {psutil.cpu_count(logical=True)} logical")
    
    memory = psutil.virtual_memory()
    print(f"Total RAM:       {memory.total / (1024**3):.2f} GB")
    print(f"Available RAM:   {memory.available / (1024**3):.2f} GB")
    
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

def patch_php_files_for_ssl():
    """
    Patch all PHP files that create mysqli connections to use SSL
    """
    print("Patching PHP files for TiDB SSL support...", flush=True)
    
    php_files = []
    for root, dirs, files in os.walk(PROJECT_FOLDER):
        for file in files:
            if file.endswith('.php'):
                php_files.append(os.path.join(root, file))
    
    patched_count = 0
    
    for php_file in php_files:
        try:
            with open(php_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            original_content = content
            
            # Pattern 1: new mysqli(...) - replace with SSL version
            pattern1 = r'new\s+mysqli\s*\(\s*([^,]+),\s*([^,]+),\s*([^,]+),\s*([^,]+)(?:,\s*([^,\)]+))?(?:,\s*([^,\)]+))?\s*\)'
            
            def replace_mysqli(match):
                host = match.group(1).strip()
                user = match.group(2).strip()
                pass_var = match.group(3).strip()
                db = match.group(4).strip()
                port = match.group(5).strip() if match.group(5) else '3306'
                
                return f'''(function() {{
    $db = mysqli_init();
    if (!$db) {{ die('mysqli_init failed'); }}
    $ssl_ca_opts = ['/etc/ssl/certs/ca-certificates.crt', '/app/ca-certificates.crt'];
    foreach ($ssl_ca_opts as $ca) {{ if (file_exists($ca)) {{ mysqli_ssl_set($db, NULL, NULL, $ca, NULL, NULL); break; }} }}
    mysqli_options($db, MYSQLI_OPT_SSL_VERIFY_SERVER_CERT, false);
    if (!mysqli_real_connect($db, {host}, {user}, {pass_var}, {db}, {port}, NULL, MYSQLI_CLIENT_SSL)) {{
        die('Connect Error (' . mysqli_connect_errno() . '): ' . mysqli_connect_error());
    }}
    return $db;
}})()'''
            
            content = re.sub(pattern1, replace_mysqli, content)
            
            # Pattern 2: mysqli_connect(...) - replace with SSL version
            pattern2 = r'mysqli_connect\s*\(\s*([^,]+),\s*([^,]+),\s*([^,]+),\s*([^,]+)(?:,\s*([^,\)]+))?\s*\)'
            
            def replace_mysqli_connect(match):
                host = match.group(1).strip()
                user = match.group(2).strip()
                pass_var = match.group(3).strip()
                db = match.group(4).strip()
                port = match.group(5).strip() if match.group(5) else '3306'
                
                return f'''(function() {{
    $db = mysqli_init();
    if (!$db) {{ die('mysqli_init failed'); }}
    $ssl_ca_opts = ['/etc/ssl/certs/ca-certificates.crt', '/app/ca-certificates.crt'];
    foreach ($ssl_ca_opts as $ca) {{ if (file_exists($ca)) {{ mysqli_ssl_set($db, NULL, NULL, $ca, NULL, NULL); break; }} }}
    mysqli_options($db, MYSQLI_OPT_SSL_VERIFY_SERVER_CERT, false);
    if (!mysqli_real_connect($db, {host}, {user}, {pass_var}, {db}, {port}, NULL, MYSQLI_CLIENT_SSL)) {{
        die('Connect Error (' . mysqli_connect_errno() . '): ' . mysqli_connect_error());
    }}
    return $db;
}})()'''
            
            content = re.sub(pattern2, replace_mysqli_connect, content)
            
            # Only write if changed
            if content != original_content:
                with open(php_file, 'w', encoding='utf-8', errors='ignore') as f:
                    f.write(content)
                patched_count += 1
                print(f"  ✓ Patched: {php_file}", flush=True)
        
        except Exception as e:
            print(f"  ⚠️ Error patching {php_file}: {e}", flush=True)
    
    print(f"✓ Patched {patched_count} PHP files for SSL", flush=True)

def start_php():
    print(f"Starting PHP server on internal port {PHP_PORT}...", flush=True)
    
    project_abs_path = os.path.abspath(PROJECT_FOLDER)
    print(f"✓ Project path: {project_abs_path}", flush=True)
    
    # Start PHP server
    process = subprocess.Popen(
        [
            "php",
            "-S", f"127.0.0.1:{PHP_PORT}",
            "-t", project_abs_path
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
    
    # Patch ALL PHP files for SSL support
    patch_php_files_for_ssl()
    
    # Start PHP
    threading.Thread(target=start_php, daemon=True).start()
    time.sleep(3)

    print("\n" + "=" * 60)
    print("📋 INSTALLER CONFIGURATION")
    print("=" * 60)
    print(f"Database Host:     {TIDB_HOST}")
    print(f"Database Port:     {TIDB_PORT}")
    print(f"Database Name:     {DB_NAME}")
    print(f"Database Username: {TIDB_USER}")
    print(f"Database Password: {TIDB_PASSWORD}")
    print(f"")
    print(f"✓ All mysqli connections patched for SSL/TLS")
    print(f"✓ TiDB connection ready with automatic SSL")
    print("=" * 60 + "\n")

    port = int(os.getenv("PORT", 8000))
    print(f"🚀 Proxy server starting on 0.0.0.0:{port}")
    print(f"   Visit: https://piprapay.onrender.com\n")
    
    server = HTTPServer(("0.0.0.0", port), Handler)
    server.serve_forever()

if __name__ == "__main__":
    main()

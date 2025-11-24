import os
import subprocess
import threading
import requests
import time
import socket
import ssl
import select
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
# 🔌 NATIVE PYTHON SSL PROXY
# This replaces 'socat'. It listens on 3306, encrypts traffic, and sends to TiDB.
# ==============================================================================
def handle_client_connection(client_socket):
    remote_socket = None
    try:
        # 1. Connect to TiDB
        remote_socket = socket.create_connection((TIDB_HOST, TIDB_PORT), timeout=10)
        
        # 2. Wrap connection in SSL (The critical part TiDB needs)
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        # SNI is required by TiDB Cloud
        remote_socket = context.wrap_socket(remote_socket, server_hostname=TIDB_HOST)

        # 3. Pipe data between Local Client (PHP) and Remote Server (TiDB)
        while True:
            r, w, x = select.select([client_socket, remote_socket], [], [], 60)
            if client_socket in r:
                data = client_socket.recv(4096)
                if not data: break
                remote_socket.sendall(data)
            if remote_socket in r:
                data = remote_socket.recv(4096)
                if not data: break
                client_socket.sendall(data)

    except Exception as e:
        # Silent fail on disconnects to avoid log spam
        pass
    finally:
        if client_socket: client_socket.close()
        if remote_socket: remote_socket.close()

def start_python_db_proxy():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        server.bind(('127.0.0.1', LOCAL_DB_PORT))
        server.listen(5)
        print(f"✓ Python SSL Proxy listening on 127.0.0.1:{LOCAL_DB_PORT}", flush=True)
        
        while True:
            client_sock, addr = server.accept()
            # Handle each connection in a separate thread
            proxy_thread = threading.Thread(target=handle_client_connection, args=(client_sock,))
            proxy_thread.daemon = True
            proxy_thread.start()
            
    except Exception as e:
        print(f"❌ Proxy Error: {e}", flush=True)

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

def main():
    print("=" * 60, flush=True)
    print("=== PipraPay Deployment (Python Native Proxy) ===", flush=True)
    print("=" * 60, flush=True)
    
    # Clone project
    if not os.path.exists(PROJECT_FOLDER):
        print(f"Cloning repository...", flush=True)
        os.system(f"git clone {REPO_URL} {PROJECT_FOLDER}")
    
    set_permissions()
    
    # 1. Start the Python Native Proxy (Background Thread)
    threading.Thread(target=start_python_db_proxy, daemon=True).start()
    
    # 2. Start PHP
    threading.Thread(target=start_php, daemon=True).start()
    time.sleep(2)

    print("\n" + "=" * 60)
    print("📋 INSTALLER CONFIGURATION")
    print("=" * 60)
    print(f"Database Host:     127.0.0.1")
    print(f"Database Port:     {LOCAL_DB_PORT}")
    print(f"Database Name:     {DB_NAME}")
    print(f"Database Username: {TIDB_USER}")
    print(f"Database Password: {TIDB_PASSWORD}")
    print("=" * 60 + "\n")

    port = int(os.getenv("PORT", 5000))
    print(f"🚀 Proxy server running on port {port}")
    server = HTTPServer(("0.0.0.0", port), Handler)
    server.serve_forever()

if __name__ == "__main__":
    main()

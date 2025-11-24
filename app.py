import os
import subprocess
import threading
import requests
import time
import socket
import ssl
from http.server import BaseHTTPRequestHandler, HTTPServer

# ==========================================
# 🔧 CONFIGURATION (YOUR TIDB DETAILS)
# ==========================================
TIDB_HOST = "gateway01.eu-central-1.prod.aws.tidbcloud.com"
TIDB_PORT = "4000"
TIDB_USER = "467VfcbbnoxchaS.root"
TIDB_PASSWORD = "U1O54Xyee6M4gR8u"
DB_NAME = "test"
# ==========================================

PHP_PORT = 8000
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

def test_tidb_connection():
    """Directly test if Python can reach TiDB before starting socat"""
    print(f"\n🔍 Testing Direct Connection to {TIDB_HOST}:{TIDB_PORT}...", flush=True)
    try:
        # Create a raw socket
        sock = socket.create_connection((TIDB_HOST, int(TIDB_PORT)), timeout=5)
        
        # Wrap it in SSL
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        ssock = context.wrap_socket(sock, server_hostname=TIDB_HOST)
        
        print("✅ Direct Connection SUCCESS! Network is good.", flush=True)
        ssock.close()
        return True
    except Exception as e:
        print(f"❌ Direct Connection FAILED: {str(e)}", flush=True)
        print("   -> Check your Firewall or Credentials.", flush=True)
        return False

def start_db_proxy():
    """Start socat with TLS1.2 enforcement"""
    print(f"=== Starting Database Proxy ===", flush=True)
    
    # Updated command:
    # 1. TCP4-LISTEN: Forces IPv4 (prevents binding issues)
    # 2. reuseaddr: Allows port reuse if script restarts
    # 3. method=TLS1.2: Forces the correct encryption protocol for TiDB
    cmd = [
        "socat",
        "-d", "-d", # Verbose logging
        "TCP4-LISTEN:3306,fork,reuseaddr,bind=127.0.0.1",
        f"OPENSSL:{TIDB_HOST}:{TIDB_PORT},verify=0,sni={TIDB_HOST},method=TLS1.2"
    ]
    
    print(f"🔗 Creating SSL Tunnel...", flush=True)
    subprocess.Popen(cmd)
    
    time.sleep(2)
    print("✓ Proxy running on 127.0.0.1:3306", flush=True)

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
    print("=== PipraPay Deployment (v3 Fix) ===", flush=True)
    print("=" * 60, flush=True)
    
    # 1. Test Network First
    if not test_tidb_connection():
        print("⚠️ WARNING: TiDB seems unreachable. Proxy might fail.")
    
    # 2. Clone project
    if not os.path.exists(PROJECT_FOLDER):
        print(f"Cloning repository...", flush=True)
        os.system(f"git clone {REPO_URL} {PROJECT_FOLDER}")
    
    set_permissions()
    
    # 3. Start the SSL Proxy
    start_db_proxy()
    
    # 4. Start PHP
    threading.Thread(target=start_php, daemon=True).start()
    time.sleep(2)

    print("\n" + "=" * 60)
    print("📋 INSTALLER CONFIGURATION")
    print("=" * 60)
    print(f"Database Host:     127.0.0.1")
    print(f"Database Port:     3306")
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

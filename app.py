import os
import subprocess
import threading
import requests
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

# --- CONFIGURATION: UPDATE THESE WITH YOUR TIDB DETAILS ---
PHP_PORT = 8000
# TiDB usually uses port 4000, check your dashboard
DB_PORT = 4000 
DB_HOST = "gateway01.eu-central-1.prod.aws.tidbcloud.com" # Replace with YOUR TiDB Host
DB_USER = "467VfcbbnoxchaS.root"                               # Replace with YOUR TiDB User
DB_PASSWORD = "U1O54Xyee6M4gR8u"                     # Replace with YOUR TiDB Password
DB_NAME = "test"
# ----------------------------------------------------------

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
    """Set proper file permissions for PipraPay directories"""
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
            print(f"✓ Set permissions for {directory}", flush=True)

def start_php():
    """Start PHP built-in server"""
    print(f"Starting PHP server on port {PHP_PORT}...", flush=True)
    os.chdir(PROJECT_FOLDER)
    
    # Pass TiDB credentials to PHP via Environment Variables
    env = os.environ.copy()
    env["DB_HOST"] = DB_HOST
    env["DB_PORT"] = str(DB_PORT)
    env["DB_USER"] = DB_USER
    env["DB_PASS"] = DB_PASSWORD
    env["DB_NAME"] = DB_NAME
    env["DB_SSL_CA"] = "/app/ca.pem"  # Path to the cert inside Docker

    process = subprocess.Popen(
        ["php", "-S", f"0.0.0.0:{PHP_PORT}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env
    )
    print(f"✓ PHP server started (PID: {process.pid})", flush=True)

def main():
    print("=" * 60, flush=True)
    print("=== PipraPay Deployment (TiDB Mode) ===", flush=True)
    print("=" * 60, flush=True)
    
    # Clone project if not exists
    if not os.path.exists(PROJECT_FOLDER):
        print(f"Cloning repository from {REPO_URL}...", flush=True)
        os.system(f"git clone {REPO_URL} {PROJECT_FOLDER}")
    
    set_permissions()
    
    # Start PHP (No Local MySQL!)
    threading.Thread(target=start_php, daemon=True).start()
    time.sleep(2)

    # Print Credentials for the Installer
    print("\n" + "=" * 60)
    print("📋 USE THESE DETAILS IN THE INSTALLER")
    print("=" * 60)
    print(f"Database Host:     {DB_HOST}")
    print(f"Database Port:     {DB_PORT}")
    print(f"Database Name:     {DB_NAME}")
    print(f"Database Username: {DB_USER}")
    print(f"Database Password: {DB_PASSWORD}")
    print("=" * 60 + "\n")

    port = int(os.getenv("PORT", 5000))
    print(f"🚀 Proxy server running on port {port}")
    server = HTTPServer(("0.0.0.0", port), Handler)
    server.serve_forever()

if __name__ == "__main__":
    main()

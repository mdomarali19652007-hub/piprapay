import os
import subprocess
import threading
import requests
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

PHP_PORT = 8000
REPO_URL = "https://github.com/ShovonSheikh/PipraPay.git"
PROJECT_FOLDER = "project"


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # health check
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status": "ok"}')
            return

        # everything else goes to PHP
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
    print("Setting file permissions...")
    
    directories = [
        f"{PROJECT_FOLDER}/invoice",
        f"{PROJECT_FOLDER}/payment",
        f"{PROJECT_FOLDER}/admin",
        f"{PROJECT_FOLDER}/pp-include"
    ]
    
    for directory in directories:
        if os.path.exists(directory):
            os.system(f"chmod -R 777 {directory}")
            print(f"✓ Set permissions for {directory}")
        else:
            print(f"⚠ Directory not found: {directory}")


def start_php():
    """Start PHP built-in server"""
    print(f"Starting PHP server on port {PHP_PORT}...")
    os.chdir(PROJECT_FOLDER)
    
    # Start PHP with error logging
    process = subprocess.Popen(
        ["php", "-S", f"0.0.0.0:{PHP_PORT}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    print(f"✓ PHP server started (PID: {process.pid})")


def main():
    print("=== PipraPay Deployment Starting ===")
    
    # Clone project if not exists
    if not os.path.exists(PROJECT_FOLDER):
        print(f"Cloning repository from {REPO_URL}...")
        result = os.system(f"git clone {REPO_URL} {PROJECT_FOLDER}")
        if result == 0:
            print("✓ Repository cloned successfully")
        else:
            print("✗ Failed to clone repository")
            return
    else:
        print("✓ Project folder already exists")

    # Set file permissions after cloning
    set_permissions()

    # Give a moment for permissions to apply
    time.sleep(1)

    # Start PHP server in background thread
    threading.Thread(target=start_php, daemon=True).start()
    
    # Wait for PHP server to start
    time.sleep(2)

    # Start Python proxy server
    port = int(os.getenv("PORT", 5000))
    print(f"Starting Python proxy server on port {port}...")
    print(f"Health check available at: http://0.0.0.0:{port}/health")
    print(f"All other requests proxied to PHP on port {PHP_PORT}")
    print("=== Server Ready ===\n")
    
    server = HTTPServer(("0.0.0.0", port), Handler)
    server.serve_forever()


if __name__ == "__main__":
    main()

import os
import subprocess
import threading
import requests
import time
import platform
import psutil
import re
from http.server import BaseHTTPRequestHandler, HTTPServer



import mysql.connector
import secrets
import string

# ==========================================
# 🔧 DATABASE CONFIGURATION
# ==========================================
DB_HOST = "127.0.0.1"
DB_PORT = 3306
DB_NAME = "piprapay"
DB_USER = "piprapay_user"
# Generate a random password for the database user
DB_PASSWORD = ''.join(secrets.choice(string.ascii_letters + string.digits) for i in range(16))
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



def start_mysql():
    print("Starting MySQL server...", flush=True)
    # Start MySQL in the background
    process = subprocess.Popen(["mysqld", "--skip-grant-tables"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True, bufsize=1)
    
    def log_mysql_output():
        for line in process.stdout:
            print(f"[MySQL] {line.strip()}", flush=True)
    
    threading.Thread(target=log_mysql_output, daemon=True).start()
    time.sleep(5)  # Give MySQL some time to start
    print("✓ MySQL server started", flush=True)

def configure_mysql():
    print("Configuring MySQL database...", flush=True)
    try:
        # Connect to MySQL without authentication
        conn = mysql.connector.connect(host=DB_HOST, port=DB_PORT, user='root')
        cursor = conn.cursor()
        
        # Flush privileges to be able to set a password
        cursor.execute("FLUSH PRIVILEGES")
        
        # Set root password
        root_password = ''.join(secrets.choice(string.ascii_letters + string.digits) for i in range(16))
        cursor.execute(f"ALTER USER 'root'@'localhost' IDENTIFIED BY '{root_password}'")
        print("✓ Root password set", flush=True)
        
        # Create the database if it doesn't exist
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME}")
        print(f"✓ Database '{DB_NAME}' created or already exists", flush=True)
        
        # Create the user and grant privileges
        cursor.execute(f"CREATE USER IF NOT EXISTS '{DB_USER}'@'localhost' IDENTIFIED BY '{DB_PASSWORD}'")
        cursor.execute(f"GRANT ALL PRIVILEGES ON {DB_NAME}.* TO '{DB_USER}'@'localhost'")
        cursor.execute("FLUSH PRIVILEGES")
        print(f"✓ User '{DB_USER}' created and granted privileges", flush=True)
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"⚠️ Error configuring MySQL: {e}", flush=True)

def show_connection_info():
    print("\n" + "=" * 60)
    print("📋 DATABASE CONNECTION INFORMATION")
    print("=" * 60)
    print(f"Database Host:     {DB_HOST}")
    print(f"Database Port:     {DB_PORT}")
    print(f"Database Name:     {DB_NAME}")
    print(f"Database Username: {DB_USER}")
    print(f"Database Password: {DB_PASSWORD}")
    print("=" * 60 + "\n")

def start_php():
    print(f"Starting PHP server on internal port {PHP_PORT}...", flush=True)
    
    project_abs_path = os.path.abspath(PROJECT_FOLDER)
    print(f"✓ Project path: {project_abs_path}", flush=True)
    
    start_mysql()
    configure_mysql()
    show_connection_info()

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

    

    port = int(os.getenv("PORT", 8000))
    print(f"🚀 Proxy server starting on 0.0.0.0:{port}")
    print(f"   Visit: https://piprapay.onrender.com\n")
    
    server = HTTPServer(("0.0.0.0", port), Handler)
    server.serve_forever()

if __name__ == "__main__":
    main()

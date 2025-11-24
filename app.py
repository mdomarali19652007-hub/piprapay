import os
import subprocess
import threading
import requests
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

PHP_PORT = 8000
MYSQL_PORT = 3306
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


def start_mysql():
    """Initialize and start MySQL server"""
    print("=== Starting MySQL Database ===", flush=True)
    
    # Get environment variables
    root_password = os.getenv("MYSQL_ROOT_PASSWORD", "R00t@Pipra2024!Secure#DB")
    database = os.getenv("MYSQL_DATABASE", "piprapay")
    user = os.getenv("MYSQL_USER", "piprapay_user")
    password = os.getenv("MYSQL_PASSWORD", "Pipra@Pay2024!Str0ng#Pass")
    
    print(f"Database: {database}, User: {user}", flush=True)
    
    # Initialize MySQL data directory if not exists
    if not os.path.exists("/var/lib/mysql/mysql"):
        print("Initializing MySQL data directory...", flush=True)
        os.system("mysqld --initialize-insecure --user=mysql --datadir=/var/lib/mysql")
        print("✓ MySQL initialized", flush=True)
    
    # Start MySQL server in background
    print(f"Starting MySQL server on port {MYSQL_PORT}...", flush=True)
    mysql_process = subprocess.Popen(
        ["mysqld", 
         "--user=mysql", 
         "--datadir=/var/lib/mysql",
         "--socket=/var/run/mysqld/mysqld.sock",
         "--pid-file=/var/run/mysqld/mysqld.pid"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    print(f"✓ MySQL server started (PID: {mysql_process.pid})", flush=True)
    
    # Wait for MySQL to be ready
    print("Waiting for MySQL to be ready...", flush=True)
    max_attempts = 30
    for i in range(max_attempts):
        result = os.system("mysqladmin ping -h localhost --silent")
        if result == 0:
            print("✓ MySQL is ready!", flush=True)
            break
        time.sleep(1)
        if i == max_attempts - 1:
            print("✗ MySQL failed to start properly", flush=True)
            return
    
    # Set root password and create database/user
    print("Configuring MySQL database...", flush=True)
    
    # First, set root password (no password needed initially after --initialize-insecure)
    os.system(f"mysql -u root -e \"ALTER USER 'root'@'localhost' IDENTIFIED BY '{root_password}';\" 2>/dev/null")
    
    # Now use the root password for subsequent commands
    commands = [
        f"CREATE DATABASE IF NOT EXISTS {database};",
        f"CREATE USER IF NOT EXISTS '{user}'@'localhost' IDENTIFIED BY '{password}';",
        f"CREATE USER IF NOT EXISTS '{user}'@'%' IDENTIFIED BY '{password}';",
        f"GRANT ALL PRIVILEGES ON {database}.* TO '{user}'@'localhost';",
        f"GRANT ALL PRIVILEGES ON {database}.* TO '{user}'@'%';",
        f"FLUSH PRIVILEGES;"
    ]
    
    for cmd in commands:
        os.system(f'mysql -u root -p"{root_password}" -e "{cmd}" 2>/dev/null')
    
    print(f"✓ Database '{database}' created", flush=True)
    print(f"✓ User '{user}' created with all privileges", flush=True)
    print("", flush=True)
    print("=" * 60, flush=True)
    print("🗄️  MYSQL DATABASE CONNECTION DETAILS", flush=True)
    print("=" * 60, flush=True)
    print(f"Host:          localhost (or 127.0.0.1)", flush=True)
    print(f"Port:          {MYSQL_PORT}", flush=True)
    print(f"Socket:        /var/run/mysqld/mysqld.sock", flush=True)
    print(f"Database:      {database}", flush=True)
    print(f"Username:      {user}", flush=True)
    print(f"Password:      {password}", flush=True)
    print(f"Root Password: {root_password}", flush=True)
    print("=" * 60, flush=True)
    print("", flush=True)
    print("💡 Use these credentials to configure your PipraPay application", flush=True)
    print("💡 PHP will automatically use the socket file for 'localhost'", flush=True)
    print("", flush=True)


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
        else:
            print(f"⚠ Directory not found: {directory}", flush=True)


def start_php():
    """Start PHP built-in server"""
    print(f"Starting PHP server on port {PHP_PORT}...", flush=True)
    os.chdir(PROJECT_FOLDER)
    
    # Start PHP with error logging
    process = subprocess.Popen(
        ["php", "-S", f"0.0.0.0:{PHP_PORT}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    print(f"✓ PHP server started (PID: {process.pid})", flush=True)


def main():
    print("=" * 60, flush=True)
    print("=== PipraPay Deployment Starting ===", flush=True)
    print("=" * 60, flush=True)
    print("", flush=True)
    
    # Start MySQL first
    start_mysql()
    
    # Clone project if not exists
    if not os.path.exists(PROJECT_FOLDER):
        print(f"Cloning repository from {REPO_URL}...", flush=True)
        result = os.system(f"git clone {REPO_URL} {PROJECT_FOLDER}")
        if result == 0:
            print("✓ Repository cloned successfully", flush=True)
        else:
            print("✗ Failed to clone repository", flush=True)
            return
    else:
        print("✓ Project folder already exists", flush=True)

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
    print("", flush=True)
    print("=" * 60, flush=True)
    print(f"🚀 Python proxy server starting on port {port}", flush=True)
    print(f"✓ Health check: http://0.0.0.0:{port}/health", flush=True)
    print(f"✓ Requests proxied to PHP on port {PHP_PORT}", flush=True)
    print("=" * 60, flush=True)
    print("=== 🎉 All Services Ready! ===", flush=True)
    print("=" * 60, flush=True)
    print("", flush=True)
    
    server = HTTPServer(("0.0.0.0", port), Handler)
    server.serve_forever()


if __name__ == "__main__":
    main()

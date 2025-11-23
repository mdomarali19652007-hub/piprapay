import os
import subprocess
import threading
import requests
from http.server import BaseHTTPRequestHandler, HTTPServer

PHP_PORT = 8000
REPO_URL = "https://github.com/username/repository.git"  # change this
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


def start_php():
    os.chdir(PROJECT_FOLDER)
    subprocess.Popen(
        ["php", "-S", f"0.0.0.0:{PHP_PORT}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )


def main():
    # install php + git
    os.system("sudo apt-get update -y")
    os.system("sudo apt-get install -y php git")

    # clone project
    if not os.path.exists(PROJECT_FOLDER):
        os.system(f"git clone {REPO_URL} {PROJECT_FOLDER}")

    # run php in background thread
    threading.Thread(target=start_php, daemon=True).start()

    # render gives PORT
    port = int(os.getenv("PORT", 5000))
    server = HTTPServer(("0.0.0.0", port), Handler)
    server.serve_forever()


if __name__ == "__main__":
    main()

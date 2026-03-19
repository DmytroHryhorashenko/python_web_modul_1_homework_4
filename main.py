import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs
from datetime import datetime

# Порты
HTTP_PORT = 3000
SOCKET_PORT = 5001

STORAGE_FILE = Path("storage/data.json")
TEMPLATES_DIR = Path("templates")
STATIC_DIR = Path("static")

# UDP сервер
def run_socket_server():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", SOCKET_PORT))
    print(f"Socket server running on port {SOCKET_PORT}")

    while True:
        data, addr = sock.recvfrom(4096)
        try:
            message_dict = json.loads(data.decode())
        except Exception:
            continue

        STORAGE_FILE.parent.mkdir(exist_ok=True)
        if STORAGE_FILE.exists():
            with open(STORAGE_FILE, "r", encoding="utf-8") as f:
                existing = json.load(f)
        else:
            existing = {}

        timestamp = str(datetime.now())
        existing[timestamp] = message_dict

        with open(STORAGE_FILE, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=4, ensure_ascii=False)

# HTTP сервер
class Handler(BaseHTTPRequestHandler):
    def send_html(self, filename, status=200):
        path = TEMPLATES_DIR / filename
        if path.exists():
            self.send_response(status)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(path.read_bytes())
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"404 Not Found")

    def do_GET(self):
        if self.path == "/":
            self.send_html("index.html")
        elif self.path == "/message":
            self.send_html("message.html")
        elif self.path.startswith("/static/"):
            file_path = STATIC_DIR / self.path[len("/static/"):]
            if file_path.exists() and file_path.is_file():
                self.send_response(200)
                if file_path.suffix == ".css":
                    self.send_header("Content-type", "text/css")
                elif file_path.suffix == ".png":
                    self.send_header("Content-type", "image/png")
                else:
                    self.send_header("Content-type", "application/octet-stream")
                self.end_headers()
                self.wfile.write(file_path.read_bytes())
            else:
                self.send_html("error.html", 404)
        else:
            self.send_html("error.html", 404)

    def do_POST(self):
        if self.path == "/send":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode()
            data = parse_qs(body)
            username = data.get("username", [""])[0]
            message = data.get("message", [""])[0]

            # Отправка на UDP сервер
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            msg = json.dumps({"username": username, "message": message})
            sock.sendto(msg.encode(), ("127.0.0.1", SOCKET_PORT))
            sock.close()

            # Перенаправление обратно на форму
            self.send_response(303)
            self.send_header("Location", "/message")
            self.end_headers()
        else:
            self.send_html("error.html", 404)

# Запуск серверов в потоках
if __name__ == "__main__":
    # Socket сервер
    threading.Thread(target=run_socket_server, daemon=True).start()

    # HTTP сервер
    httpd = HTTPServer(("0.0.0.0", HTTP_PORT), Handler)
    print(f"HTTP server running on port {HTTP_PORT}")
    httpd.serve_forever()
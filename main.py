import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs
from datetime import datetime

HTTP_PORT = 3000
SOCKET_PORT = 5000

STORAGE_FILE = Path("storage/data.json")
TEMPLATES_DIR = Path("templates")
STATIC_DIR = Path("static")


# UDP Socket сервер
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
    def send_html(self, content, status=200):
        self.send_response(status)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(content.encode("utf-8"))

    def do_GET(self):
        if self.path in ["/", "/index.html"]:
            path = TEMPLATES_DIR / "index.html"

        elif self.path == "/message":
            path = TEMPLATES_DIR / "message.html"

        # ✅ VIEW MESSAGES
        elif self.path == "/view-message":
            path = TEMPLATES_DIR / "view-message.html"

            if path.exists():
                if STORAGE_FILE.exists():
                    with open(STORAGE_FILE, "r", encoding="utf-8") as f:
                        data = json.load(f)
                else:
                    data = {}

                if not data:
                    messages_html = "<p>No messages yet.</p>"
                else:
                    messages_html = ""
                    for ts, msg in sorted(data.items()):
                        messages_html += f"""
                        <div class="message-box">
                            <div class="message-text">
                                <b>{msg['username']}</b>: {msg['message']}
                            </div>
                            <form method="post" action="/delete">
                                <input type="hidden" name="timestamp" value="{ts}">
                                <button type="submit" class="btn small">Delete</button>
                            </form>
                        </div>
                        """

                template = path.read_text(encoding="utf-8")
                template = template.replace("{{messages}}", messages_html)
                self.send_html(template)
                return
            else:
                path = TEMPLATES_DIR / "error.html"

        elif self.path.startswith("/static/"):
            file_path = STATIC_DIR / self.path[len("/static/") :]
            if file_path.exists():
                self.send_response(200)
                if file_path.suffix == ".css":
                    self.send_header("Content-type", "text/css")
                elif file_path.suffix == ".png":
                    self.send_header("Content-type", "image/png")
                else:
                    self.send_header("Content-type", "application/octet-stream")
                self.end_headers()
                self.wfile.write(file_path.read_bytes())
                return
            else:
                path = TEMPLATES_DIR / "error.html"

        else:
            path = TEMPLATES_DIR / "error.html"

        if path.exists():
            self.send_html(path.read_text(encoding="utf-8"), 200 if "error" not in path.name else 404)
        else:
            self.send_html("404 Not Found", 404)

    def do_POST(self):
        # ✅ SEND MESSAGE
        if self.path == "/send":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode()
            data = parse_qs(body)

            username = data.get("username", [""])[0]
            message = data.get("message", [""])[0]

            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            msg = json.dumps({"username": username, "message": message})
            sock.sendto(msg.encode(), ("127.0.0.1", SOCKET_PORT))
            sock.close()

            self.send_response(303)
            self.send_header("Location", "/message")
            self.end_headers()

        # ✅ DELETE MESSAGE
        elif self.path == "/delete":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode()
            data = parse_qs(body)

            timestamp = data.get("timestamp", [""])[0]

            if STORAGE_FILE.exists():
                with open(STORAGE_FILE, "r", encoding="utf-8") as f:
                    existing = json.load(f)

                if timestamp in existing:
                    del existing[timestamp]

                    with open(STORAGE_FILE, "w", encoding="utf-8") as f:
                        json.dump(existing, f, indent=4, ensure_ascii=False)

            self.send_response(303)
            self.send_header("Location", "/view-message")
            self.end_headers()

        else:
            self.send_html("404 Not Found", 404)


if __name__ == "__main__":
    threading.Thread(target=run_socket_server, daemon=True).start()
    httpd = HTTPServer(("0.0.0.0", HTTP_PORT), Handler)
    print(f"HTTP server running on port {HTTP_PORT}")
    httpd.serve_forever()
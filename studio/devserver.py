"""Browser mode: serve the UI over http://127.0.0.1 and expose Api methods at POST /api/<name>.

Used for development, and as a fallback when pywebview isn't installed.
Only listens on localhost.
"""
import json
import mimetypes
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

from . import media
from .paths import WEB_DIR
from .util import is_image


def make_handler(api):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):  # keep the console quiet
            pass

        def _send(self, code, body, ctype="application/json", cache=False):
            data = body if isinstance(body, bytes) else json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "max-age=3600" if cache else "no-store")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            parsed = urlparse(self.path)
            path = unquote(parsed.path)
            if path.startswith("/media/"):
                return self._media(path, parse_qs(parsed.query))
            if path in ("", "/"):
                path = "/index.html"
            f = (WEB_DIR / path.lstrip("/")).resolve()
            if WEB_DIR.resolve() not in f.parents or not f.is_file():
                return self._send(404, {"error": "not found"})
            ctype = mimetypes.guess_type(f.name)[0] or "application/octet-stream"
            if f.suffix == ".js":
                ctype = "text/javascript"
            self._send(200, f.read_bytes(), ctype)

        def _media(self, path, q):
            """Thumbnails and full images from the user's folders (token-protected, images only)."""
            if q.get("k", [""])[0] != api._media_token:
                return self._send(403, {"error": "bad token"})
            p = q.get("p", [""])[0]
            # dataset images, plus the animated sample GIFs LoRA Studio makes
            if not p or not (is_image(p) or p.lower().endswith(".gif")) or not os.path.isfile(p):
                return self._send(404, {"error": "not found"})
            try:
                if path == "/media/thumb":
                    size = max(32, min(1024, int(q.get("s", ["256"])[0])))
                    data = media.thumbnail_bytes(p, size)
                    self._send(200, data, "image/jpeg", cache=True)
                else:
                    ctype = mimetypes.guess_type(p)[0] or "application/octet-stream"
                    with open(p, "rb") as f:
                        self._send(200, f.read(), ctype)
            except Exception as e:  # unreadable image
                self._send(500, {"error": str(e)})

        def _trusted(self):
            """Only our own page may call the API: same host, same origin, JSON body."""
            port = self.server.server_address[1]
            ok_hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
            if self.headers.get("Host") not in ok_hosts:
                return False
            origin = self.headers.get("Origin")
            if origin and origin.rstrip("/") not in {f"http://{h}" for h in ok_hosts}:
                return False
            return (self.headers.get("Content-Type") or "").startswith("application/json")

        def do_POST(self):
            path = urlparse(self.path).path
            if not path.startswith("/api/"):
                return self._send(404, {"error": "not found"})
            if getattr(api, "_window", None) is not None:   # app window talks to Python directly
                return self._send(403, {"error": "HTTP API disabled in app mode"})
            if not self._trusted():
                return self._send(403, {"error": "forbidden"})
            name = path[5:]
            fn = getattr(api, name, None)
            if name.startswith("_") or not callable(fn):
                return self._send(404, {"error": f"no method {name}"})
            length = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(length) or b"{}")
            try:
                result = fn(*body.get("args", []))
                self._send(200, {"result": result})
            except Exception as e:  # surface backend errors to the UI
                self._send(200, {"error": str(e)})

    return Handler


def serve(api, port=0, background=False):
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(api))
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    api._media_base = url.rstrip("/")
    if background:
        threading.Thread(target=server.serve_forever, daemon=True).start()
        return server, url
    print(f"LoRA Studio running at {url}")
    server.serve_forever()

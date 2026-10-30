"""The request handler every route group builds on: local-only requests, JSON and byte responses."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlsplit

DIST = (Path(__file__).resolve().parent.parent / "web" / "dist").resolve()
HOST = "127.0.0.1"
LOCAL_NAMES = {"127.0.0.1", "localhost", "::1"}
STATIC_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
    ".json": "application/json; charset=utf-8",
    ".woff2": "font/woff2",
    ".map": "application/json",
}
UI_MISSING = b"""<!doctype html>
<meta charset="utf-8">
<title>KALDR STUDIO</title>
<p>The studio UI is the Vite app. From the <code>web</code> folder, run <code>npm install</code> and <code>npm run dev</code>, then open http://127.0.0.1:5173.</p>
"""


def static_file(url_path: str) -> Path | None:
    if not DIST.is_dir():
        return None
    rel = "index.html" if url_path in {"/", "/index.html"} else url_path.lstrip("/")
    if not rel or "\\" in rel:
        return None
    candidate = (DIST / rel).resolve()
    if candidate != DIST and DIST not in candidate.parents:
        return None
    if candidate.is_file():
        return candidate
    return None


def local_name(value: str | None, url: bool = False) -> bool:
    """True when a Host header, or an Origin with url=True, points at this machine."""
    if not value:
        return False
    try:
        name = urlsplit(value if url else "//" + value).hostname
    except ValueError:
        return False
    return name in LOCAL_NAMES



class BaseHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args) -> None:
        print(f"[{self.address_string()}] {fmt % args}", flush=True)

    def parse_request(self) -> bool:
        """Refuse a request that names another host. Blocks DNS rebinding and cross-site posts."""
        if not super().parse_request():
            return False
        origin = self.headers.get("Origin")
        if local_name(self.headers.get("Host")) and (origin is None or local_name(origin, url=True)):
            return True
        self.close_connection = True
        self.send_error(403, "local requests only")
        return False

    def _json(self, code: int, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _bytes(self, code: int, body: bytes, content_type: str, cache: str, download: str | None = None) -> None:
        total = len(body)
        start = 0
        end = max(0, total - 1)
        status = code
        ranged = False
        header = self.headers.get("Range") if code == 200 and total and not download else None
        if header and header.startswith("bytes="):
            spec = header[6:].split(",", 1)[0].strip()
            left, sep, right = spec.partition("-")
            try:
                if sep != "-" or (left == "" and right == ""):
                    raise ValueError
                if left == "":
                    length = int(right)
                    if length <= 0:
                        raise ValueError
                    start = max(0, total - length)
                else:
                    start = int(left)
                    end = int(right) if right else total - 1
                if start < 0 or start >= total or end < start:
                    self.send_response(416)
                    self.send_header("Content-Range", f"bytes */{total}")
                    self.send_header("Accept-Ranges", "bytes")
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                end = min(end, total - 1)
                body = body[start:end + 1]
                status = 206
                ranged = True
            except ValueError:
                start, end = 0, total - 1
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", cache)
        if ranged:
            self.send_header("Content-Range", f"bytes {start}-{end}/{total}")
        if download:
            self.send_header("Content-Disposition", f'attachment; filename="{download}"')
        self.end_headers()
        self.wfile.write(body)

    def _json_body(self, limit: int = 16384) -> dict:
        length = int(self.headers.get("Content-Length") or "0")
        if length <= 0 or length > limit:
            raise ValueError("that request is empty")
        try:
            payload = json.loads(self.rfile.read(length))
        except json.JSONDecodeError as exc:
            raise ValueError("that request is empty") from exc
        if not isinstance(payload, dict):
            raise ValueError("that request is empty")
        return payload

    def _payload(self, limit: int = 8192) -> dict:
        length = int(self.headers.get("Content-Length") or "0")
        if length <= 0 or length > limit:
            raise ValueError("give an http or https image URL")
        try:
            payload = json.loads(self.rfile.read(length))
        except json.JSONDecodeError as e:
            raise ValueError("give an http or https image URL") from e
        if not isinstance(payload, dict):
            raise ValueError("give an http or https image URL")
        return payload

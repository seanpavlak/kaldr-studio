"""Local Kaldr Studio API. Sprites, and vocal-free music, on 127.0.0.1.

    .venv/bin/python -m app.server

The UI is the Vite app in web/. During development, `npm run dev` proxies
/jobs, /audio and /api here. A built web/dist is served from this process as well.

Listens on 127.0.0.1 only. Sprite redraws and loops share one lock,
because both are heavy on this Mac. Beep speech does not take that lock.

Routes live in route groups: routes_sprite (the studio's sprite page),
routes_audio (its music page) and routes_api (the public /api/v1).
"""

from __future__ import annotations

import argparse
from http.server import ThreadingHTTPServer
from urllib.parse import urlparse

from app.http_base import DIST, HOST, STATIC_TYPES, UI_MISSING, static_file
from app.routes_api import ApiRoutes
from app.routes_audio import AudioRoutes
from app.routes_sprite import SpriteRoutes
from app.sprite_jobs import JOBS

PAGES = {"/terms", "/privacy", "/batch", "/music", "/music/speech", "/music/batch", "/3d", "/3d/batch"}


class Handler(ApiRoutes, AudioRoutes, SpriteRoutes):
    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        parts = [p for p in path.split("/") if p]
        if parts and parts[0] == "audio":
            self._audio_get(parts)
            return
        if self.sprite_get(path, parts):
            return
        if path in PAGES and (DIST / "index.html").is_file():
            self._bytes(200, (DIST / "index.html").read_bytes(), "text/html; charset=utf-8", "no-cache")
            return
        page = static_file(path)
        if page is not None:
            cache = "public, max-age=31536000, immutable" if path.startswith("/assets/") else "no-cache"
            self._bytes(200, page.read_bytes(), STATIC_TYPES.get(page.suffix, "application/octet-stream"), cache)
            return
        if path in {"/", "/index.html"}:
            self._bytes(200, UI_MISSING, "text/html; charset=utf-8", "no-cache")
            return
        if "text/html" in self.headers.get("Accept", "") and (DIST / "index.html").is_file():
            # Browsers get the app's own 404 page; API callers still get JSON.
            self._bytes(404, (DIST / "index.html").read_bytes(), "text/html; charset=utf-8", "no-cache")
            return
        self._json(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        parts = [p for p in path.split("/") if p]
        if self.api_post(path) or self.audio_post(path) or self.sprite_post(path, parts):
            return
        self._json(404, {"error": "not found"})

    def do_PUT(self) -> None:  # noqa: N802
        if not self.key_put(urlparse(self.path).path):
            self._json(404, {"error": "not found"})

    def do_DELETE(self) -> None:  # noqa: N802
        if not self.key_delete(urlparse(self.path).path):
            self._json(404, {"error": "not found"})


def main() -> None:
    ap = argparse.ArgumentParser(description="Kaldr Studio local server")
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args()
    JOBS.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer((HOST, args.port), Handler)
    print(f"KALDR STUDIO API at http://{HOST}:{args.port}", flush=True)
    if (DIST / "index.html").is_file():
        print(f"Studio UI at http://{HOST}:{args.port}", flush=True)
    else:
        print("Studio UI: cd web && npm run dev  →  http://127.0.0.1:5173", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopping", flush=True)
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

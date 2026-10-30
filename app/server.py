"""Local Kaldr Studio API. Sprites, and vocal-free music, on 127.0.0.1.

    .venv/bin/python app/server.py

The UI is the Vite app in web/. During development, `npm run dev` proxies
/jobs and /audio here. A built web/dist is served from this process as well.

Listens on 127.0.0.1 only. Sprite redraws and loops share one lock,
because both are heavy on this Mac. Beep speech does not take that lock.
"""

from __future__ import annotations

import argparse
import io
import json
import queue
import re
import shutil
import threading
import uuid
import zipfile
from email.parser import BytesParser
from email.policy import HTTP
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse, urlsplit

import audio_jobs
import pipeline

HERE = Path(__file__).resolve().parent
DIST = (HERE.parent / "web" / "dist").resolve()
JOBS = pipeline.JOBS
HOST = "127.0.0.1"
LOCAL_NAMES = {"127.0.0.1", "localhost", "::1"}
SAFE_ID = re.compile(r"^[0-9a-f]{16}$")
FILES = {
    "reference.png": "image/png",
    "stylized.png": "image/png",
    "final.png": "image/png",
    "idle.png": "image/png",
    "idle.json": "application/json",
    "idle.gif": "image/gif",
}
FILE_KEYS = {name: key for key, name in {
    "reference": "reference.png",
    "stylized": "stylized.png",
    "final": "final.png",
    "idle": "idle.png",
    "idle_json": "idle.json",
    "gif": "idle.gif",
}.items()}
BUNDLE = (
    ("final.png", "sprite.png"),
    ("idle.png", "idle.png"),
    ("idle.json", "idle.json"),
    ("idle.gif", "idle.gif"),
)
PIPELINE_LOCK = threading.Lock()
BATCH_LOCK = threading.Lock()
MAX_BATCH = 20
BATCH_DIR = JOBS / "_batches"
_batch_queues: dict[str, queue.Queue] = {}
# Field names each /api route takes besides `file`. Built from the validators so they never drift.
API_SPRITE_FIELDS = {"url", "model", *pipeline.RENDER_SPEC}
API_LOOP_FIELDS = {"url", "rights", *audio_jobs.parse_settings(None)}
API_SPEECH_FIELDS = set(audio_jobs.parse_speak({"text": "-"}))
API_SLACK = 1024 * 1024  # multipart boundaries and headers on top of the file
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
UI_MISSING = """<!doctype html>
<meta charset="utf-8">
<title>KALDR STUDIO</title>
<p>The studio UI is the Vite app. From the <code>web</code> folder, run <code>npm install</code> and <code>npm run dev</code>, then open http://127.0.0.1:5173.</p>
""".encode()


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


def _check_url(url: object) -> str:
    if not isinstance(url, str):
        raise ValueError("give an http or https image URL")
    url = url.strip()
    parts = urlparse(url)
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        raise ValueError("give an http or https image URL")
    if len(url) > 2000:
        raise ValueError("that URL is too long")
    return url


def _files(job_id: str) -> dict[str, str]:
    work = JOBS / job_id
    out = {}
    for name, key in FILE_KEYS.items():
        path = work / name
        if path.is_file():
            # mtime keeps the page from showing a sprite it already cached after a re-render
            out[key] = f"/jobs/{job_id}/{name}?v={path.stat().st_mtime_ns}"
    return out


def write_status(job_id: str, url: str, status: str, stage: str, error: str | None,
                 render: dict | None = None, model: str | None = None) -> None:
    path = JOBS / job_id / "status.json"
    prior = {}
    if path.is_file():
        try:
            prior = json.loads(path.read_text())
        except json.JSONDecodeError:
            prior = {}
    if render is None:
        render = prior.get("render")
    if model is None:
        model = prior.get("model")
    payload = {
        "id": job_id,
        "url": url,
        "status": status,
        "stage": stage,
        "error": error,
        "model": model,
        "render": render,
        "files": _files(job_id),
    }
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n")
    tmp.replace(path)


def _read_status(job_id: str) -> dict:
    return json.loads((JOBS / job_id / "status.json").read_text())


def _fail(job_id: str, url: str, exc: Exception, render: dict | None) -> None:
    stage = _read_status(job_id).get("stage") or "download"
    message = str(exc) if isinstance(exc, RuntimeError) and str(exc) else f"{type(exc).__name__}: {exc}"
    write_status(job_id, url, "error", stage, message, render)
    print(f"[{job_id}] error during {stage}: {message}", flush=True)


def _worker(job_id: str, url: str, render: dict, model: str, local: bool = False) -> None:
    def on_stage(stage: str) -> None:
        write_status(job_id, url, "running", stage, None, render, model)
        print(f"[{job_id}] {stage}", flush=True)

    with PIPELINE_LOCK:
        try:
            pipeline.run(url, JOBS / job_id, job_id, on_stage, render=render, model=model, local=local)
        except Exception as e:  # noqa: BLE001
            _fail(job_id, url, e, render)
            return
        write_status(job_id, url, "done", "done", None, render, model)
        print(f"[{job_id}] done", flush=True)


def _rerender(job_id: str, render: dict) -> None:
    url = _read_status(job_id)["url"]

    def on_stage(stage: str) -> None:
        write_status(job_id, url, "running", stage, None, render)
        print(f"[{job_id}] {stage}", flush=True)

    with PIPELINE_LOCK:
        try:
            pipeline.render_final(JOBS / job_id, job_id, render, on_stage)
        except Exception as e:  # noqa: BLE001
            _fail(job_id, url, e, render)
            return
        write_status(job_id, url, "done", "done", None, render)
        print(f"[{job_id}] done", flush=True)


def _new_job(url: str, render: dict, model: str) -> str:
    job_id = uuid.uuid4().hex[:16]
    (JOBS / job_id).mkdir(parents=True)
    write_status(job_id, url, "running", "queued", None, render, model)
    return job_id


def start_job(url: str, render: dict, model: str) -> str:
    job_id = _new_job(url, render, model)
    threading.Thread(target=_worker, args=(job_id, url, render, model), daemon=True).start()
    return job_id


def start_file_job(data: bytes, name: str, render: dict, model: str) -> str:
    job_id = uuid.uuid4().hex[:16]
    work = JOBS / job_id
    work.mkdir(parents=True)
    try:
        pipeline.save_image_bytes(data, work / "reference.png", bad="that file is not an image")
    except RuntimeError:
        shutil.rmtree(work, ignore_errors=True)
        raise
    write_status(job_id, name, "running", "redraw", None, render, model)
    threading.Thread(target=_worker, args=(job_id, name, render, model, True), daemon=True).start()
    return job_id


def _form_value(value: object, kind: str) -> object:
    """A form field arrives as text. Give it the type a JSON caller would send."""
    if not isinstance(value, str):
        return value
    text = value.strip().lower()
    if kind == "bool":
        if text in {"true", "1", "yes", "on"}:
            return True
        if text in {"false", "0", "no", "off"}:
            return False
        return value
    try:
        number = float(text)
    except ValueError:
        return value
    return int(number) if number.is_integer() else number


def _one_source(fields: dict, upload: tuple[bytes, str] | None) -> None:
    has_url = bool(fields.get("url"))
    if upload is not None and has_url:
        raise ValueError("send a file or a url, not both")
    if upload is None and not has_url:
        raise ValueError("send a file or a url")


def _batch_path(batch_id: str) -> Path:
    return BATCH_DIR / batch_id / "batch.json"


def _read_batch(batch_id: str) -> dict:
    return json.loads(_batch_path(batch_id).read_text())


def _write_batch(batch: dict) -> None:
    path = _batch_path(batch["id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(batch, indent=2) + "\n")
    tmp.replace(path)


def _batch_view(batch_id: str) -> dict:
    batch = _read_batch(batch_id)
    items = []
    for item in batch["items"]:
        job_id = item["job_id"]
        status_path = JOBS / job_id / "status.json"
        job = _read_status(job_id) if status_path.is_file() else None
        items.append({**item, "job": job})
    return {**batch, "items": items}


def _queue_for(batch_id: str) -> queue.Queue:
    found = _batch_queues.get(batch_id)
    if found is not None:
        return found
    found = queue.Queue()
    _batch_queues[batch_id] = found
    threading.Thread(target=_batch_runner, args=(batch_id, found), daemon=True).start()
    return found


def _batch_runner(batch_id: str, jobs: queue.Queue) -> None:
    while True:
        item = jobs.get()
        if item is None:
            return
        job_id, url, render, model, local = item
        _worker(job_id, url, render, model, local)


def _item_name(raw: str) -> str:
    return _dropped_name(raw)[:80]


def _append_job(batch_id: str, url: str, model: str, render: dict, local: bool, name: str,
                image: bytes | None = None) -> str:
    with BATCH_LOCK:
        if not _batch_path(batch_id).is_file():
            raise ValueError("no such batch")
        batch = _read_batch(batch_id)
        if len(batch["items"]) >= MAX_BATCH:
            raise ValueError("a batch can hold 20 images")
        job_id = _new_job(url, render, model)
        if image is not None:
            try:
                pipeline.save_image_bytes(image, JOBS / job_id / "reference.png", bad="that file is not an image")
            except RuntimeError:
                shutil.rmtree(JOBS / job_id, ignore_errors=True)
                raise
        batch["items"].append({"job_id": job_id, "name": name})
        _write_batch(batch)
        _queue_for(batch_id).put((job_id, url, render, model, local))
    return job_id


def create_batch(model: str, render: dict, urls: list[str]) -> str:
    checked = [_check_url(url) for url in urls]
    if len(checked) > MAX_BATCH:
        raise ValueError("a batch can hold 20 images")
    batch_id = uuid.uuid4().hex[:16]
    _write_batch({"id": batch_id, "model": model, "render": render, "items": []})
    for url in checked:
        _append_job(batch_id, url, model, render, False, _item_name(urlparse(url).path))
    return batch_id


def _safe_folder(name: str, used: set[str]) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip(".-")[:80] or "sprite"
    base = cleaned
    number = 2
    while cleaned.lower() in used:
        cleaned = f"{base}-{number}"
        number += 1
    used.add(cleaned.lower())
    return cleaned


def _batch_bundle(batch_id: str) -> bytes | None:
    if not _batch_path(batch_id).is_file():
        return None
    batch = _read_batch(batch_id)
    buf = io.BytesIO()
    used: set[str] = set()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        packed = 0
        for item in batch["items"]:
            job_id = item["job_id"]
            status_path = JOBS / job_id / "status.json"
            if not status_path.is_file() or _read_status(job_id).get("status") != "done":
                continue
            folder = _safe_folder(str(item.get("name") or "sprite"), used)
            for source, name in BUNDLE:
                path = JOBS / job_id / source
                if not path.is_file():
                    continue
                archive.write(path, f"{folder}/{name}")
                packed += 1
    if packed == 0:
        return None
    return buf.getvalue()


def start_redraw(job_id: str, render: dict, model: str) -> None:
    status = _read_status(job_id)
    url = status["url"]
    local = (JOBS / job_id / "reference.png").is_file()
    if not local and not (isinstance(url, str) and url.startswith(("http://", "https://"))):
        raise ValueError("that image is no longer available")
    write_status(job_id, url, "running", "queued", None, render, model)
    threading.Thread(target=_worker, args=(job_id, url, render, model, local), daemon=True).start()


def _dropped_name(header: str | None) -> str:
    name = unquote(header or "").replace("\\", "/").split("/")[-1].strip()
    name = re.sub(r"[\x00-\x1f]", "", name)[:180]
    return name or "dropped image"


def _bundle(job_id: str) -> bytes | None:
    work = JOBS / job_id
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        packed = 0
        for source, name in BUNDLE:
            path = work / source
            if not path.is_file():
                continue
            archive.write(path, name)
            packed += 1
    if packed == 0:
        return None
    return buf.getvalue()


def latest_job_id() -> str | None:
    found = []
    if not JOBS.is_dir():
        return None
    for path in JOBS.iterdir():
        status = path / "status.json"
        if SAFE_ID.match(path.name) and status.is_file():
            found.append((status.stat().st_mtime, path.name))
    if not found:
        return None
    return max(found)[1]


def _local_name(value: str | None, url: bool = False) -> bool:
    """True when a Host header, or an Origin with url=True, points at this machine."""
    if not value:
        return False
    try:
        name = urlsplit(value if url else "//" + value).hostname
    except ValueError:
        return False
    return name in LOCAL_NAMES


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args) -> None:
        print(f"[{self.address_string()}] {fmt % args}", flush=True)

    def parse_request(self) -> bool:
        """Refuse a request that names another host. Blocks DNS rebinding and cross-site posts."""
        if not super().parse_request():
            return False
        origin = self.headers.get("Origin")
        if _local_name(self.headers.get("Host")) and (origin is None or _local_name(origin, url=True)):
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

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        parts = [p for p in path.split("/") if p]
        if path == "/models":
            self._json(200, {"default": pipeline.DEFAULT_MODEL, "models": pipeline.list_models()})
            return
        if path == "/openrouter-key":
            hint = pipeline.openrouter_key_hint()
            self._json(200, {"saved": bool(hint), "hint": hint})
            return
        if parts and parts[0] == "audio":
            self._audio_get(parts)
            return
        if path == "/openrouter-key/limit":
            budget = pipeline.openrouter_key_budget() if pipeline.openrouter_key_saved() else {"limited": None, "remaining": None}
            self._json(200, budget)
            return
        if len(parts) == 2 and parts == ["jobs", "latest"]:
            job_id = latest_job_id()
            if job_id is None:
                self._json(404, {"error": "no jobs yet"})
                return
            self._json(200, _read_status(job_id))
            return
        if len(parts) == 2 and parts[0] == "jobs" and SAFE_ID.match(parts[1]):
            status_path = JOBS / parts[1] / "status.json"
            if not status_path.is_file():
                self._json(404, {"error": "no such job"})
                return
            self._json(200, _read_status(parts[1]))
            return
        if len(parts) == 3 and parts[0] == "jobs" and SAFE_ID.match(parts[1]) and parts[2] == "sprite.zip":
            body = _bundle(parts[1])
            if body is None:
                self._json(404, {"error": "that file is not ready"})
                return
            self._bytes(200, body, "application/zip", "no-cache", "sprite.zip")
            return
        if len(parts) == 3 and parts[0] == "jobs" and SAFE_ID.match(parts[1]) and parts[2] in FILES:
            file_path = JOBS / parts[1] / parts[2]
            if not file_path.is_file():
                self._json(404, {"error": "that file is not ready"})
                return
            self._bytes(200, file_path.read_bytes(), FILES[parts[2]], "no-cache")
            return
        if len(parts) == 2 and parts[0] == "batches" and SAFE_ID.match(parts[1]):
            if not _batch_path(parts[1]).is_file():
                self._json(404, {"error": "no such batch"})
                return
            self._json(200, _batch_view(parts[1]))
            return
        if len(parts) == 3 and parts[0] == "batches" and SAFE_ID.match(parts[1]) and parts[2] == "sprites.zip":
            body = _batch_bundle(parts[1])
            if body is None:
                self._json(404, {"error": "that file is not ready"})
                return
            self._bytes(200, body, "application/zip", "no-cache", "sprites.zip")
            return
        if path in {"/terms", "/privacy", "/batch", "/music", "/music/speech", "/music/batch", "/3d", "/3d/batch"} and (DIST / "index.html").is_file():
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

    def _audio_get(self, parts: list[str]) -> None:
        if len(parts) == 2 and parts[1] == "score":
            self._json(404, {"error": "not found"})
            return
        if len(parts) == 3 and parts[1] == "score" and parts[2] == "latest":
            viewed = audio_jobs.latest_done()
            if viewed is None:
                self._json(404, {"error": "no such loop"})
                return
            self._json(200, viewed)
            return
        if len(parts) == 3 and parts[1] == "score" and SAFE_ID.match(parts[2]):
            viewed = audio_jobs.view(parts[2])
            if viewed is None:
                self._json(404, {"error": "no such loop"})
                return
            self._json(200, viewed)
            return
        if len(parts) == 4 and parts[1] == "score" and SAFE_ID.match(parts[2]):
            packed = audio_jobs.file_bytes(parts[2], parts[3])
            if packed is None:
                self._json(404, {"error": "that file is not ready"})
                return
            body, content_type, download = packed
            self._bytes(200, body, content_type, "no-store", download)
            return
        self._json(404, {"error": "not found"})

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

    def _audio_settings(self) -> dict:
        raw = self.headers.get("X-Audio-Settings") or "{}"
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError("loop settings must be an object") from exc
        return audio_jobs.parse_settings(payload)

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

    def _file_job(self) -> None:
        length = int(self.headers.get("Content-Length") or "0")
        if length <= 0:
            self._json(400, {"error": "that file is not an image"})
            return
        if length > pipeline.MAX_BYTES:
            self._json(400, {"error": "that image is larger than 20 MB"})
            return
        try:
            render = pipeline.parse_render(json.loads(self.headers.get("X-Sprite-Render") or "null"))
            model = pipeline.parse_model(self.headers.get("X-Sprite-Model"))
        except (ValueError, json.JSONDecodeError) as e:
            message = str(e) if isinstance(e, ValueError) else "render settings must be an object"
            self._json(400, {"error": message})
            return
        data = self.rfile.read(length)
        name = _dropped_name(self.headers.get("X-Sprite-Name"))
        try:
            job_id = start_file_job(data, name, render, model)
        except RuntimeError as e:
            self._json(400, {"error": str(e)})
            return
        self._json(202, _read_status(job_id))

    def _api_form(self, allowed: set[str], limit: int) -> tuple[dict, tuple[bytes, str] | None]:
        """Fields and the optional `file` part of a multipart or JSON /api request."""
        length = int(self.headers.get("Content-Length") or "0")
        if length <= 0:
            raise ValueError("that request is empty")
        if length > limit:
            # The body stays unread, so this connection cannot carry another request.
            self.close_connection = True
            raise ValueError("that request is too large")
        body = self.rfile.read(length)
        kind = self.headers.get_content_type()
        fields: dict = {}
        upload = None
        if kind == "application/json":
            try:
                fields = json.loads(body)
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                raise ValueError("that request is not valid JSON") from e
            if not isinstance(fields, dict):
                raise ValueError("send a JSON object")
        elif kind == "multipart/form-data":
            head = f"Content-Type: {self.headers['Content-Type']}\r\n\r\n".encode()
            message = BytesParser(policy=HTTP).parsebytes(head + body)
            if not message.is_multipart():
                raise ValueError("that form could not be read")
            for part in message.iter_parts():
                name = part.get_param("name", header="content-disposition")
                data = part.get_payload(decode=True) or b""
                if name == "file":
                    upload = (data, part.get_filename() or "")
                elif name and data:
                    fields[name] = data.decode("utf-8", errors="replace")
        else:
            raise ValueError("send multipart/form-data or application/json")
        unknown = set(fields) - allowed
        if unknown:
            raise ValueError("unknown field: " + ", ".join(sorted(unknown)))
        return fields, upload

    def _api_sprite(self) -> None:
        try:
            fields, upload = self._api_form(API_SPRITE_FIELDS, pipeline.MAX_BYTES + API_SLACK)
            _one_source(fields, upload)
            model = pipeline.parse_model(fields.get("model"))
            render = pipeline.parse_render({
                name: _form_value(fields[name], spec["type"])
                for name, spec in pipeline.RENDER_SPEC.items() if name in fields
            })
            if upload is None:
                job_id = start_job(_check_url(fields["url"]), render, model)
            else:
                data, filename = upload
                if len(data) > pipeline.MAX_BYTES:
                    raise ValueError("that image is larger than 20 MB")
                job_id = start_file_job(data, _dropped_name(filename), render, model)
        except (ValueError, RuntimeError) as e:
            self._json(400, {"error": str(e)})
            return
        self._json(202, _read_status(job_id))

    def _api_loop(self) -> None:
        try:
            fields, upload = self._api_form(API_LOOP_FIELDS, audio_jobs.MAX_BYTES + API_SLACK)
            _one_source(fields, upload)
            if _form_value(fields.get("rights"), "bool") is not True:
                raise ValueError(audio_jobs.RIGHTS_ERROR)
            settings = {name: value for name, value in fields.items() if name not in {"url", "rights"}}
            if "classic" in settings:
                settings["classic"] = _form_value(settings["classic"], "bool")
                if not isinstance(settings["classic"], bool):
                    raise ValueError("classic must be true or false")
            if upload is None:
                viewed = audio_jobs.begin_url(fields["url"], settings, PIPELINE_LOCK)
            else:
                viewed = audio_jobs.begin_file(upload[0], upload[1], settings, PIPELINE_LOCK)
        except ValueError as exc:
            self._json(400, {"error": str(exc)})
            return
        self._json(202, viewed)

    def _api_speech(self) -> None:
        try:
            fields, upload = self._api_form(API_SPEECH_FIELDS, 16384)
            if upload is not None:
                raise ValueError("speech takes text, not a file")
            body = audio_jobs.speech_wav(fields)
        except ValueError as exc:
            self._json(400, {"error": str(exc)})
            return
        except Exception:
            self._json(500, {"error": "could not speak that line"})
            return
        self._bytes(200, body, "audio/wav", "no-store")

    def _key_body(self) -> str:
        length = int(self.headers.get("Content-Length") or "0")
        if length <= 0 or length > 2048:
            raise ValueError("add your OpenRouter key")
        try:
            payload = json.loads(self.rfile.read(length))
        except json.JSONDecodeError as e:
            raise ValueError("add your OpenRouter key") from e
        if not isinstance(payload, dict) or not isinstance(payload.get("key"), str):
            raise ValueError("add your OpenRouter key")
        return payload["key"]

    def do_PUT(self) -> None:  # noqa: N802
        if urlparse(self.path).path != "/openrouter-key":
            self._json(404, {"error": "not found"})
            return
        try:
            pipeline.save_openrouter_key(self._key_body())
        except ValueError as e:
            self._json(400, {"error": str(e)})
            return
        hint = pipeline.openrouter_key_hint()
        self._json(200, {"saved": bool(hint), "hint": hint, "limited": pipeline.openrouter_key_limited()})

    def do_DELETE(self) -> None:  # noqa: N802
        if urlparse(self.path).path != "/openrouter-key":
            self._json(404, {"error": "not found"})
            return
        pipeline.clear_openrouter_key()
        self._json(200, {"saved": False})

    def _create_batch(self) -> None:
        try:
            payload = self._payload(65536)
            render = pipeline.parse_render(payload.get("render"))
            model = pipeline.parse_model(payload.get("model"))
            raw_urls = payload.get("urls") or []
            if not isinstance(raw_urls, list) or any(not isinstance(item, str) for item in raw_urls):
                raise ValueError("give an http or https image URL")
            batch_id = create_batch(model, render, raw_urls)
        except (ValueError, AttributeError) as e:
            message = str(e) if isinstance(e, ValueError) else "give an http or https image URL"
            self._json(400, {"error": message})
            return
        self._json(202, _batch_view(batch_id))

    def _batch_url(self, batch_id: str) -> None:
        if not _batch_path(batch_id).is_file():
            self._json(404, {"error": "no such batch"})
            return
        try:
            payload = self._payload()
            url = _check_url(payload.get("url"))
            batch = _read_batch(batch_id)
            _append_job(batch_id, url, batch["model"], batch["render"], False, _item_name(urlparse(url).path))
        except (ValueError, AttributeError) as e:
            message = str(e) if isinstance(e, ValueError) else "give an http or https image URL"
            self._json(400, {"error": message})
            return
        self._json(202, _batch_view(batch_id))

    def _batch_file(self, batch_id: str) -> None:
        if not _batch_path(batch_id).is_file():
            self._json(404, {"error": "no such batch"})
            return
        length = int(self.headers.get("Content-Length") or "0")
        if length <= 0:
            self._json(400, {"error": "that file is not an image"})
            return
        if length > pipeline.MAX_BYTES:
            self._json(400, {"error": "that image is larger than 20 MB"})
            return
        batch = _read_batch(batch_id)
        if len(batch["items"]) >= MAX_BATCH:
            self._json(400, {"error": "a batch can hold 20 images"})
            return
        data = self.rfile.read(length)
        name = _item_name(_dropped_name(self.headers.get("X-Sprite-Name")))
        try:
            _append_job(batch_id, name, batch["model"], batch["render"], True, name, image=data)
        except ValueError as e:
            self._json(400, {"error": str(e)})
            return
        except RuntimeError as e:
            self._json(400, {"error": str(e)})
            return
        self._json(202, _batch_view(batch_id))

    def _job_redraw(self, job_id: str) -> None:
        if not (JOBS / job_id / "status.json").is_file():
            self._json(404, {"error": "no such job"})
            return
        try:
            payload = self._payload()
            render = pipeline.parse_render(payload.get("render"))
            model = pipeline.parse_model(payload.get("model"))
            start_redraw(job_id, render, model)
        except (ValueError, AttributeError) as e:
            message = str(e) if isinstance(e, ValueError) else "pick a model from the list"
            self._json(400, {"error": message})
            return
        self._json(202, _read_status(job_id))

    def _audio_speak(self) -> None:
        try:
            body = audio_jobs.speech_wav(self._json_body())
        except ValueError as exc:
            self._json(400, {"error": str(exc)})
            return
        except Exception:
            self._json(500, {"error": "could not speak that line"})
            return
        self._bytes(200, body, "audio/wav", "no-store")

    def _audio_score_url(self) -> None:
        try:
            payload = self._json_body()
            if payload.get("rights") is not True:
                raise ValueError(audio_jobs.RIGHTS_ERROR)
            viewed = audio_jobs.begin_url(payload.get("url"), payload.get("settings"), PIPELINE_LOCK)
        except ValueError as exc:
            self._json(400, {"error": str(exc)})
            return
        self._json(202, viewed)

    def _audio_score_file(self) -> None:
        length = int(self.headers.get("Content-Length") or "0")
        if length <= 0:
            self._json(400, {"error": "that file is empty"})
            return
        if length > audio_jobs.MAX_BYTES:
            self._json(400, {"error": "that file is larger than 80 MB"})
            return
        try:
            if self.headers.get("X-Audio-Rights") != "confirmed":
                raise ValueError(audio_jobs.RIGHTS_ERROR)
            settings = self._audio_settings()
        except ValueError as exc:
            self.rfile.read(length)
            self._json(400, {"error": str(exc)})
            return
        data = self.rfile.read(length)
        name = unquote(self.headers.get("X-Audio-Name") or "score")
        try:
            viewed = audio_jobs.begin_file(data, name, settings, PIPELINE_LOCK)
        except ValueError as exc:
            self._json(400, {"error": str(exc)})
            return
        self._json(202, viewed)

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/api/v1/sprite":
            self._api_sprite()
            return
        if path == "/api/v1/loop":
            self._api_loop()
            return
        if path == "/api/v1/speech":
            self._api_speech()
            return
        if path == "/audio/speech":
            self._audio_speak()
            return
        if path == "/audio/score":
            self._audio_score_url()
            return
        if path == "/audio/score/file":
            self._audio_score_file()
            return
        if path == "/jobs/file":
            self._file_job()
            return
        parts = [p for p in path.split("/") if p]
        if path == "/batches":
            self._create_batch()
            return
        if len(parts) == 3 and parts[0] == "batches" and SAFE_ID.match(parts[1]) and parts[2] == "url":
            self._batch_url(parts[1])
            return
        if len(parts) == 3 and parts[0] == "batches" and SAFE_ID.match(parts[1]) and parts[2] == "file":
            self._batch_file(parts[1])
            return
        if len(parts) == 3 and parts[0] == "jobs" and SAFE_ID.match(parts[1]) and parts[2] == "redraw":
            self._job_redraw(parts[1])
            return
        rerender = len(parts) == 3 and parts[0] == "jobs" and parts[2] == "render" and SAFE_ID.match(parts[1])
        if path != "/jobs" and not rerender:
            self._json(404, {"error": "not found"})
            return
        try:
            payload = self._payload()
            render = pipeline.parse_render(payload.get("render"))
            model = pipeline.parse_model(payload.get("model")) if not rerender else None
            if rerender:
                if not (JOBS / parts[1] / "status.json").is_file():
                    self._json(404, {"error": "no such job"})
                    return
                if not (JOBS / parts[1] / "stylized.png").is_file():
                    self._json(400, {"error": "redraw this image before updating the sprite"})
                    return
                url = _read_status(parts[1])["url"]
                write_status(parts[1], url, "running", "pixelate", None, render)
                threading.Thread(target=_rerender, args=(parts[1], render), daemon=True).start()
                self._json(202, _read_status(parts[1]))
                return
            url = _check_url(payload.get("url"))
        except (ValueError, AttributeError) as e:
            message = str(e) if isinstance(e, ValueError) else "give an http or https image URL"
            self._json(400, {"error": message})
            return
        job_id = start_job(url, render, model)
        self._json(202, _read_status(job_id))


def main() -> None:
    ap = argparse.ArgumentParser(description="Local sprite studio")
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

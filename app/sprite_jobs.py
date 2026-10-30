"""Sprite jobs and batches. Each job is a folder under studio_jobs/ with a status.json."""

from __future__ import annotations

import io
import json
import queue
import re
import shutil
import threading
import uuid
import zipfile
from pathlib import Path
from urllib.parse import unquote, urlparse

from app import pipeline

JOBS = pipeline.JOBS
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
# Sprite redraws and loops share this lock, because both are heavy on this Mac.
PIPELINE_LOCK = threading.Lock()
BATCH_LOCK = threading.Lock()
MAX_BATCH = 20
BATCH_DIR = JOBS / "_batches"
_batch_queues: dict[str, queue.Queue] = {}


def check_url(url: object) -> str:
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


def read_status(job_id: str) -> dict:
    return json.loads((JOBS / job_id / "status.json").read_text())


def _fail(job_id: str, url: str, exc: Exception, render: dict | None) -> None:
    stage = read_status(job_id).get("stage") or "download"
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
    url = read_status(job_id)["url"]

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



def start_rerender(job_id: str, render: dict) -> None:
    url = read_status(job_id)["url"]
    write_status(job_id, url, "running", "pixelate", None, render)
    threading.Thread(target=_rerender, args=(job_id, render), daemon=True).start()


def batch_path(batch_id: str) -> Path:
    return BATCH_DIR / batch_id / "batch.json"


def read_batch(batch_id: str) -> dict:
    return json.loads(batch_path(batch_id).read_text())


def _write_batch(batch: dict) -> None:
    path = batch_path(batch["id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(batch, indent=2) + "\n")
    tmp.replace(path)


def batch_view(batch_id: str) -> dict:
    batch = read_batch(batch_id)
    items = []
    for item in batch["items"]:
        job_id = item["job_id"]
        status_path = JOBS / job_id / "status.json"
        job = read_status(job_id) if status_path.is_file() else None
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


def item_name(raw: str) -> str:
    return dropped_name(raw)[:80]


def append_job(batch_id: str, url: str, model: str, render: dict, local: bool, name: str,
                image: bytes | None = None) -> str:
    with BATCH_LOCK:
        if not batch_path(batch_id).is_file():
            raise ValueError("no such batch")
        batch = read_batch(batch_id)
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
    checked = [check_url(url) for url in urls]
    if len(checked) > MAX_BATCH:
        raise ValueError("a batch can hold 20 images")
    batch_id = uuid.uuid4().hex[:16]
    _write_batch({"id": batch_id, "model": model, "render": render, "items": []})
    for url in checked:
        append_job(batch_id, url, model, render, False, item_name(urlparse(url).path))
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


def batch_bundle(batch_id: str) -> bytes | None:
    if not batch_path(batch_id).is_file():
        return None
    batch = read_batch(batch_id)
    buf = io.BytesIO()
    used: set[str] = set()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        packed = 0
        for item in batch["items"]:
            job_id = item["job_id"]
            status_path = JOBS / job_id / "status.json"
            if not status_path.is_file() or read_status(job_id).get("status") != "done":
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
    status = read_status(job_id)
    url = status["url"]
    local = (JOBS / job_id / "reference.png").is_file()
    if not local and not (isinstance(url, str) and url.startswith(("http://", "https://"))):
        raise ValueError("that image is no longer available")
    write_status(job_id, url, "running", "queued", None, render, model)
    threading.Thread(target=_worker, args=(job_id, url, render, model, local), daemon=True).start()


def dropped_name(header: str | None) -> str:
    name = unquote(header or "").replace("\\", "/").split("/")[-1].strip()
    name = re.sub(r"[\x00-\x1f]", "", name)[:180]
    return name or "dropped image"


def bundle(job_id: str) -> bytes | None:
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


"""Sprite routes: single jobs, batches and the OpenRouter key, as the studio page calls them."""

from __future__ import annotations

import json
from urllib.parse import urlparse

from app import pipeline
from app.http_base import BaseHandler
from app.sprite_jobs import (
    FILES,
    JOBS,
    MAX_BATCH,
    SAFE_ID,
    append_job,
    batch_bundle,
    batch_path,
    batch_view,
    bundle,
    check_url,
    create_batch,
    dropped_name,
    item_name,
    latest_job_id,
    read_batch,
    read_status,
    start_file_job,
    start_job,
    start_redraw,
    start_rerender,
)


class SpriteRoutes(BaseHandler):
    def sprite_get(self, path: str, parts: list[str]) -> bool:
        if path == "/models":
            self._json(200, {"default": pipeline.DEFAULT_MODEL, "models": pipeline.list_models()})
            return True
        if path == "/openrouter-key":
            hint = pipeline.openrouter_key_hint()
            self._json(200, {"saved": bool(hint), "hint": hint})
            return True
        if path == "/openrouter-key/limit":
            budget = pipeline.openrouter_key_budget() if pipeline.openrouter_key_saved() else {"limited": None, "remaining": None}
            self._json(200, budget)
            return True
        if len(parts) == 2 and parts == ["jobs", "latest"]:
            job_id = latest_job_id()
            if job_id is None:
                self._json(404, {"error": "no jobs yet"})
                return True
            self._json(200, read_status(job_id))
            return True
        if len(parts) == 2 and parts[0] == "jobs" and SAFE_ID.match(parts[1]):
            status_path = JOBS / parts[1] / "status.json"
            if not status_path.is_file():
                self._json(404, {"error": "no such job"})
                return True
            self._json(200, read_status(parts[1]))
            return True
        if len(parts) == 3 and parts[0] == "jobs" and SAFE_ID.match(parts[1]) and parts[2] == "sprite.zip":
            body = bundle(parts[1])
            if body is None:
                self._json(404, {"error": "that file is not ready"})
                return True
            self._bytes(200, body, "application/zip", "no-cache", "sprite.zip")
            return True
        if len(parts) == 3 and parts[0] == "jobs" and SAFE_ID.match(parts[1]) and parts[2] in FILES:
            file_path = JOBS / parts[1] / parts[2]
            if not file_path.is_file():
                self._json(404, {"error": "that file is not ready"})
                return True
            self._bytes(200, file_path.read_bytes(), FILES[parts[2]], "no-cache")
            return True
        if len(parts) == 2 and parts[0] == "batches" and SAFE_ID.match(parts[1]):
            if not batch_path(parts[1]).is_file():
                self._json(404, {"error": "no such batch"})
                return True
            self._json(200, batch_view(parts[1]))
            return True
        if len(parts) == 3 and parts[0] == "batches" and SAFE_ID.match(parts[1]) and parts[2] == "sprites.zip":
            body = batch_bundle(parts[1])
            if body is None:
                self._json(404, {"error": "that file is not ready"})
                return True
            self._bytes(200, body, "application/zip", "no-cache", "sprites.zip")
            return True
        return False

    def sprite_post(self, path: str, parts: list[str]) -> bool:
        if path == "/jobs/file":
            self._file_job()
            return True
        if path == "/batches":
            self._create_batch()
            return True
        if len(parts) == 3 and parts[0] == "batches" and SAFE_ID.match(parts[1]) and parts[2] == "url":
            self._batch_url(parts[1])
            return True
        if len(parts) == 3 and parts[0] == "batches" and SAFE_ID.match(parts[1]) and parts[2] == "file":
            self._batch_file(parts[1])
            return True
        if len(parts) == 3 and parts[0] == "jobs" and SAFE_ID.match(parts[1]) and parts[2] == "redraw":
            self._job_redraw(parts[1])
            return True
        if len(parts) == 3 and parts[0] == "jobs" and SAFE_ID.match(parts[1]) and parts[2] == "render":
            self._job_render(parts[1])
            return True
        if path == "/jobs":
            self._job_create()
            return True
        return False

    def key_put(self, path: str) -> bool:
        if path != "/openrouter-key":
            return False
        try:
            pipeline.save_openrouter_key(self._key_body())
        except ValueError as e:
            self._json(400, {"error": str(e)})
            return True
        hint = pipeline.openrouter_key_hint()
        self._json(200, {"saved": bool(hint), "hint": hint, "limited": pipeline.openrouter_key_limited()})
        return True

    def key_delete(self, path: str) -> bool:
        if path != "/openrouter-key":
            return False
        pipeline.clear_openrouter_key()
        self._json(200, {"saved": False})
        return True

    def _job_create(self) -> None:
        try:
            payload = self._payload()
            render = pipeline.parse_render(payload.get("render"))
            model = pipeline.parse_model(payload.get("model"))
            url = check_url(payload.get("url"))
        except (ValueError, AttributeError) as e:
            message = str(e) if isinstance(e, ValueError) else "give an http or https image URL"
            self._json(400, {"error": message})
            return
        job_id = start_job(url, render, model)
        self._json(202, read_status(job_id))

    def _job_render(self, job_id: str) -> None:
        try:
            payload = self._payload()
            render = pipeline.parse_render(payload.get("render"))
        except (ValueError, AttributeError) as e:
            message = str(e) if isinstance(e, ValueError) else "give an http or https image URL"
            self._json(400, {"error": message})
            return
        if not (JOBS / job_id / "status.json").is_file():
            self._json(404, {"error": "no such job"})
            return
        if not (JOBS / job_id / "stylized.png").is_file():
            self._json(400, {"error": "redraw this image before updating the sprite"})
            return
        start_rerender(job_id, render)
        self._json(202, read_status(job_id))

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
        name = dropped_name(self.headers.get("X-Sprite-Name"))
        try:
            job_id = start_file_job(data, name, render, model)
        except RuntimeError as e:
            self._json(400, {"error": str(e)})
            return
        self._json(202, read_status(job_id))

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
        self._json(202, batch_view(batch_id))

    def _batch_url(self, batch_id: str) -> None:
        if not batch_path(batch_id).is_file():
            self._json(404, {"error": "no such batch"})
            return
        try:
            payload = self._payload()
            url = check_url(payload.get("url"))
            batch = read_batch(batch_id)
            append_job(batch_id, url, batch["model"], batch["render"], False, item_name(urlparse(url).path))
        except (ValueError, AttributeError) as e:
            message = str(e) if isinstance(e, ValueError) else "give an http or https image URL"
            self._json(400, {"error": message})
            return
        self._json(202, batch_view(batch_id))

    def _batch_file(self, batch_id: str) -> None:
        if not batch_path(batch_id).is_file():
            self._json(404, {"error": "no such batch"})
            return
        length = int(self.headers.get("Content-Length") or "0")
        if length <= 0:
            self._json(400, {"error": "that file is not an image"})
            return
        if length > pipeline.MAX_BYTES:
            self._json(400, {"error": "that image is larger than 20 MB"})
            return
        batch = read_batch(batch_id)
        if len(batch["items"]) >= MAX_BATCH:
            self._json(400, {"error": "a batch can hold 20 images"})
            return
        data = self.rfile.read(length)
        name = item_name(dropped_name(self.headers.get("X-Sprite-Name")))
        try:
            append_job(batch_id, name, batch["model"], batch["render"], True, name, image=data)
        except ValueError as e:
            self._json(400, {"error": str(e)})
            return
        except RuntimeError as e:
            self._json(400, {"error": str(e)})
            return
        self._json(202, batch_view(batch_id))

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
        self._json(202, read_status(job_id))

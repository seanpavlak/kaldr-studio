"""A live server on a free port. Job starters are stubbed, so no test spends OpenRouter credit or runs Demucs."""

from __future__ import annotations

import http.client
import json
import threading
import uuid
from http.server import ThreadingHTTPServer

import pytest

from app import audio_jobs, routes_api, routes_sprite
from app.server import Handler

JOB_ID = "0123456789abcdef"


class Client:
    def __init__(self, port: int) -> None:
        self.port = port

    def request(self, method: str, path: str, body: bytes | None = None, headers: dict | None = None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=30)
        conn.request(method, path, body=body, headers=headers or {})
        res = conn.getresponse()
        data = res.read()
        conn.close()
        return res.status, res.getheader("Content-Type") or "", data

    def json(self, method: str, path: str, payload, headers: dict | None = None):
        status, kind, data = self.request(method, path, json.dumps(payload).encode(),
                                          {"Content-Type": "application/json", **(headers or {})})
        return status, kind, data

    def form(self, path: str, fields: dict, file: tuple[str, bytes] | None = None, headers: dict | None = None):
        boundary = uuid.uuid4().hex
        chunks = []
        for name, value in fields.items():
            chunks.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())
        if file is not None:
            filename, data = file
            chunks.append(f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\n'
                          f"Content-Type: application/octet-stream\r\n\r\n".encode() + data + b"\r\n")
        chunks.append(f"--{boundary}--\r\n".encode())
        kind = f"multipart/form-data; boundary={boundary}"
        return self.request("POST", path, b"".join(chunks), {"Content-Type": kind, **(headers or {})})


@pytest.fixture
def started(monkeypatch):
    """Records what each route would have started, instead of starting it."""
    seen: dict = {}

    def job(url, render, model):
        seen["sprite"] = {"url": url, "render": render, "model": model}
        return JOB_ID

    def file_job(data, name, render, model):
        seen["sprite"] = {"bytes": data, "name": name, "render": render, "model": model}
        return JOB_ID

    def loop_url(url, settings, lock):
        seen["loop"] = {"url": audio_jobs.check_media_url(url), "settings": audio_jobs.parse_settings(settings)}
        return {"id": JOB_ID}

    def loop_file(data, name, settings, lock):
        seen["loop"] = {"bytes": data, "name": name, "settings": audio_jobs.parse_settings(settings)}
        return {"id": JOB_ID}

    for module in (routes_api, routes_sprite):
        monkeypatch.setattr(module, "start_job", job)
        monkeypatch.setattr(module, "start_file_job", file_job)
        monkeypatch.setattr(module, "read_status", lambda job_id: {"id": job_id})
    monkeypatch.setattr(audio_jobs, "begin_url", loop_url)
    monkeypatch.setattr(audio_jobs, "begin_file", loop_file)
    return seen


@pytest.fixture
def client():
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield Client(server.server_address[1])
    server.shutdown()
    server.server_close()

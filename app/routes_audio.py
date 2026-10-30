"""Audio routes: vocal-free loops and beep speech, as the studio page calls them."""

from __future__ import annotations

import json
from urllib.parse import unquote

from app import audio_jobs
from app.http_base import BaseHandler
from app.sprite_jobs import PIPELINE_LOCK, SAFE_ID


class AudioRoutes(BaseHandler):
    def audio_post(self, path: str) -> bool:
        if path == "/audio/speech":
            self._audio_speak()
            return True
        if path == "/audio/score":
            self._audio_score_url()
            return True
        if path == "/audio/score/file":
            self._audio_score_file()
            return True
        return False

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

    def _audio_settings(self) -> dict:
        raw = self.headers.get("X-Audio-Settings") or "{}"
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError("loop settings must be an object") from exc
        return audio_jobs.parse_settings(payload)

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

"""The one settings file all the builders share."""

from __future__ import annotations

import json

from app import pipeline, settings
from app.http_base import BaseHandler


class SettingsRoutes(BaseHandler):
    def settings_get(self, path: str) -> bool:
        if path == "/settings":
            self._json(200, settings.load())
            return True
        if path == f"/settings/{pipeline.SETTINGS_NAME}":
            body = json.dumps(settings.load(), indent=2).encode() + b"\n"
            self._bytes(200, body, "application/json; charset=utf-8", "no-store", pipeline.SETTINGS_NAME)
            return True
        return False

    def settings_put(self, path: str) -> bool:
        if path != "/settings":
            return False
        try:
            self._json(200, settings.save(self._json_body()))
        except ValueError as exc:
            self._json(400, {"error": str(exc)})
        return True

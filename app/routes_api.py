"""Public API, version 1. One route per generator, taking everything the studio page sends."""

from __future__ import annotations

import json
from email.parser import BytesParser
from email.policy import HTTP

from app import audio_jobs, pipeline
from app.http_base import BaseHandler
from app.sprite_jobs import PIPELINE_LOCK, check_url, dropped_name, read_status, start_file_job, start_job

# Field names each route takes besides `file`. Built from the validators so they never drift.
API_SPRITE_FIELDS = {"url", "model", *pipeline.RENDER_SPEC}
API_LOOP_FIELDS = {"url", "rights", *audio_jobs.parse_settings(None)}
API_SPEECH_FIELDS = set(audio_jobs.parse_speak({"text": "-"}))
API_SLACK = 1024 * 1024  # multipart boundaries and headers on top of the file


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



class ApiRoutes(BaseHandler):
    def api_post(self, path: str) -> bool:
        if path == "/api/v1/sprite":
            self._api_sprite()
            return True
        if path == "/api/v1/loop":
            self._api_loop()
            return True
        if path == "/api/v1/speech":
            self._api_speech()
            return True
        return False

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
                job_id = start_job(check_url(fields["url"]), render, model)
            else:
                data, filename = upload
                if len(data) > pipeline.MAX_BYTES:
                    raise ValueError("that image is larger than 20 MB")
                job_id = start_file_job(data, dropped_name(filename), render, model)
        except (ValueError, RuntimeError) as e:
            self._json(400, {"error": str(e)})
            return
        self._json(202, read_status(job_id))

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

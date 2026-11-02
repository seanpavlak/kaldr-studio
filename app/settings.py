"""One settings file for every builder, kept beside the key and downloadable from the studio.

Each section uses the field names of its /api/v1 route, so a section can be posted as it is.
The text of a line is never saved here, only how it is spoken.
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path

from app import audio_jobs, pipeline

VERSION = 1
LOCK = threading.Lock()


def _sprite(raw: object) -> dict:
    if not isinstance(raw, dict):
        raise ValueError("sprite settings must be an object")
    render = {name: value for name, value in raw.items() if name != "model"}
    return {"model": pipeline.parse_model(raw.get("model")), **pipeline.parse_render(render)}


def _speech(raw: object) -> dict:
    if not isinstance(raw, dict):
        raise ValueError("speech settings must be an object")
    spoken = audio_jobs.parse_speak({**raw, "text": "-"})
    del spoken["text"]
    return spoken


SECTIONS = {"sprite": _sprite, "loop": audio_jobs.parse_settings, "speech": _speech}


def _path() -> Path:
    return pipeline.support_folder() / pipeline.SETTINGS_NAME


def defaults() -> dict:
    return {name: parse({}) for name, parse in SECTIONS.items()}


def parse(raw: dict) -> dict:
    """Validate the sections a caller sent. A section left out stays as it was."""
    unknown = set(raw) - set(SECTIONS)
    if unknown:
        raise ValueError("unknown settings: " + ", ".join(sorted(unknown)))
    return {name: SECTIONS[name](value) for name, value in raw.items()}


def load() -> dict:
    """The saved settings. A section that no longer validates falls back to its defaults."""
    settings = defaults()
    try:
        saved = json.loads(_path().read_text())
    except (OSError, ValueError):
        saved = {}
    if isinstance(saved, dict):
        for name, parser in SECTIONS.items():
            try:
                if name in saved:
                    settings[name] = parser(saved[name])
            except ValueError:
                pass
    return {"version": VERSION, **settings}


def save(raw: dict) -> dict:
    changes = parse(raw)
    with LOCK:
        settings = {**load(), **changes}
        path = _path()
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(settings, indent=2) + "\n")
        os.replace(tmp, path)
    return settings

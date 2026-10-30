"""Vocal-free music jobs. Beep speech is instant. A loop is a background job.

Neither path calls OpenRouter. A sung melody may be replayed as an instrument.
The vocal recording itself is never written into the file.
"""

from __future__ import annotations

import importlib.util
import io
import json
import re
import subprocess
import sys
import tempfile
import threading
import uuid
import zipfile
from pathlib import Path
from urllib.parse import urlparse

import pipeline

ROOT = Path(__file__).resolve().parents[1]
AUDIO = pipeline.JOBS / "_audio"
MAX_BYTES = 80 * 1024 * 1024
MAX_TEXT = 600
MEDIA_SUFFIXES = {".mp3", ".mp4", ".m4a", ".wav", ".ogg", ".webm", ".flac", ".mov", ".mkv", ".aac", ".m4v"}
LEADS = {"vocal-melody", "instrument", "none"}
STYLES = {"soft", "gb"}
TRACKS = (
    ("lead", "Lead"),
    ("pluck", "Pluck"),
    ("pad", "Pad"),
    ("arp", "Arpeggio"),
    ("bass", "Bass"),
    ("drums", "Drums"),
    ("noise", "Noise"),
)
TRACK_FILES = {f"{stem_id}.wav" for stem_id, _label in TRACKS}


def parse_settings(raw) -> dict:
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise ValueError("loop settings must be an object")
    style = raw.get("style") or "soft"
    if style not in STYLES:
        raise ValueError("style must be soft or gb")
    lead = raw.get("lead") or "vocal-melody"
    if lead not in LEADS:
        raise ValueError("lead must be vocal-melody, instrument, or none")

    def number(key: str, default: float, lo: float, hi: float) -> float:
        value = raw.get(key, default)
        try:
            value = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{key} must be a number") from exc
        if not lo <= value <= hi:
            raise ValueError(f"{key} is out of range")
        return value

    min_seconds = number("min_seconds", 40, 8, 180)
    max_seconds = number("max_seconds", 90, 8, 240)
    start_after = number("start_after", 0, 0, 600)
    if min_seconds > max_seconds:
        raise ValueError("the shortest loop cannot be longer than the longest")
    return {
        "style": style,
        "classic": bool(raw.get("classic", False)),
        "lead": lead,
        "min_seconds": min_seconds,
        "max_seconds": max_seconds,
        "start_after": start_after,
        "space": number("space", 1, 0, 2.5),
        "brightness": number("brightness", 1, 0.35, 2),
        "lead_level": number("lead_level", 1, 0, 2.5),
        "chords_level": number("chords_level", 1, 0, 2.5),
        "bass_level": number("bass_level", 1, 0, 2.5),
        "drums_level": number("drums_level", 1, 0, 2.5),
    }


def parse_speak(raw: dict) -> dict:
    text = raw.get("text")
    if not isinstance(text, str) or not text.strip():
        raise ValueError("type a line first")
    text = text.strip()
    if len(text) > MAX_TEXT:
        raise ValueError("keep it under 600 characters")

    def number(key: str, default: float, lo: float, hi: float) -> float:
        value = raw.get(key, default)
        try:
            value = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{key} must be a number") from exc
        if not lo <= value <= hi:
            raise ValueError(f"{key} is out of range")
        return value

    seed = raw.get("seed", None)
    if seed is None or seed == "":
        parsed_seed = None
    else:
        try:
            parsed_seed = int(seed)
        except (TypeError, ValueError) as exc:
            raise ValueError("seed must be a whole number") from exc
        if not 0 <= parsed_seed <= 2_000_000_000:
            raise ValueError("seed is out of range")
    return {
        "text": text,
        "pitch": number("pitch", 300, 80, 800),
        "speed": number("speed", 16, 4, 40),
        "variation": number("variation", 3, 0, 12),
        "length": number("length", 1, 0.2, 3),
        "drop": number("drop", 1, 0, 6),
        "pauses": number("pauses", 1, 0, 4),
        "brightness": number("brightness", 6000, 400, 16000),
        "lift": number("lift", 1, 0, 6),
        "tone": number("tone", 0.5, 0.05, 0.9),
        "seed": parsed_seed,
    }


def check_media_url(url) -> str:
    if not isinstance(url, str):
        raise ValueError("give an http or https address")
    url = url.strip()
    if len(url) > 2000:
        raise ValueError("that address is too long")
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("give an http or https address")
    return url


def display_name(raw: str) -> str:
    cleaned = re.sub(r"\s+", " ", raw).strip()
    cleaned = re.sub(r"[^\w.\- ]+", "", cleaned).strip(" .")
    return (cleaned[:80] or "score")


def _folder(job_id: str) -> Path:
    return AUDIO / job_id


def _save(folder: Path, payload: dict) -> None:
    path = folder / "status.json"
    tmp = folder / "status.json.tmp"
    tmp.write_text(json.dumps(payload))
    tmp.replace(path)


def _read(job_id: str) -> dict | None:
    path = _folder(job_id) / "status.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text())


def latest_done() -> dict | None:
    if not AUDIO.is_dir():
        return None
    best = None
    best_time = -1.0
    for folder in AUDIO.iterdir():
        if not folder.is_dir() or not re.fullmatch(r"[0-9a-f]{16}", folder.name):
            continue
        status = _read(folder.name)
        if not status or status.get("status") != "done" or not (folder / "loop.wav").is_file():
            continue
        mtime = (folder / "status.json").stat().st_mtime
        if mtime > best_time:
            best_time = mtime
            best = folder.name
    return view(best) if best else None


def view(job_id: str) -> dict | None:
    data = _read(job_id)
    if data is None:
        return None
    folder = _folder(job_id)
    base = f"/audio/score/{job_id}"
    tracks = [
        {"id": stem_id, "label": label, "wav": f"{base}/{stem_id}.wav"}
        for stem_id, label in TRACKS
        if (folder / f"{stem_id}.wav").is_file()
    ]
    ready = (folder / "loop.wav").is_file() and (folder / "loop.ogg").is_file()
    data["files"] = {
        "wav": f"{base}/loop.wav" if (folder / "loop.wav").is_file() else None,
        "ogg": f"{base}/loop.ogg" if (folder / "loop.ogg").is_file() else None,
        "zip": f"{base}/score.zip" if ready else None,
        "tracks": tracks,
    }
    return data


def file_bytes(job_id: str, name: str) -> tuple[bytes, str, str | None] | None:
    folder = _folder(job_id)
    status = _read(job_id)
    if status is None or status.get("status") != "done":
        return None
    download = _download_name(status.get("name") or "score")
    if name == "loop.wav" and (folder / "loop.wav").is_file():
        return (folder / "loop.wav").read_bytes(), "audio/wav", None
    if name in TRACK_FILES and (folder / name).is_file():
        return (folder / name).read_bytes(), "audio/wav", None
    if name == "loop.ogg" and (folder / "loop.ogg").is_file():
        return (folder / "loop.ogg").read_bytes(), "audio/ogg", None
    if name == "score.zip" and (folder / "loop.wav").is_file() and (folder / "loop.ogg").is_file():
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.write(folder / "loop.wav", "loop.wav")
            archive.write(folder / "loop.ogg", "loop.ogg")
            for stem_id, _label in TRACKS:
                stem = folder / f"{stem_id}.wav"
                if stem.is_file():
                    archive.write(stem, f"{stem_id}.wav")
        return buf.getvalue(), "application/zip", f"{download}.zip"
    return None


def _download_name(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-")
    return (cleaned[:60] or "score")


def speech_wav(raw: dict) -> bytes:
    spoken = parse_speak(raw)
    module = _beep_speech()
    audio = module.speak(
        spoken["text"],
        spoken["pitch"],
        spoken["speed"],
        spoken["variation"],
        spoken["seed"],
        length=spoken["length"],
        drop=spoken["drop"],
        pauses=spoken["pauses"],
        brightness=spoken["brightness"],
        lift=spoken["lift"],
        width=spoken["tone"],
    )
    buf = io.BytesIO()
    import soundfile as sf
    sf.write(buf, audio, module.SR, format="WAV", subtype="PCM_16")
    return buf.getvalue()


def begin_url(url: str, settings: dict, lock: threading.Lock) -> dict:
    checked = check_media_url(url)
    chosen = parse_settings(settings)
    job_id = uuid.uuid4().hex[:16]
    folder = _folder(job_id)
    folder.mkdir(parents=True)
    name = display_name(Path(urlparse(checked).path).name or "score")
    payload = _running(job_id, name, "queued", chosen)
    _save(folder, payload)
    threading.Thread(target=_worker, args=(job_id, checked, None, lock), daemon=True).start()
    return view(job_id)


def begin_file(data: bytes, filename: str, settings: dict, lock: threading.Lock) -> dict:
    if not data:
        raise ValueError("that file is empty")
    if len(data) > MAX_BYTES:
        raise ValueError("that file is larger than 80 MB")
    suffix = Path(filename).suffix.lower()
    if suffix not in MEDIA_SUFFIXES:
        raise ValueError("that file is not a video or a song")
    chosen = parse_settings(settings)
    job_id = uuid.uuid4().hex[:16]
    folder = _folder(job_id)
    folder.mkdir(parents=True)
    source = folder / f"source{suffix}"
    source.write_bytes(data)
    name = display_name(Path(filename).stem or "score")
    payload = _running(job_id, name, "queued", chosen)
    _save(folder, payload)
    threading.Thread(target=_worker, args=(job_id, None, source, lock), daemon=True).start()
    return view(job_id)


def _running(job_id: str, name: str, stage: str, settings: dict) -> dict:
    return {
        "id": job_id,
        "name": name,
        "status": "running",
        "stage": stage,
        "error": None,
        "settings": settings,
        "info": None,
    }


def _worker(job_id: str, url: str | None, source: Path | None, lock: threading.Lock) -> None:
    folder = _folder(job_id)
    try:
        with lock:
            retro = _retroloop()
            status = _read(job_id)
            settings = status["settings"]

            def progress(stage: str) -> None:
                current = _read(job_id) or status
                current["stage"] = stage
                _save(folder, current)

            if url:
                progress("download")
                with tempfile.TemporaryDirectory() as tmp:
                    path = retro.fetch(url, Path(tmp))
                    host = urlparse(url).netloc.lower()
                    if "youtube" in host or host.endswith("youtu.be"):
                        current = _read(job_id) or status
                        current["name"] = display_name(retro.youtube_title(url))
                        _save(folder, current)
                    progress("separate")
                    stems = retro.separate(path)
            else:
                progress("separate")
                stems = retro.separate(source)
            audio, info, tracks = retro.render_loop(
                stems,
                style=settings["style"],
                classic=settings["classic"],
                lead_from=settings["lead"],
                min_seconds=settings["min_seconds"],
                max_seconds=settings["max_seconds"],
                start_after=settings["start_after"],
                space=settings.get("space", 1),
                brightness=settings.get("brightness", 1),
                lead_level=settings.get("lead_level", 1),
                chords_level=settings.get("chords_level", 1),
                bass_level=settings.get("bass_level", 1),
                drums_level=settings.get("drums_level", 1),
                progress=progress,
            )
            import soundfile as sf
            sf.write(folder / "loop.wav", audio.T, retro.SR, subtype="PCM_16")
            sf.write(folder / "loop.ogg", audio.T, retro.SR, format="OGG", subtype="VORBIS")
            for stem_id, _label in TRACKS:
                stem = tracks.get(stem_id)
                if stem is not None:
                    sf.write(folder / f"{stem_id}.wav", stem.T, retro.SR, subtype="PCM_16")
            done = _read(job_id) or status
            done["status"] = "done"
            done["stage"] = "done"
            done["error"] = None
            done["info"] = info
            _save(folder, done)
    except Exception as exc:
        failed = _read(job_id) or {"id": job_id, "name": "score", "settings": {}, "info": None}
        failed["status"] = "error"
        failed["stage"] = "error"
        failed["error"] = _public_error(exc)
        _save(folder, failed)


def _public_error(exc: Exception) -> str:
    if isinstance(exc, ImportError):
        return "the loop tools are not installed in this environment"
    if isinstance(exc, FileNotFoundError):
        return "ffmpeg is not installed"
    if isinstance(exc, subprocess.CalledProcessError):
        return "could not read that recording"
    message = str(exc).strip() or "the loop failed"
    if len(message) > 300:
        message = message[:300]
    return message


def _beep_speech():
    path = ROOT / "beep_speech" / "beep_speech.py"
    spec = importlib.util.spec_from_file_location("kaldr_beep_speech", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("beep speech is not available")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _retroloop():
    root = str(ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)
    import retroloop
    return retroloop

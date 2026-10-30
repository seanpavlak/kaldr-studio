"""One creature from an image URL: download, redraw, pixelate, idle.

The redraw step is a single function. The studio calls FLUX.2 Klein 4B on
OpenRouter, the same model the local mflux pass uses. mflux_redraw remains
for a machine that should run the weights itself.
"""

from __future__ import annotations

import base64
import io
import json
import math
import os
import ssl
import sys
import urllib.error
import urllib.request
import zlib
from pathlib import Path

import certifi
import numpy as np
from PIL import Image, UnidentifiedImageError
from PIL.Image import DecompressionBombError

ROOT = Path(__file__).resolve().parent.parent
JOBS = ROOT / "studio_jobs"
MAX_BYTES = 20 * 1024 * 1024
MAX_PIXELS = 16_000_000
_SCRIPTS = ROOT / "scripts"

# Defaults match scripts/pixelate.py. Ranges are what the studio page offers.
RENDER_SPEC = {
    "canvas": {"type": "choice", "choices": (32, 48, 64), "default": 48},
    "palette_colors": {"type": "int", "min": 4, "max": 24, "default": 14},
    "saturation": {"type": "float", "min": 0.5, "max": 2.0, "default": 1.25},
    "contrast": {"type": "float", "min": 0.5, "max": 2.0, "default": 1.1},
    "coverage": {"type": "float", "min": 0.05, "max": 0.8, "default": 0.35},
    "dark_bias": {"type": "float", "min": 0.0, "max": 6.0, "default": 3.0},
    "outline": {"type": "bool", "default": True},
    "sticker": {"type": "bool", "default": False},
}
RENDER_LABELS = {
    "canvas": "size must be 32, 48, or 64",
    "palette_colors": "colors must be from 4 to 24",
    "saturation": "saturation must be from 0.5 to 2",
    "contrast": "contrast must be from 0.5 to 2",
    "coverage": "coverage must be from 0.05 to 0.8",
    "dark_bias": "dark lines must be from 0 to 6",
    "outline": "outline must be true or false",
    "sticker": "sticker border must be true or false",
}


def _scripts_on_path() -> None:
    if str(_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(_SCRIPTS))


OPENROUTER_URL = "https://openrouter.ai/api/v1/images"
OPENROUTER_KEY_URL = "https://openrouter.ai/api/v1/key"
# Models whose image endpoint accepts a reference image and a square frame.
# Price is one redraw at the resolution this studio requests. "about" means
# the provider bills tokens, so the charge moves a little with the picture.
DEFAULT_MODEL = "black-forest-labs/flux.2-klein-4b"
MODELS = (
    {"id": "black-forest-labs/flux.2-klein-4b", "label": "FLUX.2 Klein 4B", "price": "$0.014", "usd": 0.014, "estimate": False, "seed": True, "output_format": "png", "resolution": None},
    {"id": "black-forest-labs/flux-3-image-klein", "label": "FLUX.3 Klein", "price": "$0.009", "usd": 0.009, "estimate": False, "seed": False, "output_format": None, "resolution": "1K"},
    {"id": "bytedance-seed/seedream-5-0-flash", "label": "Seedream 5.0 Flash", "price": "$0.018", "usd": 0.018, "estimate": False, "seed": True, "output_format": None, "resolution": "1K"},
    {"id": "qwen/qwen-image-2.1-turbo", "label": "Qwen Image 2.1 Turbo", "price": "$0.018", "usd": 0.018, "estimate": False, "seed": True, "output_format": None, "resolution": "1K"},
    {"id": "sourceful/riverflow-v2.5-fast", "label": "Riverflow 2.5 Fast", "price": "$0.019", "usd": 0.019, "estimate": False, "seed": False, "output_format": "jpeg", "resolution": "1K"},
    {"id": "openai/gpt-image-1-mini", "label": "GPT Image 1 Mini", "price": "about $0.02", "usd": 0.02, "estimate": True, "seed": False, "output_format": None, "resolution": None},
    {"id": "black-forest-labs/flux.2-pro", "label": "FLUX.2 Pro", "price": "$0.030", "usd": 0.030, "estimate": False, "seed": True, "output_format": "png", "resolution": None},
    {"id": "google/gemini-2.5-flash-image", "label": "Nano Banana", "price": "about $0.04", "usd": 0.04, "estimate": True, "seed": False, "output_format": None, "resolution": None},
)


def list_models() -> list[dict]:
    return [
        {"id": item["id"], "label": item["label"], "price": item["price"], "usd": item["usd"], "estimate": item["estimate"]}
        for item in MODELS
    ]


def parse_model(raw: object) -> str:
    if raw is None or raw == "":
        return DEFAULT_MODEL
    if not isinstance(raw, str) or raw not in {item["id"] for item in MODELS}:
        raise ValueError("pick a model from the list")
    return raw


def _model_spec(model_id: str) -> dict:
    for item in MODELS:
        if item["id"] == model_id:
            return item
    return MODELS[0]


def _key_path() -> Path:
    folder = Path.home() / "Library/Application Support/sprite-studio"
    folder.mkdir(mode=0o700, exist_ok=True)
    os.chmod(folder, 0o700)
    return folder / "openrouter.key"


def openrouter_key_saved() -> bool:
    return bool(openrouter_key_hint())


def openrouter_key_hint() -> str:
    """Start and end of the saved key. The middle stays on disk."""
    path = _key_path()
    if not path.is_file():
        return ""
    key = path.read_text().strip()
    if len(key) < 16:
        return ""
    # OpenRouter's own preview format: sk-or-v1-abc...xyz
    return f"{key[:12]}...{key[-3:]}"


def save_openrouter_key(key: str) -> None:
    key = key.strip()
    if len(key) < 20 or len(key) > 300 or any(char.isspace() for char in key):
        raise ValueError("that does not look like an OpenRouter key")
    path = _key_path()
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(path, flags, 0o600)
    try:
        os.write(fd, key.encode())
    finally:
        os.close(fd)
    os.chmod(path, 0o600)


def clear_openrouter_key() -> None:
    path = _key_path()
    if path.is_file():
        path.unlink()


def key_limit_state(payload: object) -> bool | None:
    """True when the key has a credit cap. False when OpenRouter reports no cap. None if unknown."""
    if not isinstance(payload, dict):
        return None
    data = payload.get("data")
    if not isinstance(data, dict) or "limit" not in data:
        return None
    limit = data.get("limit")
    if limit is None:
        return False
    if isinstance(limit, bool) or not isinstance(limit, (int, float)):
        return None
    return True


def key_remaining(payload: object) -> float | None:
    """Dollars left on the key cap. None when OpenRouter has no number to give."""
    if not isinstance(payload, dict):
        return None
    data = payload.get("data")
    if not isinstance(data, dict):
        return None
    remaining = data.get("limit_remaining")
    if isinstance(remaining, bool) or not isinstance(remaining, (int, float)):
        return None
    return float(remaining)


def _key_payload() -> object | None:
    """OpenRouter key metadata. Never logs the key or the response."""
    try:
        token = _openrouter_key()
    except RuntimeError:
        return None
    req = urllib.request.Request(
        OPENROUTER_KEY_URL,
        headers={"Authorization": "Bearer " + token},
        method="GET",
    )
    context = ssl.create_default_context(cafile=certifi.where())
    try:
        with urllib.request.urlopen(req, timeout=12, context=context) as resp:
            return json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError, ValueError):
        return None


def openrouter_key_limited() -> bool | None:
    """Ask OpenRouter whether the saved key has a spending limit. Never logs the key."""
    payload = _key_payload()
    if payload is None:
        return None
    return key_limit_state(payload)


def openrouter_key_budget() -> dict:
    """Limit flag plus dollars remaining. A failed check is all nulls."""
    payload = _key_payload()
    if payload is None:
        return {"limited": None, "remaining": None}
    return {"limited": key_limit_state(payload), "remaining": key_remaining(payload)}


def _openrouter_key() -> str:
    path = _key_path()
    if not path.is_file():
        raise RuntimeError("redraw failed: add your OpenRouter key")
    key = path.read_text().strip()
    if not key:
        raise RuntimeError("redraw failed: add your OpenRouter key")
    return key


def _reference_png(image: Path) -> bytes:
    """PNG bytes for the model. Black Forest Labs rejects a reference under 256px."""
    with Image.open(image) as opened:
        opened.load()
        frame = opened.convert("RGBA")
    width, height = frame.size
    if width < 256 or height < 256:
        scale = max(256 / width, 256 / height)
        size = (math.ceil(width * scale), math.ceil(height * scale))
        # A tiny sprite stays crisp. A larger picture is scaled smoothly.
        resample = Image.Resampling.NEAREST if max(width, height) <= 64 else Image.Resampling.LANCZOS
        frame = frame.resize(size, resample)
    buf = io.BytesIO()
    frame.save(buf, format="PNG")
    return buf.getvalue()


def openrouter_redraw(image: Path, out: Path, seed: int, prompt: Path | None = None, model: str | None = None) -> None:
    """Redraw a reference into a square PNG with one of the curated OpenRouter models."""
    _scripts_on_path()
    from run_pipeline import CONVERSION_PROMPT

    spec = _model_spec(model or DEFAULT_MODEL)
    prompt_text = (prompt or CONVERSION_PROMPT).read_text().strip()
    encoded = base64.b64encode(_reference_png(image)).decode("ascii")
    payload = {
        "model": spec["id"],
        "prompt": prompt_text,
        "aspect_ratio": "1:1",
        "input_references": [
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{encoded}"}}
        ],
    }
    if spec["seed"]:
        payload["seed"] = seed
    if spec["output_format"]:
        payload["output_format"] = spec["output_format"]
    if spec["resolution"]:
        payload["resolution"] = spec["resolution"]
    req = urllib.request.Request(
        OPENROUTER_URL,
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": "Bearer " + _openrouter_key(),
            "Content-Type": "application/json",
        },
        method="POST",
    )
    context = ssl.create_default_context(cafile=certifi.where())
    try:
        with urllib.request.urlopen(req, timeout=180, context=context) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace").strip().replace("\n", " ")
        raise RuntimeError(f"redraw failed: OpenRouter HTTP {e.code}: {detail[-400:]}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"redraw failed: {getattr(e, 'reason', e)}") from e

    images = data.get("data") if isinstance(data, dict) else None
    first = images[0] if isinstance(images, list) and images else None
    if not isinstance(first, dict):
        raise RuntimeError("redraw failed: OpenRouter returned no image")
    if first.get("b64_json"):
        raw = base64.b64decode(first["b64_json"])
    elif first.get("url"):
        image_req = urllib.request.Request(first["url"], headers={"User-Agent": "keepers-sprite-studio"})
        try:
            with urllib.request.urlopen(image_req, timeout=60, context=context) as resp:
                raw = resp.read()
        except urllib.error.URLError as e:
            raise RuntimeError(f"redraw failed: could not download the OpenRouter image: {e}") from e
    else:
        raise RuntimeError("redraw failed: OpenRouter returned no image")
    try:
        with Image.open(io.BytesIO(raw)) as img:
            img.load()
            img.convert("RGBA").save(out)
    except (UnidentifiedImageError, OSError) as e:
        raise RuntimeError("redraw failed: OpenRouter did not return an image") from e


def mflux_redraw(image: Path, out: Path, seed: int, prompt: Path | None = None, model: str | None = None) -> None:
    """Redraw a reference into a 512 PNG. Replace this to call a hosted model."""
    import subprocess

    # sys.executable is a venv symlink. Resolving it leaves the venv and loses mflux.
    bin_dir = str(Path(sys.executable).parent)
    os.environ["PATH"] = bin_dir + os.pathsep + os.environ.get("PATH", "")
    _scripts_on_path()
    from run_pipeline import CONVERSION_PROMPT, run_pass1

    try:
        run_pass1(image, out, seed, prompt or CONVERSION_PROMPT)
    except subprocess.CalledProcessError as e:
        detail = (e.stderr or e.stdout or str(e)).strip()
        raise RuntimeError("redraw failed: " + detail[-400:]) from e
    except FileNotFoundError as e:
        raise RuntimeError(
            "redraw failed: mflux-generate-flux2-edit was not found in the project venv"
        ) from e
    if not out.exists():
        raise RuntimeError("redraw failed: the model did not write an image")


def save_image_bytes(data: bytes, dest: Path, *, bad: str) -> None:
    """Write image bytes as a PNG. Raises RuntimeError when they are not a usable image."""
    if len(data) > MAX_BYTES:
        raise RuntimeError("that image is larger than 20 MB")
    try:
        with Image.open(io.BytesIO(data)) as img:
            img.load()
            if img.width * img.height > MAX_PIXELS:
                raise RuntimeError("that image is too large")
            frame = img.convert("RGBA")
        frame.save(dest, "PNG")
    except RuntimeError:
        dest.unlink(missing_ok=True)
        raise
    except UnidentifiedImageError as e:
        dest.unlink(missing_ok=True)
        raise RuntimeError(bad) from e
    except DecompressionBombError as e:
        dest.unlink(missing_ok=True)
        raise RuntimeError("that image is too large") from e
    except OSError as e:
        dest.unlink(missing_ok=True)
        raise RuntimeError(bad) from e


def download_reference(url: str, dest: Path) -> None:
    """Save the URL as a PNG. Raises RuntimeError when it is not a usable image."""
    req = urllib.request.Request(url, headers={"User-Agent": "keepers-sprite-studio"})
    # The python.org Mac install has no default CA bundle, so HTTPS checks use certifi.
    context = ssl.create_default_context(cafile=certifi.where())
    try:
        with urllib.request.urlopen(req, timeout=30, context=context) as resp:
            data = resp.read(MAX_BYTES + 1)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"could not download that URL: HTTP {e.code}") from e
    except urllib.error.URLError as e:
        reason = getattr(e, "reason", e)
        raise RuntimeError(f"could not download that URL: {reason}") from e
    save_image_bytes(data, dest, bad="that URL did not return an image")


def save_gif(frames: list[np.ndarray], durations: list[int], path: Path) -> None:
    """Animated GIF. Pixel colors are kept exactly when the sprite fits in 255 colors."""
    used: list[tuple[int, int, int]] = []
    seen: set[tuple[int, int, int]] = set()
    for frame in frames:
        opaque = frame.reshape(-1, 4)
        opaque = opaque[opaque[:, 3] >= 128][:, :3]
        for rgb in opaque:
            color = (int(rgb[0]), int(rgb[1]), int(rgb[2]))
            if color not in seen:
                seen.add(color)
                used.append(color)
    if len(used) > 255:
        _save_gif_quantized(frames, durations, path)
        return
    index = {color: i for i, color in enumerate(used)}
    palette = [channel for color in used for channel in color]
    palette.extend([0] * (768 - len(palette)))
    converted = []
    width, height = int(frames[0].shape[1]), int(frames[0].shape[0])
    for frame in frames:
        image = Image.new("P", (width, height))
        image.putpalette(palette)
        pixels = []
        for pixel in frame.reshape(-1, 4):
            if int(pixel[3]) < 128:
                pixels.append(255)
            else:
                pixels.append(index[(int(pixel[0]), int(pixel[1]), int(pixel[2]))])
        image.putdata(pixels)
        converted.append(image)
    converted[0].save(
        path,
        save_all=True,
        append_images=converted[1:],
        duration=durations,
        loop=0,
        disposal=2,
        transparency=255,
        optimize=False,
    )


def _save_gif_quantized(frames: list[np.ndarray], durations: list[int], path: Path) -> None:
    """Fallback when a sprite uses more than 255 colors."""
    images = [Image.fromarray(f, "RGBA") for f in frames]
    palette_src = images[0].convert("RGB").quantize(
        colors=255, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE
    )
    converted = []
    for im in images:
        quantized = im.convert("RGB").quantize(palette=palette_src, dither=Image.Dither.NONE)
        alpha = im.getchannel("A")
        quantized.putdata([255 if a < 128 else p for p, a in zip(quantized.getdata(), alpha.getdata())])
        palette = quantized.getpalette() or []
        if len(palette) < 768:
            palette = palette + [0] * (768 - len(palette))
        quantized.putpalette(palette)
        converted.append(quantized)
    converted[0].save(
        path,
        save_all=True,
        append_images=converted[1:],
        duration=durations,
        loop=0,
        disposal=2,
        transparency=255,
        optimize=False,
    )


def default_render() -> dict:
    return {name: spec["default"] for name, spec in RENDER_SPEC.items()}


def parse_render(raw: object) -> dict:
    """Validate the studio's render controls. Missing fields keep the batch defaults."""
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise ValueError("render settings must be an object")
    unknown = set(raw) - set(RENDER_SPEC)
    if unknown:
        raise ValueError("unknown render setting: " + ", ".join(sorted(unknown)))
    out = default_render()
    for name, spec in RENDER_SPEC.items():
        if name not in raw or raw[name] is None:
            continue
        value = raw[name]
        kind = spec["type"]
        if kind == "bool":
            if not isinstance(value, bool):
                raise ValueError(RENDER_LABELS[name])
            out[name] = value
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(RENDER_LABELS[name])
        if kind == "choice":
            if int(value) not in spec["choices"] or int(value) != value:
                raise ValueError(RENDER_LABELS[name])
            out[name] = int(value)
            continue
        if kind == "int":
            if int(value) != value:
                raise ValueError(RENDER_LABELS[name])
            value = int(value)
        else:
            value = float(value)
        if not spec["min"] <= value <= spec["max"]:
            raise ValueError(RENDER_LABELS[name])
        out[name] = value
    return out


def _finish_sprite(stylized: Path, workdir: Path, seed_key: str, render: dict, on_stage) -> None:
    _scripts_on_path()
    from pixelate import pixelate

    with Image.open(stylized) as img:
        sprite_img = pixelate(
            img,
            sticker=render["sticker"],
            canvas=render["canvas"],
            palette_colors=render["palette_colors"],
            saturation=render["saturation"],
            contrast=render["contrast"],
            alpha_coverage=render["coverage"],
            dark_bias=render["dark_bias"],
            outline=render["outline"],
        )
    final = workdir / "final.png"
    sprite_img.save(final)

    on_stage("animate")
    from animate import build_one

    sprite = np.array(sprite_img.convert("RGBA"))
    frames, meta = build_one(sprite, seed_key)
    meta["render"] = render
    sheet = Image.fromarray(np.concatenate(frames, axis=1), "RGBA")
    sheet.save(workdir / "idle.png", optimize=True)
    (workdir / "idle.json").write_text(json.dumps(meta, indent=2) + "\n")
    save_gif(frames, meta["frame_ms"], workdir / "idle.gif")


def render_final(workdir: Path, seed_key: str, render: dict, on_stage) -> None:
    """Pixelate and animate an existing redraw. Does not download or call the model."""
    stylized = workdir / "stylized.png"
    if not stylized.is_file():
        raise RuntimeError("redraw this image before updating the sprite")
    on_stage("pixelate")
    _finish_sprite(stylized, workdir, seed_key, render, on_stage)


def run(url: str, workdir: Path, seed_key: str, on_stage, redraw=openrouter_redraw, render: dict | None = None,
        model: str | None = None, local: bool = False) -> None:
    """Run the four stages. on_stage(name) is called before each one starts."""
    workdir.mkdir(parents=True, exist_ok=True)
    chosen = parse_model(model)

    reference = workdir / "reference.png"
    if not local:
        on_stage("download")
        download_reference(url, reference)
    elif not reference.is_file():
        raise RuntimeError("that file is not an image")

    on_stage("redraw")
    stylized = workdir / "stylized.png"
    seed = zlib.crc32(seed_key.encode()) % 1_000_000
    redraw(reference, stylized, seed, model=chosen)

    on_stage("pixelate")
    # Studio sprites are not dex names, so facing and fill-hole lists stay off.
    _finish_sprite(stylized, workdir, seed_key, render or default_render(), on_stage)

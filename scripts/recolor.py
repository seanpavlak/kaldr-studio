"""Apply palette-only changes (private/dex/_tools/recolors.txt) to creatures' base renders.

The original render is kept as <key>.stylized.orig.png and every recolor starts from it, so
rerunning never compounds the shift. The base sprite is re-pixelated and Resonant/Aberrant are
redrawn from the recolored base so all three forms match.

    .venv/bin/python -m scripts.recolor [NAME ...]
"""
from __future__ import annotations

import glob
import json
import shutil
import sys
import zlib
from pathlib import Path

import numpy as np
from PIL import Image

from scripts.pixelate import pixelate_file
from scripts.run_pipeline import ASSETS_FINAL, ASSETS_TEMP, ROOT, VARIANT_PROMPTS, run_pass1


def recolors() -> dict[str, tuple[float, float, float]]:
    out = {}
    for line in (ROOT / "private" / "dex" / "_tools" / "recolors.txt").read_text().splitlines():
        if line.strip() and not line.startswith("#"):
            name, shift, sat, *val = line.split("|")
            out[name] = (float(shift), float(sat), float(val[0]) if val else 1.0)
    return out


def recolor_render(render: Path, shift: float, sat: float, val: float = 1.0) -> None:
    orig = render.with_name(render.name.replace(".stylized.png", ".stylized.orig.png"))
    if not orig.exists():
        shutil.copy(render, orig)
    hsv = np.array(Image.open(orig).convert("RGB").convert("HSV")).astype(np.float32) / 255
    hsv[..., 0] = (hsv[..., 0] + shift) % 1.0
    hsv[..., 1] = np.clip(hsv[..., 1] * sat, 0, 1)
    hsv[..., 2] = np.clip(hsv[..., 2] * val, 0, 1)
    Image.fromarray((hsv * 255).astype(np.uint8), "HSV").convert("RGB").save(render)


def main() -> None:
    entries = {json.loads(Path(f).read_text())["name"]: json.loads(Path(f).read_text()) for f in glob.glob(str(ROOT / "private" / "dex" / "[0-9]*.json"))}
    todo = recolors()
    if sys.argv[1:]:
        todo = {n: todo[n] for n in sys.argv[1:]}
    for name, (shift, sat, val) in todo.items():
        e = entries[name]
        key = e["sprite"].split("/")[-1][: -len(".png")]
        base = ASSETS_TEMP / f"{key}.stylized.png"
        recolor_render(base, shift, sat, val)
        pixelate_file(str(base), str(ASSETS_FINAL / f"{key}.png"))
        palette_key = e["source_file"] or e["id"]
        for variant, prompt in VARIANT_PROMPTS.items():
            render = ASSETS_TEMP / f"{key}_{variant}.stylized.png"
            run_pass1(base, render, zlib.crc32(f"{key}_{variant}_recolor".encode()) % 1_000_000, prompt)
            pixelate_file(str(render), str(ASSETS_FINAL / f"{key}_{variant}.png"), variant=variant, key=palette_key)
        print(f"ok  {name}", flush=True)


if __name__ == "__main__":
    main()

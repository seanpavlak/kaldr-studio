"""Redesign a creature from a written brief (private/dex/_tools/redesigns.txt) instead of its source image.

The base is generated from text alone, then Resonant and Aberrant are drawn from the new base as
usual. The creature is recorded in private/dex/_tools/generated_art.json (so the dex uses this art) and its
source image is skipped by run_pipeline.py (so a rerun can't bring the old look back).

    .venv/bin/python -m scripts.redesign [NAME ...]
"""

from __future__ import annotations

import glob
import json
import subprocess
import sys
import zlib
from pathlib import Path

from scripts.pixelate import pixelate_file
from scripts.run_pipeline import ASSETS_FINAL, ASSETS_TEMP, MODEL, ROOT, VARIANT_PROMPTS, run_pass1

TOOLS = ROOT / "private" / "dex" / "_tools"
GENERATED_ART = TOOLS / "generated_art.json"
STYLE = (
    "Style: small retro creature-battler game sprite in clean 16-bit pixel art, like a Cassette Beasts battle sprite. "
    "Simple readable shapes, clear eyes, bold flat color areas with 2-3 shades of cel shading, light from the top-left, "
    "solid black outline. No gradients, no texture, no noise.\n\n"
    "Composition: one creature, full body, 3/4 view, centered, filling most of the frame, nothing cropped. "
    "Plain flat white background. No shadow, no ground, no text, no border."
)


def palette_key(name: str) -> str:
    """Seed for a generated creature's Resonant/Aberrant palette: the id format these sprites were first
    made with, so re-renders keep the same colours now that ids are UUIDs."""
    import re
    return "gk-" + re.sub(r"[^a-z0-9]+", "_", name.encode("ascii", "ignore").decode().lower()).strip("_")


def briefs() -> dict[str, str]:
    out = {}
    for line in (TOOLS / "redesigns.txt").read_text().splitlines():
        if line.strip() and not line.startswith("#"):
            name, brief = line.split("|", 1)
            out[name] = brief
    return out


def text_to_image(prompt_file: Path, out: Path, seed: int) -> None:
    out.unlink(missing_ok=True)  # mflux never overwrites
    subprocess.run(["mflux-generate-flux2", "--model", MODEL, "--prompt-file", str(prompt_file), "--width", "512",
                    "--height", "512", "--steps", "8", "--seed", str(seed), "--no-metadata", "--output", str(out)],
                   check=True, capture_output=True, text=True)


def main() -> None:
    entries = {json.loads(Path(f).read_text())["name"]: json.loads(Path(f).read_text()) for f in glob.glob(str(ROOT / "private" / "dex" / "[0-9]*.json"))}
    todo = briefs()
    if sys.argv[1:]:
        todo = {n: todo[n] for n in sys.argv[1:]}
    art = json.loads(GENERATED_ART.read_text())
    for name, brief in todo.items():
        e = entries[name]
        key = art.setdefault(name, e["index_name"])
        prompt = ASSETS_TEMP / f"{key}.prompt.md"
        prompt.write_text(f"A single original creature: {brief}.\n\n{STYLE}")
        base = ASSETS_TEMP / f"{key}.stylized.png"
        text_to_image(prompt, base, zlib.crc32(f"{key}_redesign".encode()) % 1_000_000)
        pixelate_file(str(base), str(ASSETS_FINAL / f"{key}.png"))
        for variant, vprompt in VARIANT_PROMPTS.items():
            render = ASSETS_TEMP / f"{key}_{variant}.stylized.png"
            run_pass1(base, render, zlib.crc32(f"{key}_{variant}_redesign".encode()) % 1_000_000, vprompt)
            pixelate_file(str(render), str(ASSETS_FINAL / f"{key}_{variant}.png"), variant=variant, key=palette_key(name))
        print(f"ok  {name}", flush=True)
    GENERATED_ART.write_text(json.dumps(dict(sorted(art.items())), indent=2))


if __name__ == "__main__":
    main()

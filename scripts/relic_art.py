"""Relic icons: relics_raw/* -> assets_temp/relics/srcN.stylized.png -> assets_final/relics/<slug>.png

The same two passes as creature sprites (see run_pipeline.py), with an object prompt:
  pass 1  FLUX.2 Klein redraws the reference as a pixel-art-flavored relic icon (prompts/relic.prompt.md,
          plus the relic's own art note from private/dex/_tools/relics.txt when it has one)
  pass 2  pixelate.py reduces it to an exact 48x48 sprite

Renders are keyed by source number (private/dex/_tools/relic_sources.json), so renaming a relic only redoes pass 2.
Resumable: existing renders and sprites are skipped unless --force.

    .venv/bin/python -m scripts.relic_art              # every relic in relics.txt
    .venv/bin/python -m scripts.relic_art --src 4 62   # just these sources
"""

from __future__ import annotations

import argparse
import json
import re
import time
import zlib
from pathlib import Path

from scripts.pixelate import pixelate_file
from scripts.run_pipeline import run_pass1

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "private" / "art" / "relics_raw"
SOURCES = ROOT / "private" / "dex" / "_tools" / "relic_sources.json"
RELICS = ROOT / "private" / "dex" / "_tools" / "relics.txt"
PROMPT = ROOT / "prompts" / "relic.prompt.md"
TEMP = ROOT / "private" / "art" / "assets_temp" / "relics"
FINAL = ROOT / "private" / "art" / "assets_final" / "relics"


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def load_relics() -> list[dict]:
    """relics.txt: src|Name|rarity|value|category|when|effect|flavor|art note (optional)"""
    out = []
    for line in RELICS.read_text().splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("|")]
        parts += [""] * (9 - len(parts))
        src, name, rarity, value, category, when, effect, flavor, art = parts[:9]
        out.append({"src": int(src), "name": name, "rarity": rarity, "value": int(value), "category": category,
                    "when": when, "effect": effect, "flavor": flavor, "art": art})
    return out


def render(src: int, art_note: str, out_name: str, force: bool) -> str:
    sources = json.loads(SOURCES.read_text())
    raw = RAW / sources[str(src)]
    TEMP.mkdir(parents=True, exist_ok=True)
    FINAL.mkdir(parents=True, exist_ok=True)
    temp = TEMP / f"src{src:03d}.stylized.png"
    final = FINAL / f"{out_name}.png"
    if final.exists() and temp.exists() and not force:
        return "skip"
    if not temp.exists() or force:
        prompt = PROMPT
        if art_note:
            prompt = TEMP / f"src{src:03d}.prompt.md"
            prompt.write_text(PROMPT.read_text() + f"\nThis object: {art_note}\n")
        run_pass1(raw, temp, zlib.crc32(f"relic{src}".encode()) % 1_000_000, prompt)
    pixelate_file(str(temp), str(final))
    return "done"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", type=int, nargs="*")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    if args.src:
        known = {r["src"]: r for r in load_relics()} if RELICS.exists() else {}
        jobs = [(s, known.get(s, {}).get("art", ""), slug(known[s]["name"]) if s in known else f"test_src{s:03d}")
                for s in args.src]
    else:
        jobs = [(r["src"], r["art"], slug(r["name"])) for r in load_relics()]
    t0 = time.time()
    for i, (src, art, name) in enumerate(jobs, 1):
        status = render(src, art, name, args.force)
        print(f"[{i}/{len(jobs)}] src{src:03d} {name}: {status} ({time.time() - t0:.0f}s)", flush=True)


if __name__ == "__main__":
    main()

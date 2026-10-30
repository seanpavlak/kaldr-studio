"""Mirror creatures left-to-right and toggle them in private/dex/_tools/facing.txt, so re-renders keep the new facing.

    .venv/bin/python scripts/flip_facing.py NAME [NAME ...]

Flips all three forms (base, Resonant, Aberrant). Rebuild their animations and the dex afterwards:
    .venv/bin/python scripts/animate.py NAME ... && .venv/bin/python private/dex/_tools/gen_dex.py && .venv/bin/python private/dex/_tools/build_viewer.py
"""
import glob
import json
import sys
from pathlib import Path

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent.parent
FACING = ROOT / "private" / "dex" / "_tools" / "facing.txt"


def main(names: list[str]) -> None:
    dex = {e["name"]: e for e in (json.loads(Path(f).read_text()) for f in glob.glob(str(ROOT / "private" / "dex" / "[0-9]*.json")))}
    unknown = [n for n in names if n not in dex]
    if unknown:
        sys.exit(f"unknown creatures: {unknown}")
    lines = FACING.read_text().splitlines()
    header = [l for l in lines if l.startswith("#") or not l.strip()]
    listed = [l.strip() for l in lines if l.strip() and not l.startswith("#")]
    for n in names:
        stem = dex[n]["index_name"]
        for suffix in ("", "_resonant", "_aberrant"):
            p = ROOT / "private" / "art" / "assets_final" / f"{stem}{suffix}.png"
            ImageOps.mirror(Image.open(p).convert("RGBA")).save(p)
        if n in listed:
            listed.remove(n)
            print(f"{n}: flipped (removed from facing.txt)")
        else:
            listed.append(n)
            print(f"{n}: flipped (added to facing.txt)")
    listed.sort(key=lambda n: dex[n]["dex_number"])
    FACING.write_text("\n".join(header) + "\n" + "\n".join(listed) + "\n")


if __name__ == "__main__":
    main(sys.argv[1:])

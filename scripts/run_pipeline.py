"""Batch pipeline: assets_raw/* -> assets_temp/*.stylized.png -> assets_final/*.png

Pass 1 (generative): FLUX.2 Klein 4B (via mflux) redesigns the reference art as a
stylized pixel-art-flavored illustration, guided by prompts/conversion.prompt.md.
Not expected to be pixel-perfect or the right size - that's pass 2's job.

Pass 2 (deterministic): scripts/pixelate.py forces the pass-1 output into an
exact 48x48 RGBA sprite with background removal, a small creature-only palette,
majority-vote cell sampling, speck cleanup, and a 1px black outline.

Resumable: files already present in assets_temp / assets_final are skipped
unless --force is passed. Each raw asset gets a stable slug recorded in
assets_temp/manifest.json so reruns don't drift.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import time
import zlib
from pathlib import Path

from scripts.pixelate import pixelate_file

ROOT = Path(__file__).resolve().parent.parent
ART = ROOT / "private" / "art"
ASSETS_RAW = ART / "assets_raw"
# Later drops of source art live in their own folders; their manifest keys and slugs are
# prefixed so filenames like "_ (10).jpeg" can repeat across folders.
EXTRA_RAW_DIRS = {ART / "assets_raw_2": "r2"}
ASSETS_TEMP = ART / "assets_temp"
ASSETS_FINAL = ART / "assets_final"
CONVERSION_PROMPT = ROOT / "prompts" / "conversion.prompt.md"
VARIANT_PROMPTS = {v: ROOT / "prompts" / f"variant_{v}.prompt.md" for v in ("resonant", "aberrant")}
RESONANT_HALO_PROMPT = ROOT / "prompts" / "variant_resonant_halo.prompt.md"
# Only a rare few Resonants get a halo; the list lives beside the prompts.
RESONANT_HALO = {line.strip() for line in (ROOT / "prompts" / "resonant_halo.txt").read_text().splitlines()
                 if line.strip() and not line.startswith("#")}
MANIFEST_PATH = ASSETS_TEMP / "manifest.json"

MODEL = "flux2-klein-4b"
PASS1_SIZE = 512  # the model needs room to draw eyes and shading; pass 2 does the 48x48 reduction
PASS1_STEPS = 8

VALID_EXTS = {".jpeg", ".jpg", ".png", ".webp"}


def load_manifest() -> dict:
    if MANIFEST_PATH.exists():
        return json.loads(MANIFEST_PATH.read_text())
    return {}


def save_manifest(manifest: dict) -> None:
    ASSETS_TEMP.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, ensure_ascii=False))


def sanitize_stem(name: str) -> str:
    stem = Path(name).stem
    ascii_stem = stem.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^A-Za-z0-9_-]+", "_", ascii_stem).strip("_")
    slug = re.sub(r"_+", "_", slug)
    return slug[:40] or "sprite"


def _looks_like_image(path: Path) -> bool:
    with open(path, "rb") as f:
        head = f.read(12)
    return head.startswith(b"\xff\xd8\xff") or head.startswith(b"\x89PNG") or head[8:12] == b"WEBP"


def list_raw_files() -> list[Path]:
    files = [p for p in sorted(ASSETS_RAW.iterdir()) if p.suffix.lower() in VALID_EXTS]
    for d in EXTRA_RAW_DIRS:
        if d.exists():
            # extra folders also accept images saved without a usable extension
            files += [p for p in sorted(d.iterdir()) if p.is_file() and not p.name.startswith(".")
                      and (p.suffix.lower() in VALID_EXTS or _looks_like_image(p))]
    return files


def redesigned_sources() -> set[str]:
    """Raw keys of creatures redesigned from a brief (private/dex/_tools/redesigns.txt); never regenerate these."""
    names = {line.split("|", 1)[0] for line in (ROOT / "private" / "dex" / "_tools" / "redesigns.txt").read_text().splitlines()
             if line.strip() and not line.startswith("#")}
    out = set()
    for f in (ROOT / "private" / "dex").glob("[0-9]*.json"):
        e = json.loads(f.read_text())
        if e["name"] in names and e.get("source_file"):
            out.add(e["source_file"])
    return out


def recolor_for(key: str) -> tuple[float, float, float] | None:
    """Palette shift for the creature drawn from this raw file, if any (private/dex/_tools/recolors.txt)."""
    shifts = {}
    for line in (ROOT / "private" / "dex" / "_tools" / "recolors.txt").read_text().splitlines():
        if line.strip() and not line.startswith("#"):
            name, shift, sat, *val = line.split("|")
            shifts[name] = (float(shift), float(sat), float(val[0]) if val else 1.0)
    for f in (ROOT / "private" / "dex").glob("[0-9]*.json"):
        e = json.loads(f.read_text())
        if e.get("source_file") == key and e["name"] in shifts:
            return shifts[e["name"]]
    return None


def raw_key(path: Path) -> str:
    """Manifest key: the bare filename for assets_raw, folder-qualified for extra folders."""
    return path.name if path.parent == ASSETS_RAW else f"{path.parent.name}/{path.name}"


def build_manifest(manifest: dict) -> dict:
    used_slugs = set(manifest.values())
    changed = False
    for path in list_raw_files():
        key = raw_key(path)
        if key in manifest:
            continue
        prefix = EXTRA_RAW_DIRS.get(path.parent)
        base = sanitize_stem(path.name)
        if prefix:
            base = f"{prefix}_{base}"
        slug = base
        i = 2
        while slug in used_slugs:
            slug = f"{base}_{i}"
            i += 1
        used_slugs.add(slug)
        manifest[key] = slug
        changed = True
    if changed:
        save_manifest(manifest)
    return manifest


def run_pass1(raw_path: Path, out_path: Path, seed: int, prompt: Path = CONVERSION_PROMPT) -> None:
    # mflux never overwrites: with an existing output it writes <name>_1.png, _2.png, ...
    # and pass 2 would silently keep reading the stale render.
    out_path.unlink(missing_ok=True)
    cmd = [
        "mflux-generate-flux2-edit",
        "--model", MODEL,
        "--image-paths", str(raw_path),
        "--prompt-file", str(prompt),
        "--width", str(PASS1_SIZE),
        "--height", str(PASS1_SIZE),
        "--steps", str(PASS1_STEPS),
        "--seed", str(seed),
        "--no-metadata",
        "--output", str(out_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True)


def process_one(raw_path: Path, slug: str, force: bool, variant: str | None = None) -> str:
    if variant:
        # Variants redraw the creature's own base render, so they stay the same creature.
        source = ASSETS_TEMP / f"{slug}.stylized.png"
        if not source.exists():
            raise FileNotFoundError(f"no base render {source.name}; run the base pass first")
        temp_path = ASSETS_TEMP / f"{slug}_{variant}.stylized.png"
        final_path = ASSETS_FINAL / f"{slug}_{variant}.png"
        prompt, seed_key = VARIANT_PROMPTS[variant], f"{slug}_{variant}"
        if variant == "resonant" and slug in RESONANT_HALO:
            prompt = RESONANT_HALO_PROMPT
    else:
        source = raw_path
        temp_path = ASSETS_TEMP / f"{slug}.stylized.png"
        final_path = ASSETS_FINAL / f"{slug}.png"
        prompt, seed_key = CONVERSION_PROMPT, slug

    if final_path.exists() and not force:
        return "skip"

    if not temp_path.exists() or force:
        seed = zlib.crc32(seed_key.encode()) % 1_000_000  # hash() is randomized per process
        run_pass1(source, temp_path, seed, prompt)
        shift = recolor_for(raw_key(raw_path)) if not variant else None
        if shift:
            from recolor import recolor_render  # palette-only change from private/dex/_tools/recolors.txt
            orig = temp_path.with_name(temp_path.name.replace(".stylized.png", ".stylized.orig.png"))
            orig.unlink(missing_ok=True)  # fresh render: recolor from it, not a stale original
            recolor_render(temp_path, *shift)

    # key the per-creature variant palette on the raw filename, which never changes (slugs can be renamed)
    pixelate_file(str(temp_path), str(final_path), variant=variant, key=raw_key(raw_path))
    return "ok"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None, help="Only process the first N raw assets")
    ap.add_argument("--force", action="store_true", help="Reprocess even if outputs already exist")
    ap.add_argument("--only", type=str, default=None, help="Only process raw filenames containing this substring")
    ap.add_argument("--variant", choices=sorted(VARIANT_PROMPTS), default=None,
                    help="Generate the Resonant or Aberrant variant from each base render instead of the base sprite")
    args = ap.parse_args()

    ASSETS_TEMP.mkdir(parents=True, exist_ok=True)
    ASSETS_FINAL.mkdir(parents=True, exist_ok=True)

    manifest = build_manifest(load_manifest())

    skip = redesigned_sources()
    raw_files = [p for p in list_raw_files() if raw_key(p) not in skip]
    if args.only:
        raw_files = [p for p in raw_files if args.only in p.name]
    if args.limit:
        raw_files = raw_files[: args.limit]

    total = len(raw_files)
    errors = []
    t0 = time.time()
    for i, raw_path in enumerate(raw_files, 1):
        slug = manifest[raw_key(raw_path)]
        try:
            status = process_one(raw_path, slug, args.force, args.variant)
            elapsed = time.time() - t0
            print(f"[{i}/{total}] {status:5s} {raw_path.name} -> {slug}.png  ({elapsed:.0f}s elapsed)")
        except subprocess.CalledProcessError as e:
            errors.append((raw_path.name, e.stderr[-500:] if e.stderr else str(e)))
            print(f"[{i}/{total}] FAIL  {raw_path.name}: {e.stderr[-200:] if e.stderr else e}")
        except Exception as e:  # noqa: BLE001
            errors.append((raw_path.name, str(e)))
            print(f"[{i}/{total}] FAIL  {raw_path.name}: {e}")

    print(f"\nDone. {total - len(errors)}/{total} succeeded in {time.time() - t0:.0f}s.")
    if errors:
        print(f"{len(errors)} failures:")
        for name, err in errors:
            print(f"  - {name}: {err}")


if __name__ == "__main__":
    main()

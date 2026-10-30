"""Generate art for dex entries that have no source image (missing evolution stages).

Each missing creature is drawn from its closest family member's pass-1 render plus the entry's
generation_prompt_notes, so it keeps the family look. Its Resonant and Aberrant forms then come
from the new base render, like every other creature. Outputs are named by index_name.

    .venv/bin/python scripts/generate_missing.py [--only NAME ...] [--force]
"""

from __future__ import annotations

import argparse
import glob
import json
import zlib
from pathlib import Path

from pixelate import pixelate_file
from redesign import palette_key
from run_pipeline import ASSETS_FINAL, ASSETS_TEMP, ROOT, VARIANT_PROMPTS, run_pass1

DEX = ROOT / "private" / "dex"
GENERATED_ART = DEX / "_tools" / "generated_art.json"  # creature name -> file key; survives re-indexing
MISSING_PROMPT = ROOT / "prompts" / "missing_stage.prompt.md"


def load_entries() -> list[dict]:
    return sorted((json.loads(Path(f).read_text()) for f in glob.glob(str(DEX / "[0-9]*.json"))), key=lambda e: e["dex_number"])


def reference_for(entry: dict, entries: list[dict]) -> dict:
    """Closest family member with art; ties go to the later (more detailed) stage."""
    stage = entry["evolution"]["stage"]
    family = [e for e in entries if e["family_id"] == entry["family_id"] and e["status"] == "has_art"]
    return min(family, key=lambda e: (abs(e["evolution"]["stage"] - stage), -e["evolution"]["stage"]))


def build_prompt(entry: dict, ref: dict) -> Path:
    stage, total = entry["evolution"]["stage"], entry["evolution"]["stages_total"]
    if stage < ref["evolution"]["stage"]:
        relation = f"its earlier, smaller, younger pre-evolution (stage {stage} of {total})"
    else:
        relation = f"its later, larger, more powerful evolution (stage {stage} of {total})"
    text = MISSING_PROMPT.read_text().format(relation=relation, notes=entry["generation_prompt_notes"])
    out = ASSETS_TEMP / f"{entry['index_name']}.prompt.md"
    out.write_text(text)
    return out


def generate(entry: dict, ref: dict, force: bool) -> None:
    art = json.loads(GENERATED_ART.read_text()) if GENERATED_ART.exists() else {}
    name = art.setdefault(entry["name"], entry["index_name"])
    GENERATED_ART.write_text(json.dumps(dict(sorted(art.items())), indent=2))
    ref_key = ref["sprite"].split("/")[-1][: -len(".png")]
    ref_render = ASSETS_TEMP / f"{ref_key}.stylized.png"
    base_render = ASSETS_TEMP / f"{name}.stylized.png"
    if force or not base_render.exists():
        run_pass1(ref_render, base_render, zlib.crc32(name.encode()) % 1_000_000, build_prompt(entry, ref))
    pixelate_file(str(base_render), str(ASSETS_FINAL / f"{name}.png"))
    for variant, prompt in VARIANT_PROMPTS.items():
        render = ASSETS_TEMP / f"{name}_{variant}.stylized.png"
        if force or not render.exists():
            run_pass1(base_render, render, zlib.crc32(f"{name}_{variant}".encode()) % 1_000_000, prompt)
        # no raw file exists for these, so the stable palette key is the creature id
        pixelate_file(str(render), str(ASSETS_FINAL / f"{name}_{variant}.png"), variant=variant, key=palette_key(entry["name"]))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", default=None, help="Creature names to generate")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    entries = load_entries()
    todo = [e for e in entries if e["status"] == "needs_generation" or (e["source_file"] is None and args.force)]
    if args.only:
        todo = [e for e in entries if e["name"] in args.only]
    for i, entry in enumerate(todo, 1):
        ref = reference_for(entry, entries)
        try:
            generate(entry, ref, args.force)
            print(f"[{i}/{len(todo)}] ok    {entry['name']} <- {ref['name']}", flush=True)
        except Exception as e:  # noqa: BLE001
            print(f"[{i}/{len(todo)}] FAIL  {entry['name']}: {e}", flush=True)


if __name__ == "__main__":
    main()

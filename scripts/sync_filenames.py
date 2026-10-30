"""Rename sprites and renders so every file is named by its creature's current index_name.

Run after regenerating the dex whenever dex numbers or names change. Files are found through
the dex's current sprite paths, renamed in two phases (so no rename can clobber another creature's
file), and the manifest, generated-art records and halo list are updated to match.
"""
import glob
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ART = ROOT / "private" / "art"
os.chdir(ROOT)
entries = [json.loads(Path(f).read_text()) for f in glob.glob("private/dex/[0-9]*.json")]
moves = {e["sprite"].split("/")[-1][:-4]: e["index_name"] for e in entries
         if e["sprite"] and e["sprite"].split("/")[-1][:-4] != e["index_name"]}
assert len(set(moves.values())) == len(moves)
pairs = []
for old, new in moves.items():
    for d, sufs in ((f"{ART}/assets_final", ["", "_resonant", "_aberrant"]),
                    (f"{ART}/assets_final/anim", ["_idle", "_resonant_idle", "_aberrant_idle"]),
                    (f"{ART}/assets_temp", [".stylized", "_resonant.stylized", "_aberrant.stylized", ".prompt.md"])):
        for s in sufs:
            exts = [""] if s.endswith(".md") else [".png", ".apng", ".json"] if d.endswith("anim") else [".png"]
            for ext in exts:
                src = f"{d}/{old}{s}{ext}"
                if os.path.exists(src):
                    pairs.append((src, f"{d}/{new}{s}{ext}"))
for src, _ in pairs:
    os.rename(src, src + ".sync")
for src, dst in pairs:
    assert not os.path.exists(dst), dst
    os.rename(src + ".sync", dst)
for path in (f"{ART}/assets_temp/manifest.json", "private/dex/_tools/generated_art.json"):
    data = json.loads(Path(path).read_text())
    Path(path).write_text(json.dumps({k: moves.get(v, v) for k, v in data.items()}, indent=2, ensure_ascii=False))
halo = Path("prompts/resonant_halo.txt")
halo.write_text("\n".join(l if l.startswith("#") or not l.strip() else moves.get(l.strip(), l.strip())
                          for l in halo.read_text().splitlines()) + "\n")
print(f"{len(moves)} creatures, {len(pairs)} files renamed")

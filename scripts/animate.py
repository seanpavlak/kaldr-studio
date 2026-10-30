"""Build looping idle animations for creatures from their finished 48x48 sprites.

Animations are pixel-honest: every move is exactly one pixel, built from three operations.
  breathe  remove one row so everything above it settles 1px (inside the legs, so they bend)
  lift     stretch a region up by 1px (ears, horns, crests, wingtips rustling)
  raise    move a region up by 1px, leaving the row below empty (a paw stepping off the ground)

A creature's idle is a list of keyframes naming which operations are active and how long to hold.
Every loop starts and ends on the unchanged rest frame.

Creatures listed in private/dex/_tools/animations.json use that hand-tuned spec (relative boxes).
Every other creature is analyzed automatically, per form:
  - legs: scanning up from the bottom, the rows where the silhouette splits into separate runs;
    the breath removes a row inside them, and each foot gets its own paw step
  - legless body plans (blob, serpentine, aquatic, cephalopod, amorphous) get a slow squash pulse
  - top corners (ears, horns, crests, wingtips) rustle, when there is headroom above them
The keyframe timeline comes from the normal form, so all three forms share frames and timing;
each form finds its own regions, and an operation a form lacks is simply skipped there.

Outputs in assets_final/anim/:
  <index_name>[_resonant|_aberrant]_idle.png   horizontal spritesheet (48*N x 48)
  <index_name>_idle.json                        frame count and per-frame durations

build_one() does the same analysis for a single sprite that is not in the dex.

    .venv/bin/python -m scripts.animate [NAME ...]
"""

from __future__ import annotations

import glob
import json
import sys
import zlib
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SPECS = ROOT / "private" / "dex" / "_tools" / "animations.json"
OUT = ROOT / "private" / "art" / "assets_final" / "anim"
FORMS = {"normal": "", "resonant": "_resonant", "aberrant": "_aberrant"}
LEGLESS = {"blob", "serpentine", "aquatic", "cephalopod", "amorphous"}
SIZE_TEMPO = {"tiny": 0.8, "small": 0.9, "medium": 1.0, "large": 1.15, "huge": 1.3, "colossal": 1.4}

Box = tuple[int, int, int, int]


# ---------- operations ----------
def bbox(a: np.ndarray) -> Box:
    ys, xs = np.where(a[..., 3] > 0)
    return xs.min(), ys.min(), xs.max(), ys.max()


def breathe(a: np.ndarray, row: int) -> np.ndarray:
    out = np.zeros_like(a)
    out[row + 1:] = a[row + 1:]          # below the removed row stays put (feet planted)
    out[1:row + 1] = a[0:row]            # rows above shift down one
    return out


def lift(a: np.ndarray, b: Box) -> np.ndarray:
    x0, y0, x1, y1 = b
    out = a.copy()
    region = a[y0:y1 + 1, x0:x1 + 1]
    target = out[y0 - 1:y1, x0:x1 + 1]
    solid = region[..., 3] > 0
    target[solid] = region[solid]
    return out


def raise_(a: np.ndarray, b: Box) -> np.ndarray:
    x0, y0, x1, y1 = b
    out = a.copy()
    out[y0 - 1:y1, x0:x1 + 1] = a[y0:y1 + 1, x0:x1 + 1]
    out[y1, x0:x1 + 1] = 0
    return out


def render(a: np.ndarray, regions: dict, key: dict) -> np.ndarray:
    frame = a
    after = regions.get("lift_after_breathe", False)
    lifts = [regions["lift"][n] for n in key.get("lift", []) if n in regions["lift"]]
    if not after:
        for b in lifts:
            frame = lift(frame, b)
    for name in key.get("raise", []):
        if name in regions["raise"]:
            frame = raise_(frame, regions["raise"][name])
    if key.get("breathe") and regions["breathe_row"] is not None:
        frame = breathe(frame, regions["breathe_row"])
        if after:  # no headroom at rest: the ears/crest can only flick while the body is settled
            for b in lifts:
                frame = lift(frame, b)
    return frame


# ---------- analysis ----------
def runs(row: np.ndarray) -> list[tuple[int, int]]:
    out, start = [], None
    for x, v in enumerate(row):
        if v and start is None:
            start = x
        if not v and start is not None:
            out.append((start, x - 1))
            start = None
    if start is not None:
        out.append((start, len(row) - 1))
    return out


def analyze(a: np.ndarray, shape: str) -> dict:
    """Find this sprite's breathing row, feet and top-corner features."""
    op = a[..., 3] > 0
    bx0, by0, bx1, by1 = bbox(a)
    w, h = bx1 - bx0, by1 - by0
    regions = {"breathe_row": None, "lift": {}, "raise": {}}

    # legs: the rows at the bottom where the silhouette is split into separate runs
    zone_top = by1 + 1
    for y in range(by1, by0 + h // 2, -1):
        if len(runs(op[y])) >= 2:
            zone_top = y
        else:
            break
    zone_h = by1 - zone_top + 1
    legged = shape not in LEGLESS and zone_h >= 3
    if legged:
        regions["breathe_row"] = zone_top + max(1, zone_h // 2)
        feet = sorted((r for r in runs(op[by1 - 1]) if r[1] - r[0] >= 2), key=lambda r: r[0])
        if len(feet) > 2:
            feet = [feet[0], feet[-1]]
        for i, (x0, x1) in enumerate(feet):
            col = op[:, x0:x1 + 1]
            foot_bottom = max(y for y in range(by1 + 1) if col[y].any())
            regions["raise"][f"paw{i + 1}"] = (x0, max(zone_top + 1, foot_bottom - 3), x1, foot_bottom)
    else:
        regions["breathe_row"] = round(by0 + 0.55 * h)

    # top corners rustle; a lift moves pixels one row higher, so a sprite already at the top margin
    # gets its lifts measured on the breathed frame (body settled 1px) and only flicks mid-breath
    top = by0
    if by0 < 2:
        regions["lift_after_breathe"] = True
        top = by0 + 1
    for name, (fx0, fx1) in {"left_top": (0.0, 0.3), "right_top": (0.7, 1.0)}.items():
        x0, x1 = round(bx0 + fx0 * w), round(bx0 + fx1 * w)
        y0, y1 = top, round(top + 0.4 * h)
        if op[y0 - (top - by0):y1 + 1 - (top - by0), x0:x1 + 1].sum() >= 6:
            regions["lift"][name] = (x0, y0, x1, y1)
    return regions


def rel_regions(a: np.ndarray, spec: dict) -> dict:
    """Hand-tuned spec (relative boxes) -> pixel regions for this sprite."""
    bx0, by0, bx1, by1 = bbox(a)
    w, h = bx1 - bx0, by1 - by0

    def px(r):
        return (round(bx0 + r[0] * w), round(by0 + r[1] * h), round(bx0 + r[2] * w), round(by0 + r[3] * h))

    return {"breathe_row": round(by0 + spec["breathe_row"] * h),
            "lift": {k: px(v) for k, v in spec.get("lift", {}).items()},
            "raise": {k: px(v) for k, v in spec.get("raise", {}).items()}}


def timeline(entry: dict, regions: dict) -> list[dict]:
    """Keyframes for an automatic idle: tempo by size, with a per-creature offset."""
    seed = zlib.crc32(entry["id"].encode())
    t = 360 * SIZE_TEMPO.get(entry["physical"]["size_class"], 1.0) * (0.9 + (seed % 21) / 100)

    def ms(f):
        return int(round(t * f / 10) * 10)

    lifts = sorted(regions["lift"])
    paws = sorted(regions["raise"])
    if seed % 2 and len(paws) == 2:
        paws.reverse()
    keys = [{"ms": ms(1.0)}]
    if lifts:
        keys.append({"ms": ms(0.5), "lift": lifts})
        keys.append({"ms": ms(0.7), "breathe": True, "lift": lifts})
    keys.append({"ms": ms(1.05), "breathe": True})
    if lifts:
        keys.append({"ms": ms(0.55), "breathe": True, "lift": lifts[-1:]})
    if paws:
        keys.append({"ms": ms(0.6)})
        for i, paw in enumerate(paws):
            keys.append({"ms": ms(0.47), "raise": [paw]})
            if i < len(paws) - 1:
                keys.append({"ms": ms(0.42)})
    elif lifts:
        keys.append({"ms": ms(0.7)})
        keys.append({"ms": ms(0.5), "lift": lifts[:1]})
    keys.append({"ms": ms(1.0)})
    if regions.get("lift_after_breathe"):
        # lifts only work mid-breath for this sprite: fold lift-only frames into the breath
        keys = [({**k, "breathe": True} if k.get("lift") and not k.get("breathe") else k) for k in keys]
    return keys


# ---------- build ----------
def build(entry: dict, spec: dict | None) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    stem = entry["index_name"]
    sprites = {form: np.array(Image.open(ROOT / "private" / "art" / "assets_final" / f"{stem}{suffix}.png").convert("RGBA"))
               for form, suffix in FORMS.items()}
    if spec:
        keys = spec["idle"]["keyframes"]
        regions = {form: rel_regions(a, spec["idle"]) for form, a in sprites.items()}
    else:
        shape = entry["physical"]["body_shape"]
        regions = {form: analyze(a, shape) for form, a in sprites.items()}
        keys = timeline(entry, regions["normal"])
    assert keys[0] == keys[-1] == {"ms": keys[0]["ms"]}, "the loop must start and end on the plain rest frame"
    for form, suffix in FORMS.items():
        frames = [render(sprites[form], regions[form], k) for k in keys]
        for f in frames:  # every frame keeps the 1px transparent margin
            assert f[0, :, 3].max() == f[-1, :, 3].max() == f[:, 0, 3].max() == f[:, -1, 3].max() == 0, stem
        assert (frames[0] == frames[-1]).all()
        Image.fromarray(np.concatenate(frames, axis=1), "RGBA").save(OUT / f"{stem}{suffix}_idle.png", optimize=True)
    meta = {"name": entry["name"], "animation": "idle", "frames": len(keys), "frame_ms": [k["ms"] for k in keys],
            "loop": True, "frame_size": [48, 48], "sheet_layout": "horizontal",
            "source": "hand-tuned" if spec else "auto"}
    (OUT / f"{stem}_idle.json").write_text(json.dumps(meta, indent=2))


def build_one(sprite: np.ndarray, seed_key: str, *, name: str = "sprite",
              shape: str = "unknown", size_class: str = "medium") -> tuple[list[np.ndarray], dict]:
    """Idle frames and timings for one sprite, with no dex entry and no other forms.

    shape defaults to a value outside the legless set, so the leg scan still runs.
    A silhouette with no split feet gets the squash pulse from analyze().
    """
    regions = analyze(sprite, shape)
    keys = timeline({"id": seed_key, "physical": {"size_class": size_class}}, regions)
    assert keys[0] == keys[-1] == {"ms": keys[0]["ms"]}, "the loop must start and end on the plain rest frame"
    frames = [render(sprite, regions, k) for k in keys]
    for f in frames:  # every frame keeps the 1px transparent margin
        assert f[0, :, 3].max() == f[-1, :, 3].max() == f[:, 0, 3].max() == f[:, -1, 3].max() == 0, name
    assert (frames[0] == frames[-1]).all()
    meta = {"name": name, "animation": "idle", "frames": len(keys), "frame_ms": [k["ms"] for k in keys],
            "loop": True, "frame_size": [int(sprite.shape[1]), int(sprite.shape[0])],
            "sheet_layout": "horizontal", "source": "auto"}
    return frames, meta


def main() -> None:
    specs = json.loads(SPECS.read_text())
    entries = sorted((json.loads(Path(f).read_text()) for f in glob.glob(str(ROOT / "private" / "dex" / "[0-9]*.json"))),
                     key=lambda e: e["dex_number"])
    names = set(sys.argv[1:])
    for old in OUT.glob("*.apng"):
        old.unlink()  # previews are no longer built; the dex animates the spritesheets
    done = 0
    for e in entries:
        if names and e["name"] not in names:
            continue
        build(e, specs.get(e["name"]))
        done += 1
    print(f"built idle animations for {done} creatures")


if __name__ == "__main__":
    main()

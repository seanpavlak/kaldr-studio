"""Deterministic pass 2: force a stylized image into a true 48x48 pixel-art sprite.

Not generative. Takes the pass-1 stylized illustration (any resolution, any
background) and produces an exact 48x48 RGBA PNG in the style of hand-made
creature-battler sprites: background removed, a small palette picked on the
creature only, every output pixel taken as the dominant palette color of its
source cell (never a blended average), stray pixels cleaned up, and a 1px black
outline around the silhouette (optionally wrapped in a white sticker border).
"""

from __future__ import annotations

import zlib

import numpy as np
from PIL import Image, ImageEnhance
from rembg import remove, new_session

CANVAS = 48
PALETTE_COLORS = 14
SUPERSAMPLE = 4  # source pixels per output pixel when picking cell colors
ALPHA_COVERAGE = 0.35  # fraction of a cell that must be opaque to keep the pixel
DARK_BIAS = 3.0  # extra vote weight for dark colors so eyes / inner lines survive
MARGIN = 1  # transparent pixels kept between the outline and the canvas edge
SATURATION = 1.25
CONTRAST = 1.1
OUTLINE_RGB = (0, 0, 0)
STICKER_RGB = (255, 255, 255)
STICKER = False  # add a white sticker border outside the black outline

_session = None


def _get_session():
    global _session
    if _session is None:
        _session = new_session("birefnet-general")  # MIT; matches BRIA RMBG-2.0, which is non-commercial
    return _session


def _cutout(img: Image.Image) -> Image.Image:
    """Return an RGBA image with the background removed."""
    rgba = img.convert("RGBA")
    # If the source already carries real transparency, trust it and skip rembg.
    alpha = np.array(rgba.split()[3])
    if alpha.min() < 250:
        return rgba
    return remove(rgba, session=_get_session())


def _bbox(alpha: np.ndarray) -> tuple[int, int, int, int]:
    ys, xs = np.where(alpha > 127)
    if len(xs) == 0:
        return 0, 0, alpha.shape[1], alpha.shape[0]
    return xs.min(), ys.min(), xs.max() + 1, ys.max() + 1


def _neighbors(mask: np.ndarray, diagonal: bool) -> np.ndarray:
    """Count of True neighbors for each cell of a boolean mask."""
    p = np.pad(mask, 1).astype(np.uint8)
    n = p[:-2, 1:-1] + p[2:, 1:-1] + p[1:-1, :-2] + p[1:-1, 2:]
    if diagonal:
        n = n + p[:-2, :-2] + p[:-2, 2:] + p[2:, :-2] + p[2:, 2:]
    return n


def _dilate_mask(mask: np.ndarray) -> np.ndarray:
    """1-pixel 4-connected dilation of a boolean mask."""
    return mask | (_neighbors(mask, diagonal=False) > 0)


def _clean_mask(mask: np.ndarray) -> np.ndarray:
    """Drop lone specks and fill pinholes so the silhouette reads as solid."""
    n8 = _neighbors(mask, diagonal=True)
    mask = mask & (n8 >= 2)
    n4 = _neighbors(mask, diagonal=False)
    return mask | (n4 >= 3)


def _fit_palette(pixels: np.ndarray, k: int) -> np.ndarray:
    """Pick k colors for the opaque creature pixels only (no background bleed)."""
    strip = Image.fromarray(pixels.reshape(1, -1, 3).astype(np.uint8), "RGB")
    pal_img = strip.quantize(colors=k, method=Image.Quantize.MEDIANCUT, kmeans=4)
    pal = np.array(pal_img.getpalette()[: k * 3], dtype=np.int32).reshape(-1, 3)
    return pal


def _nearest(rgb: np.ndarray, pal: np.ndarray) -> np.ndarray:
    d = ((rgb[..., None, :].astype(np.int32) - pal) ** 2).sum(-1)
    return d.argmin(-1)


def _despeckle(idx: np.ndarray, mask: np.ndarray, passes: int = 2) -> np.ndarray:
    """Replace pixels whose color appears in none of their 8 neighbors."""
    h, w = idx.shape
    for _ in range(passes):
        out = idx.copy()
        for y in range(h):
            for x in range(w):
                if not mask[y, x]:
                    continue
                y0, y1, x0, x1 = max(y - 1, 0), min(y + 2, h), max(x - 1, 0), min(x + 2, w)
                win = idx[y0:y1, x0:x1][mask[y0:y1, x0:x1]]
                same = (win == idx[y, x]).sum() - 1
                if same == 0 and len(win) > 1:
                    vals, counts = np.unique(win[win != idx[y, x]], return_counts=True)
                    out[y, x] = vals[counts.argmax()]
        idx = out
    return idx


def _fill_holes(cutout: Image.Image, original: Image.Image) -> Image.Image:
    """Put back regions the background remover cut out of the body's interior (white stripes or
    patches on a white background), taking their colours from the original render."""
    from scipy.ndimage import binary_fill_holes
    a = np.array(cutout)
    solid = a[..., 3] > 128
    holes = binary_fill_holes(solid) & ~solid
    a[holes, :3] = np.array(original.convert("RGB"))[holes]
    a[holes, 3] = 255
    return Image.fromarray(a)


def pixelate(img: Image.Image, sticker: bool = STICKER, fill_holes: bool = False, *,
              canvas: int = CANVAS, palette_colors: int = PALETTE_COLORS,
              saturation: float = SATURATION, contrast: float = CONTRAST,
              alpha_coverage: float = ALPHA_COVERAGE, dark_bias: float = DARK_BIAS,
              outline: bool = True) -> Image.Image:
    """Convert a stylized illustration into an exact canvas-sized sprite.

    Defaults match the batch pipeline. The studio passes other values from its render controls.
    """
    cutout = _cutout(img)
    if fill_holes:
        cutout = _fill_holes(cutout, img)
    rgb = ImageEnhance.Contrast(ImageEnhance.Color(cutout.convert("RGB")).enhance(saturation)).enhance(contrast)
    cutout = Image.merge("RGBA", (*rgb.split(), cutout.split()[3]))

    x0, y0, x1, y1 = _bbox(np.array(cutout.split()[3]))
    cropped = cutout.crop((x0, y0, x1, y1))

    border = 2 if sticker else 1
    target = canvas - 2 * (border + MARGIN)
    w, h = cropped.size
    scale = target / max(w, h)
    out_w, out_h = max(1, round(w * scale)), max(1, round(h * scale))

    # Resample to SUPERSAMPLE x the output grid, then decide each output pixel
    # from its SUPERSAMPLE x SUPERSAMPLE cell by majority vote.
    ss = SUPERSAMPLE
    big = np.array(cropped.resize((out_w * ss, out_h * ss), Image.LANCZOS))
    big_rgb, big_a = big[..., :3], big[..., 3] > 127

    pal = _fit_palette(big_rgb[big_a], palette_colors)
    big_idx = _nearest(big_rgb, pal)

    cells_idx = big_idx.reshape(out_h, ss, out_w, ss).transpose(0, 2, 1, 3).reshape(out_h, out_w, ss * ss)
    cells_a = big_a.reshape(out_h, ss, out_w, ss).transpose(0, 2, 1, 3).reshape(out_h, out_w, ss * ss)

    small_mask = cells_a.mean(-1) >= alpha_coverage
    luma = pal @ np.array([0.299, 0.587, 0.114]) / 255
    weights = 1 + dark_bias * (1 - luma) ** 2
    small_idx = np.zeros((out_h, out_w), dtype=np.int64)
    for y in range(out_h):
        for x in range(out_w):
            votes = cells_idx[y, x][cells_a[y, x]]
            if len(votes):
                small_idx[y, x] = np.bincount(votes, weights=weights[votes], minlength=len(pal)).argmax()

    mask = np.zeros((canvas, canvas), dtype=bool)
    idx = np.zeros((canvas, canvas), dtype=np.int64)
    ox, oy = (canvas - out_w) // 2, (canvas - out_h) // 2
    mask[oy : oy + out_h, ox : ox + out_w] = small_mask
    idx[oy : oy + out_h, ox : ox + out_w] = small_idx

    mask = _clean_mask(mask)
    idx = _despeckle(idx, mask)

    out = np.zeros((canvas, canvas, 4), dtype=np.uint8)
    out[mask, :3] = pal[idx[mask]]
    out[mask, 3] = 255

    filled = mask
    if outline:
        ring = _dilate_mask(mask) & ~mask
        out[ring] = (*OUTLINE_RGB, 255)
        filled = mask | ring
    if sticker:
        outer = _dilate_mask(filled) & ~filled
        out[outer] = (*STICKER_RGB, 255)

    result = Image.fromarray(out, mode="RGBA")
    assert result.size == (canvas, canvas)
    return result


# Variant palette filters, applied to the finished 48x48 sprite (the variant artwork changes the
# surface or adds mutations; the filter sets the palette). Settings are picked per creature from a
# stable hash of its key, so variants differ from each other but never change between runs.
RESONANT_SHIFTS = [0.0, 0.08, -0.08, 0.16, -0.16, 0.3, -0.3, 0.5]
IRIDESCENT = [(255, 150, 214), (178, 140, 255), (120, 220, 255), (150, 255, 210), (255, 214, 130)]  # pink violet cyan mint gold
ABERRANT_GLOWS = [(184, 255, 58), (255, 36, 64), (196, 64, 255)]  # acid green, blood red, toxic violet
VARIANT_OUTLINES = {"resonant": (0, 229, 255), "aberrant": (74, 0, 22)}  # neon cyan, crimson


def _hsv(rgb: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    hsv = np.array(Image.fromarray(rgb).convert("HSV")).astype(np.float32) / 255
    return hsv[..., 0], hsv[..., 1], hsv[..., 2]


def _rgb(h: np.ndarray, s_: np.ndarray, v: np.ndarray) -> np.ndarray:
    hsv = (np.dstack([h % 1.0, np.clip(s_, 0, 1), np.clip(v, 0, 1)]) * 255).astype(np.uint8)
    return np.array(Image.fromarray(hsv, "HSV").convert("RGB")).astype(np.float32)


def apply_variant(img: Image.Image, variant: str, key: str = "") -> Image.Image:
    seed = zlib.crc32(f"{key}:{variant}".encode())
    rgba = np.array(img.convert("RGBA"))
    opaque = rgba[..., 3] > 0
    # outline = the black ring touching transparency; beyond the canvas edge counts as transparent
    clear = np.pad(~opaque, 1, constant_values=True)
    touches_clear = clear[:-2, 1:-1] | clear[2:, 1:-1] | clear[1:-1, :-2] | clear[1:-1, 2:]
    outline = opaque & np.all(rgba[..., :3] == OUTLINE_RGB, axis=-1) & touches_clear
    body = opaque & ~outline
    h, s_, v = _hsv(rgba[..., :3])

    if variant == "resonant":
        # the Resonant art is already iridescent; a per-creature hue shift keeps them from all
        # landing on the same pastel palette, and a faint pearl sheen survives the reduction
        shift = RESONANT_SHIFTS[seed % len(RESONANT_SHIFTS)]
        shifted = _rgb(h + shift, s_ * 1.05, v)
        yy, xx = np.mgrid[0:rgba.shape[0], 0:rgba.shape[1]]
        band = ((xx + yy) // 3 + seed // 7) % len(IRIDESCENT)
        pearl = np.array(IRIDESCENT, dtype=np.float32)[band]
        light = np.clip((v - 0.7) / 0.3, 0, 1)[..., None] * 0.25
        out_rgb = shifted * (1 - light) + pearl * light
    else:
        # the Aberrant art is already dark; lift the deepest shadows just enough to keep detail at
        # 48x48, and burn its glowing parts in this creature's color
        out_rgb = _rgb(h, s_, 0.1 + v * 0.95)
        glow = (v > 0.75) & (s_ > 0.45)
        out_rgb[glow] = ABERRANT_GLOWS[seed % len(ABERRANT_GLOWS)]

    out = rgba.copy()
    out[body, :3] = np.clip(out_rgb[body], 0, 255).astype(np.uint8)
    out[outline, :3] = VARIANT_OUTLINES[variant]
    return Image.fromarray(out, "RGBA")


_LISTS: dict[str, set[str]] = {}


def _listed(dst_path: str, list_name: str) -> bool:
    """True when the creature an output sprite belongs to is named in private/dex/_tools/<list_name>."""
    import re
    from pathlib import Path
    if list_name not in _LISTS:
        p = Path(__file__).resolve().parent.parent / "private" / "dex" / "_tools" / list_name
        names = [l.strip() for l in p.read_text().splitlines() if l.strip() and not l.startswith("#")] if p.exists() else []
        _LISTS[list_name] = {re.sub(r"[^a-z0-9]+", "_", n.lower()).strip("_") for n in names}
    stem = re.sub(r"^\d+_", "", Path(dst_path).stem)
    stem = re.sub(r"_(resonant|aberrant)$", "", stem)
    return stem in _LISTS[list_name]


def _faces_left(dst_path: str) -> bool:
    """Creatures in facing.txt face left in their art, so their sprites get mirrored."""
    return _listed(dst_path, "facing.txt")


def pixelate_file(src_path: str, dst_path: str, sticker: bool = STICKER, variant: str | None = None, key: str = "") -> None:
    img = Image.open(src_path)
    result = pixelate(img, sticker=sticker, fill_holes=_listed(dst_path, "fill_holes.txt"))
    if variant:
        result = apply_variant(result, variant, key)
    if _faces_left(dst_path):  # every creature faces right in the autobattle lineup
        result = result.transpose(Image.FLIP_LEFT_RIGHT)
    result.save(dst_path)


if __name__ == "__main__":
    import sys

    pixelate_file(sys.argv[1], sys.argv[2], sticker="--sticker" in sys.argv[3:])
    print(f"wrote {sys.argv[2]}")

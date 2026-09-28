"""Typography: renders text cards into full-frame coverage masks with Pillow."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

FONTS = Path(__file__).resolve().parents[1] / "assets" / "fonts"

STYLES = {
    # kind: (font file, weight, size as fraction of frame height)
    "card": ("Jost-Variable.ttf", 340, 0.032),
    "title": ("Jost-Variable.ttf", 400, 0.056),
}
SUPERSAMPLE = 3


@lru_cache(maxsize=8)
def _font(file: str, weight: int, px: int) -> ImageFont.FreeTypeFont:
    f = ImageFont.truetype(str(FONTS / file), px)
    try:
        f.set_variation_by_axes([weight])
    except OSError:
        pass  # static font / no variation support: keep default weight
    return f


@lru_cache(maxsize=64)
def _layer(kind: str, text: str, track_q: int, w: int, h: int) -> np.ndarray:
    file, weight, size = STYLES[kind]
    tracking = track_q / 1000.0
    ss = SUPERSAMPLE
    px = max(8, int(round(size * h * ss)))
    font = _font(file, weight, px)
    # manual letter spacing (trailer typography uses very wide tracking)
    adv = [font.getlength(ch) for ch in text]
    spacing = tracking * px
    total = sum(adv) + spacing * (len(text) - 1)
    W, H = w * ss, h * ss
    img = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(img)
    x = (W - total) / 2.0
    # optical vertical centre using cap height
    top, bottom = font.getbbox("H")[1], font.getbbox("H")[3]
    y = H / 2.0 - (top + bottom) / 2.0
    for ch, a in zip(text, adv):
        d.text((x, y), ch, fill=255, font=font)
        x += a + spacing
    img = img.resize((w, h), Image.Resampling.LANCZOS)
    return np.asarray(img, dtype=np.uint8)


def text_layer(P: dict, w: int, h: int):
    """Returns (mask, cache_key) for the frame, or (None, None)."""
    spec = P.get("text")
    if not spec or P.get("text_opacity", 0.0) <= 0.0:
        return None, None
    kind, text = spec
    track_q = int(round(P.get("text_track", 0.4) * 1000 / 4)) * 4  # quantise for caching
    key = (kind, text, track_q, w, h)
    return _layer(kind, text, track_q, w, h), key

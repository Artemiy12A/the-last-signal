"""Title typography, drawn at 2x and downsampled; restrained glow, tracked capitals."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FONT = ROOT / "assets" / "fonts" / "Jost-Variable.ttf"


@lru_cache(maxsize=8)
def _font(path: str, size: int, weight: int | None):
    f = ImageFont.truetype(path, size)
    if weight is not None:
        try:
            f.set_variation_by_axes([weight])
        except Exception:
            pass
    return f


def render_text_mask(W, H, text, font=str(DEFAULT_FONT), size=0.034, tracking=0.62, y=0.5,
                     weight=300, ss=2) -> np.ndarray:
    """Alpha mask (H,W) of centred tracked text. size = cap height as fraction of frame width."""
    WW, HH = W * ss, H * ss
    px = int(size * W * ss * 1.45)
    f = _font(font, px, weight)
    img = Image.new("L", (WW, HH), 0)
    d = ImageDraw.Draw(img)
    track = tracking * px
    widths = [d.textlength(ch, font=f) for ch in text]
    total = sum(widths) + track * (len(text) - 1)
    x = (WW - total) / 2
    asc, desc = f.getmetrics()
    yy = y * HH - (asc - desc * 0.2) / 2
    for ch, w in zip(text, widths):
        d.text((x, yy), ch, font=f, fill=255)
        x += w + track
    img = img.resize((W, H), Image.LANCZOS)
    return np.asarray(img, dtype=np.float32) / 255.0


def draw_title(enc: np.ndarray, text: str, opacity: float = 1.0, glow: float = 0.25, color=(0.92, 0.9, 0.86),
               **kw) -> np.ndarray:
    H, W = enc.shape[:2]
    m = render_text_mask(W, H, text, **kw)
    if glow > 0:
        g = np.asarray(Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(W * 0.004)),
                       dtype=np.float32) / 255.0
        g2 = np.asarray(Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(W * 0.02)),
                        dtype=np.float32) / 255.0
        halo = (g * 0.6 + g2 * 0.4) * glow
    else:
        halo = 0
    col = np.asarray(color, np.float32)
    a = np.clip(m * opacity, 0, 1)[..., None]
    out = enc * (1 - a) + col * a
    out = out + (np.asarray(halo)[..., None] if np.ndim(halo) else 0) * opacity * col * 0.5
    return np.clip(out, 0, 1)


def draw_ring(enc: np.ndarray, opacity: float, radius: float = 0.3, width: float = 0.0016, color=(1.0, 0.8, 0.55),
              y: float = 0.5) -> np.ndarray:
    """A barely-there photon ring behind the title: a thin circle (radius as a fraction of frame height),
    softened, added on top of black."""
    if opacity <= 0:
        return enc
    H, W = enc.shape[:2]
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    r = np.hypot(xx - W / 2, yy - y * H) / H
    w = max(width, 0.5 / H)
    ring = np.exp(-0.5 * ((r - radius) / w) ** 2)
    glow = np.exp(-0.5 * ((r - radius) / (w * 8)) ** 2) * 0.25
    # the Doppler-bright side on the left, as in the film
    side = 0.65 + 0.35 * np.clip((W / 2 - xx) / (radius * H), -1, 1)
    add = (ring + glow) * side * opacity
    return np.clip(enc + add[..., None] * np.asarray(color, np.float32), 0, 1)

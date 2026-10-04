"""Poster (2:3) and cover (9:16) from a real frame of the final film, typeset with the film's own title
renderer (Jost, tracked capitals, the red point of the motif). No generated imagery: the picture is a
frame of the release MP4, at 1:1 pixel scale (never upscaled).

  python production/tools/make_posters.py --video reference/final/THE_LAST_SIGNAL.mp4 [--t 52.0]
  -> production/out/posters/THE_LAST_SIGNAL_poster_2x3.{png,pdf}, THE_LAST_SIGNAL_cover_9x16.{png,pdf}
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "production"))

from comp.titles import draw_title  # noqa: E402

TITLE = "THE LAST SIGNAL"
TAGLINE = "SOME SIGNALS ARE ECHOES"
INK = (0.92, 0.9, 0.86)          # the film's title colour
MUTED = (0.55, 0.53, 0.5)
RED = np.array([1.0, 0.3, 0.16], np.float32)


def frame(video: Path, t: float) -> np.ndarray:
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", str(video), "-frames:v", "1",
                          "-f", "rawvideo", "-pix_fmt", "rgb48le", "-"], capture_output=True, check=True).stdout
    probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                            "-of", "csv=p=0", str(video)], capture_output=True, text=True, check=True).stdout
    w, h = map(int, probe.strip().split(","))
    return np.frombuffer(raw, np.uint16).reshape(h, w, 3).astype(np.float32) / 65535.0


def place_band(canvas: np.ndarray, img: np.ndarray, cy: float, feather: float):
    """Composite a frame across the canvas, centred at height cy. The star field dissolves into black over
    `feather` of the frame height at top and bottom; the disk (a luminance key) keeps full strength."""
    from PIL import ImageFilter
    H, W = canvas.shape[:2]
    h, w = img.shape[:2]
    x0 = (w - W) // 2
    img = img[:, x0:x0 + W]
    y0 = int(round(cy * H - h / 2))
    n = int(feather * h)
    k = np.arange(n, dtype=np.float32) / n
    ramp = np.ones(h, np.float32)
    ramp[:n] = k * k * (3 - 2 * k)
    ramp[-n:] = ramp[:n][::-1]
    lum = img @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    key = np.clip((lum - 0.06) / 0.18, 0, 1)
    key = np.asarray(Image.fromarray((key * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(h * 0.02)),
                     np.float32) / 255.0
    edge = np.minimum(np.arange(h), np.arange(h)[::-1]).astype(np.float32) / max(h * 0.015, 1)
    hard = np.clip(edge, 0, 1)[:, None]               # the frame's own edge is never shown hard
    alpha = np.clip(np.maximum(ramp[:, None], key), 0, 1) * hard
    canvas[y0:y0 + h] = canvas[y0:y0 + h] * (1 - alpha[..., None]) + img * alpha[..., None]


def red_point(canvas: np.ndarray, x: float, y: float, r: float):
    H, W = canvas.shape[:2]
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    d2 = ((xx - x * W) ** 2 + (yy - y * H) ** 2) / (r * W) ** 2
    core = np.exp(-0.5 * d2)
    halo = np.exp(-0.5 * d2 / 16.0) * 0.18
    canvas += (core + halo)[..., None] * RED
    np.clip(canvas, 0, 1, out=canvas)


def grain(canvas: np.ndarray, amount: float, seed: int):
    rng = np.random.default_rng(seed)
    n = rng.normal(0, amount, canvas.shape[:2]).astype(np.float32)[..., None]
    np.clip(canvas + n, 0, 1, out=canvas)


def compose(img: np.ndarray, W: int, H: int, band_cy: float, title_y: float, title_size: float,
            tag_y: float, tag_size: float, seed: int) -> np.ndarray:
    c = np.zeros((H, W, 3), np.float32)
    place_band(c, img, band_cy, feather=0.3)
    grain(c, 0.004, seed)
    c = draw_title(c, TAGLINE, glow=0.0, color=MUTED, size=tag_size, tracking=0.62, weight=400, y=tag_y)
    c = draw_title(c, TITLE, glow=0.32, color=INK, size=title_size, tracking=0.5, weight=500, y=title_y)
    red_point(c, 0.5, title_y + 0.045 * W / H, 0.0032)
    return c


def save(c: np.ndarray, base: Path, dpi: int):
    im = Image.fromarray((np.clip(c, 0, 1) * 255 + 0.5).astype(np.uint8))
    im.save(base.with_suffix(".png"), optimize=True)
    im.save(base.with_suffix(".pdf"), resolution=dpi)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", type=Path, required=True)
    ap.add_argument("--t", type=float, default=52.0, help="film time of the still (S10, the reveal)")
    ap.add_argument("--out", type=Path, default=ROOT / "production" / "out" / "posters")
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    img = frame(a.video, a.t)
    h, w = img.shape[:2]
    # 2:3 poster at the film's width: the whole frame, wings and all
    poster = compose(img, w, w * 3 // 2, band_cy=0.40, title_y=0.70, title_size=0.032, tag_y=0.13,
                     tag_size=0.0105, seed=1)
    save(poster, a.out / "THE_LAST_SIGNAL_poster_2x3", dpi=200)
    # 9:16 cover, 1080 wide: the frame's centre at 1:1, the disk running off both edges
    cover = compose(img, 1080, 1920, band_cy=0.40, title_y=0.69, title_size=0.034, tag_y=0.12,
                    tag_size=0.0135, seed=2)
    save(cover, a.out / "THE_LAST_SIGNAL_cover_9x16", dpi=144)
    print("->", *sorted(p.name for p in a.out.iterdir()))


if __name__ == "__main__":
    main()

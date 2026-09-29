"""THE LAST SIGNAL compositor: scene-linear layers in, graded display frame out.

Order (per docs/research_sota.md §0.10):
  per-layer gains/tints -> depth of field (oval bokeh) on the far plates -> ship over plates ->
  foreground layers -> lens: veiling glare + energy-conserving bloom + anamorphic streaks ->
  halation -> distortion + edge chromatic aberration -> vignette -> white balance / saturation ->
  AgX display transform -> display grade -> signal interference -> grain -> titles -> fade.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from scipy import ndimage, signal

from .tonemap import agx, srgb_encode

LUMA = np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)


# ------------------------------------------------------------------ parameters
@dataclass
class CompParams:
    exposure: float = 0.0                     # EV applied to everything
    gains: dict = field(default_factory=dict)  # per-layer scalar or rgb gain: disk, haze, sky, stars, ship, ship_emit, fg
    white: tuple = (1.0, 1.0, 1.0)            # white-balance multipliers (linear)
    saturation: float = 1.0                   # linear saturation around luminance
    coc_px: float = 0.0                       # blur-circle diameter (px) for the far plates (DOF)
    bokeh_ratio: float = 2.0                  # anamorphic oval: height / width
    bloom: float = 0.035                      # energy-conserving bloom mix
    glare: float = 0.012                      # very wide veiling glare
    streak: float = 0.06                      # anamorphic streak gain
    streak_threshold: float = 24.0            # linear threshold (x mid grey 0.18 ~ 130x)
    streak_len: float = 220.0                 # px (sigma of the horizontal blur)
    streak_tint: tuple = (0.75, 0.85, 1.0)
    halation: float = 0.05
    halation_threshold: float = 1.5
    ca: float = 1.2                           # px of R/B separation at the frame corner
    distortion: float = 0.015                 # horizontal barrel
    vignette: float = 0.28
    punch: float = 0.12                       # AgX look contrast
    look_sat: float = 1.05
    lift: float = 0.0
    gamma: float = 1.0
    gain: float = 1.0
    black_point: float = 0.004                # display-space black crush (deep blacks)
    grain: float = 0.022
    grain_size: float = 0.9
    interference: float = 0.0                 # 0..1 from the EDL
    fade: float = 1.0                         # 0 = black
    seed: int = 0
    title: dict | None = None
    sprites: list | None = None               # point lights in the far plate: {x, y (0..1), rgb, sigma_px}


# ------------------------------------------------------------------ helpers
def _blur(img: np.ndarray, sigma: float) -> np.ndarray:
    """Gaussian blur of an (H,W,3) image; large sigmas go through a downsampled pyramid."""
    if sigma < 0.3:
        return img
    if sigma <= 12:
        return ndimage.gaussian_filter(img, (sigma, sigma, 0), mode="nearest")
    f = int(2 ** math.floor(math.log2(sigma / 6)))
    f = max(1, f)
    H, W = img.shape[:2]
    h, w = (H + f - 1) // f, (W + f - 1) // f
    pad = np.pad(img, ((0, h * f - H), (0, w * f - W), (0, 0)), mode="edge")
    small = pad.reshape(h, f, w, f, img.shape[2]).mean((1, 3))
    small = ndimage.gaussian_filter(small, (sigma / f, sigma / f, 0), mode="nearest")
    up = ndimage.zoom(small, (f, f, 1), order=1)[:H, :W]
    return up


def _hblur(img: np.ndarray, sigma: float) -> np.ndarray:
    f = 4
    H, W = img.shape[:2]
    w = (W + f - 1) // f
    pad = np.pad(img, ((0, 0), (0, w * f - W), (0, 0)), mode="edge")
    small = pad.reshape(H, w, f, img.shape[2]).mean(2)
    small = ndimage.gaussian_filter1d(small, sigma / f, axis=1, mode="constant")
    return ndimage.zoom(small, (1, f, 1), order=1)[:, :W]


def oval_kernel(diam_px: float, ratio: float) -> np.ndarray:
    """Anamorphic bokeh: an ellipse ratio x taller than wide, soft edge, slightly brighter rim."""
    w = max(diam_px / ratio, 1.0)
    h = max(diam_px, 1.0)
    rx, ry = w / 2, h / 2
    X = int(math.ceil(rx)) + 2
    Y = int(math.ceil(ry)) + 2
    y, x = np.mgrid[-Y:Y + 1, -X:X + 1].astype(np.float32)
    d = np.sqrt((x / rx) ** 2 + (y / ry) ** 2)
    k = np.clip((1.0 - d) * max(rx, 1.0), 0, 1)          # ~1 px soft edge
    k *= 0.85 + 0.15 * np.clip(d, 0, 1) ** 4             # gentle rim
    return (k / k.sum()).astype(np.float32)


def dof(img: np.ndarray, coc: float, ratio: float) -> np.ndarray:
    if coc < 1.2:
        return img
    k = oval_kernel(coc, ratio)
    out = np.empty_like(img)
    for c in range(3):
        out[..., c] = signal.fftconvolve(img[..., c], k, mode="same")
    return np.maximum(out, 0)


def lens_remap(img: np.ndarray, distortion: float, ca: float) -> np.ndarray:
    """Horizontal-leaning barrel distortion and radial chromatic aberration (edges only)."""
    if distortion == 0 and ca == 0:
        return img
    H, W = img.shape[:2]
    y, x = np.mgrid[0:H, 0:W].astype(np.float32)
    cx, cy = (W - 1) / 2, (H - 1) / 2
    nx, ny = (x - cx) / cx, (y - cy) / cx          # normalised by half-width
    r2 = nx * nx + ny * ny
    out = np.empty_like(img)
    for c, sgn in ((0, 1.0), (1, 0.0), (2, -1.0)):
        k = distortion * r2 + sgn * (ca / cx) * r2 / max(1.0 + (H / W) ** 2, 1e-6)
        sx = cx + (x - cx) * (1 + k * 1.0)
        sy = cy + (y - cy) * (1 + k * 0.6)
        out[..., c] = ndimage.map_coordinates(img[..., c], [sy, sx], order=1, mode="nearest")
    return out


def vignette_mask(H, W, amount):
    y, x = np.mgrid[0:H, 0:W].astype(np.float32)
    nx, ny = (x - (W - 1) / 2) / (W / 2), (y - (H - 1) / 2) / (W / 2)
    r2 = nx * nx + ny * ny
    return (1.0 - amount * np.clip(r2, 0, 2) ** 1.5 / 1.0).clip(0.2, 1)[..., None]


def grain(disp: np.ndarray, amount: float, size: float, seed: int) -> np.ndarray:
    if amount <= 0:
        return disp
    H, W = disp.shape[:2]
    rng = np.random.default_rng(seed * 7919 + 13)
    n = rng.standard_normal((H, W)).astype(np.float32)
    n = ndimage.gaussian_filter(n, size * 0.6)
    n /= n.std() + 1e-6
    c = rng.standard_normal((H, W, 3)).astype(np.float32)
    c = ndimage.gaussian_filter(c, (size * 0.9, size * 0.9, 0))
    c /= c.std() + 1e-6
    L = (disp @ LUMA)[..., None]
    # film-like response: strongest in the mid-tones, less in deep shadow and highlights
    w = (4.0 * L * (1.0 - L)).clip(0, 1) ** 0.8 + 0.08 * (L > 0.002)
    g = amount * w * (n[..., None] * 0.85 + c * 0.25)
    return np.clip(disp + g, 0, 1)


def interference_fx(enc: np.ndarray, amt: float, seed: int, t: float) -> np.ndarray:
    """The signal leaking into the image (display-encoded input). Analog, restrained: thin horizontal
    tears that slip sideways, a slow rolling band of fine noise, a brief exposure dip, and at high
    strength a pixel of lateral chroma slip and vertical jitter. Never blocky, never RGB bars."""
    if amt <= 0.01:
        return enc
    H, W = enc.shape[:2]
    rng = np.random.default_rng(seed * 104729 + 7)
    out = enc.copy()
    s = W / 1920.0
    for _ in range(int(2 + amt * 10)):
        y0 = int(rng.uniform(0, H))
        h = max(1, int(rng.uniform(1, 2 + 5 * amt) * s))
        sh = int(round(rng.normal(0, (2 + 14 * amt) * s)))
        out[y0:y0 + h] = np.roll(enc[y0:y0 + h], sh, axis=1)
    yy = np.arange(H, dtype=np.float32)[:, None, None] / H
    band = np.exp(-((yy - ((t * 0.37) % 1.3 - 0.15)) / 0.06) ** 2)
    fine = rng.standard_normal((H, W, 1)).astype(np.float32)
    out = out * (1.0 - 0.10 * amt * float(rng.uniform(0.3, 1.0))) + band * (0.035 * amt + 0.03 * amt * fine)
    if amt > 0.5:
        k = (amt - 0.5) * 2
        dx = int(round(1.5 * k * s)) or 1
        out[..., 0] = np.roll(out[..., 0], dx, axis=1)
        out[..., 2] = np.roll(out[..., 2], -dx, axis=1)
        out = np.roll(out, int(round(rng.normal(0, 1.5 * k * s))), axis=0)
    return np.clip(out, 0, 1)


def render_sprites(H: int, W: int, sprites: list) -> np.ndarray:
    """Point lights (e.g. a distant ship's strobe) as small Gaussian PSFs, energy normalised."""
    out = np.zeros((H, W, 3), np.float32)
    for sp in sprites:
        x, y = sp["x"] * W, sp["y"] * H
        sig = max(0.5, float(sp.get("sigma_px", 1.0)))
        r = int(math.ceil(sig * 4))
        x0, x1 = max(0, int(x) - r), min(W, int(x) + r + 2)
        y0, y1 = max(0, int(y) - r), min(H, int(y) + r + 2)
        if x0 >= x1 or y0 >= y1:
            continue
        yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32)
        g = np.exp(-((xx + 0.5 - x) ** 2 + (yy + 0.5 - y) ** 2) / (2 * sig * sig)) / (2 * math.pi * sig * sig)
        out[y0:y1, x0:x1] += g[..., None] * np.asarray(sp["rgb"], np.float32)
    return out


def _gain(v):
    if v is None:
        return 1.0
    return np.asarray(v, dtype=np.float32) if np.ndim(v) else float(v)


# ------------------------------------------------------------------ main entry
def composite(layers: dict, P: CompParams, t: float = 0.0) -> np.ndarray:
    """layers: name -> float32 arrays (H,W,3) scene-linear; optional 'ship' RGBA premultiplied (H,W,4),
    'ship_emit' (H,W,3), 'fg' RGBA premultiplied. Returns the display-encoded frame (sRGB curve) 0..1."""
    any_ = next(iter(layers.values()))
    H, W = any_.shape[:2]
    G = P.gains
    far = np.zeros((H, W, 3), np.float32)
    for n in ("sky", "stars", "haze", "disk", "beacon"):
        if n in layers:
            far += layers[n][..., :3] * _gain(G.get(n, 1.0))
    if P.sprites:
        far = far + render_sprites(H, W, P.sprites)
    far = dof(far, P.coc_px, P.bokeh_ratio)
    img = far
    if "ship" in layers:
        s = layers["ship"]
        a = s[..., 3:4]
        # the denoised Combined is the base; light groups (not denoised) only carry the regrade deltas,
        # so noise appears only where a group is pushed away from 1
        rgb = s[..., :3].copy()
        for g in ("env", "key", "lamps"):
            k = f"ship_{g}"
            gv = _gain(G.get(k, 1.0))
            if k in layers and np.any(np.asarray(gv) != 1.0):
                rgb = rgb + layers[k] * (np.asarray(gv, np.float32) - 1.0)
        rgb = np.maximum(rgb, 0.0)
        img = img * (1.0 - a) + rgb * _gain(G.get("ship", 1.0))
    if "ship_emit" in layers:
        img = img + layers["ship_emit"] * _gain(G.get("ship_emit", 1.0))
    if "fg" in layers:
        f = layers["fg"]
        img = img * (1.0 - f[..., 3:4]) + f[..., :3] * _gain(G.get("fg", 1.0))
    img = img * (2.0 ** P.exposure)

    # --- lens: glare, bloom, streaks (all energy-aware, restrained)
    if P.bloom > 0 or P.glare > 0:
        b = (_blur(img, 3) * 0.35 + _blur(img, 10) * 0.3 + _blur(img, 32) * 0.22 + _blur(img, 90) * 0.13)
        img = img * (1 - P.bloom) + b * P.bloom
        if P.glare > 0:
            img = img + _blur(img, 260) * P.glare
    if P.streak > 0:
        L = img @ LUMA
        hi = np.clip(L - P.streak_threshold, 0, None)[..., None] * (img / np.maximum(L, 1e-6)[..., None])
        if hi.max() > 0:
            st = _hblur(hi, P.streak_len) * 3.0 + _hblur(hi, P.streak_len * 0.25)
            img = img + st * P.streak * np.asarray(P.streak_tint, np.float32)
    if P.halation > 0:
        L = img @ LUMA
        hi = np.clip(L - P.halation_threshold, 0, 40.0)[..., None]
        hal = _blur(hi, 7) * 0.6 + _blur(hi, 18) * 0.4
        img = img + hal * P.halation * np.array([1.0, 0.32, 0.08], np.float32)

    img = lens_remap(img, P.distortion, P.ca)
    if P.vignette > 0:
        img = img * vignette_mask(H, W, P.vignette)

    # --- linear grade
    img = img * np.asarray(P.white, np.float32)
    if P.saturation != 1.0:
        L = (img @ LUMA)[..., None]
        img = np.maximum(L + P.saturation * (img - L), 0)

    disp = agx(img, P.punch, P.look_sat).astype(np.float32)
    # display grade: black point, lift/gamma/gain
    disp = np.clip((disp - P.black_point) / (1 - P.black_point), 0, 1)
    disp = np.clip(disp * P.gain + P.lift * (1 - disp), 0, 1) ** (1.0 / P.gamma)
    disp = srgb_encode(disp).astype(np.float32)      # everything below works on the encoded signal
    disp = interference_fx(disp, P.interference, P.seed, t)
    disp = grain(disp, P.grain, P.grain_size, P.seed)
    if P.title:
        from .titles import draw_title
        disp = draw_title(disp, **P.title)
    disp = disp * P.fade
    return disp


def to_rgb8(enc: np.ndarray) -> np.ndarray:
    """enc: display-encoded (sRGB/Rec.709-like) 0..1 as returned by composite()."""
    return (np.clip(enc, 0, 1) * 255 + 0.5).astype(np.uint8)


def to_rgb16(enc: np.ndarray) -> np.ndarray:
    return (np.clip(enc, 0, 1) * 65535 + 0.5).astype(np.uint16)

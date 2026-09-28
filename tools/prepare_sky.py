#!/usr/bin/env python3
"""Build the Milky Way sky texture used by the renderer.

Source: NASA/Goddard Scientific Visualization Studio, "Deep Star Maps 2020"
        https://svs.gsfc.nasa.gov/4851  (starmap_2020_8k_gal.exr, galactic coords)
        NASA imagery is not subject to copyright in the United States.

The renderer draws point stars analytically (so they stay razor sharp and
lens correctly around the black hole). What we need from the NASA map is the
*diffuse* galaxy: the glow of unresolved stars, dust lanes and the galactic
core. This script removes point sources with a morphological opening,
downsamples to 4096x2048 and stores the result as a gamma-encoded 8-bit JPEG
plus a small JSON with the decode scale.

The generated file (assets/sky/milkyway_diffuse.jpg) is committed to the
repository, so rendering never depends on NASA's servers. Run this script only
if you want to regenerate it:

    python tools/prepare_sky.py
"""
from __future__ import annotations

import hashlib
import json
import sys
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]
URL = "https://svs.gsfc.nasa.gov/vis/a000000/a004800/a004851/starmap_2020_8k_gal.exr"
CACHE = ROOT / ".cache" / "starmap_2020_8k_gal.exr"
OUT_DIR = ROOT / "assets" / "sky"
GAMMA = 2.4


def download() -> Path:
    if CACHE.exists() and CACHE.stat().st_size > 100_000_000:
        return CACHE
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    print(f"downloading {URL} ...", flush=True)
    tmp = CACHE.with_suffix(".part")
    urllib.request.urlretrieve(URL, tmp)
    tmp.rename(CACHE)
    return CACHE


def load_exr(path: Path) -> np.ndarray:
    import OpenEXR  # pip install OpenEXR

    f = OpenEXR.File(str(path))
    ch = f.channels()
    if "RGB" in ch:
        rgb = ch["RGB"].pixels
    else:
        rgb = np.stack([ch[c].pixels for c in "RGB"], axis=-1)
    return rgb.astype(np.float32)


def main() -> int:
    src = download()
    print("sha256", hashlib.sha256(src.read_bytes()).hexdigest()[:16])
    rgb = load_exr(src)
    print("loaded", rgb.shape, float(rgb.max()))

    # Remove point stars: grey opening on luminance-guided channels.
    diffuse = np.empty_like(rgb)
    for c in range(3):
        opened = ndimage.grey_opening(rgb[..., c], size=(7, 7), mode="wrap")
        diffuse[..., c] = ndimage.median_filter(opened, size=3, mode="wrap")

    # 8192x4096 -> 4096x2048 box downsample.
    h, w, _ = diffuse.shape
    diffuse = diffuse.reshape(h // 2, 2, w // 2, 2, 3).mean(axis=(1, 3))

    lum = diffuse @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    scale = float(np.percentile(lum, 99.97))
    enc = np.clip(diffuse / scale, 0.0, 1.0) ** (1.0 / GAMMA)
    img = Image.fromarray((enc * 255.0 + 0.5).astype(np.uint8), "RGB")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    img.save(OUT_DIR / "milkyway_diffuse.jpg", quality=93, subsampling=0, optimize=True)
    meta = {
        "source": URL,
        "credit": "NASA/Goddard Space Flight Center Scientific Visualization Studio, Deep Star Maps 2020",
        "encoding": f"linear = (value ** {GAMMA}) * scale",
        "gamma": GAMMA,
        "scale": scale,
        "median_linear": float(np.median(lum)),
    }
    (OUT_DIR / "milkyway_diffuse.json").write_text(json.dumps(meta, indent=2) + "\n")
    print(json.dumps(meta, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Build the sky inputs for the tracer.

  python production/tools/build_sky.py stars   # Tycho-2 (+ supplement 1) -> cache/sky/stars_tycho2.bin
  python production/tools/build_sky.py mw      # diffuse Milky Way map -> cache/sky/mw_gal.exr
  python production/tools/build_sky.py all

Stars: ICRS -> galactic unit vectors; colour from B-V (Ballesteros 2012 temperature, Planck spectrum
through the CIE 1931 CMFs -> linear Rec.709, luminance 1); flux = 10^(-0.4*gamma*V).
Binary layout: uint32 N, then N x (float32 dir[3], float32 rgb[3]).

Sources (see ASSETS.md): Tycho-2, Hog et al. 2000, CDS I/259 (ESA); NASA SVS Deep Star Maps 2020.
"""
from __future__ import annotations

import argparse
import gzip
import json
import math
import os
import struct
import sys
import urllib.request
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "production" / "cache"
DL = CACHE / "downloads"
SKY = CACHE / "sky"

TYCHO_BASE = "https://cdsarc.cds.unistra.fr/ftp/I/259/"

# ICRS (J2000) -> galactic rotation
R_ICRS_GAL = np.array([
    [-0.0548755604162154, -0.8734370902348850, -0.4838350155487132],
    [0.4941094278755837, -0.4448296299600112, 0.7469822444972189],
    [-0.8676661490190047, -0.1980763734312015, 0.4559837761750669],
])


def fetch(url: str, dest: Path) -> Path:
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    print(f"  fetch {url}", flush=True)
    for attempt in range(5):
        try:
            with urllib.request.urlopen(url, timeout=120) as r, open(tmp, "wb") as f:
                while True:
                    b = r.read(1 << 20)
                    if not b:
                        break
                    f.write(b)
            tmp.rename(dest)
            return dest
        except Exception as e:  # network hiccup: retry with backoff
            print(f"    retry {attempt + 1}: {e}", flush=True)
            import time
            time.sleep(2 ** attempt)
    raise RuntimeError(f"failed to fetch {url}")


# ------------------------------------------------------------------ colour
def _lobe(l, mu, s1, s2):
    t = (l - mu) / np.where(l < mu, s1, s2)
    return np.exp(-0.5 * t * t)


def _cmf(l):
    x = 1.056 * _lobe(l, 599.8, 37.9, 31.0) + 0.362 * _lobe(l, 442.0, 16.0, 26.7) - 0.065 * _lobe(l, 501.1, 20.4, 26.2)
    y = 0.821 * _lobe(l, 568.8, 46.9, 40.5) + 0.286 * _lobe(l, 530.9, 16.3, 31.1)
    z = 1.217 * _lobe(l, 437.0, 11.8, 36.0) + 0.681 * _lobe(l, 459.0, 26.0, 13.8)
    return x, y, z


XYZ2RGB = np.array([[3.2404542, -1.5371385, -0.4985314],
                    [-0.9692660, 1.8760108, 0.0415560],
                    [0.0556434, -0.2040259, 1.0572252]])


def blackbody_rgb(T: np.ndarray, white_K: float = 6500.0) -> np.ndarray:
    """Luminance-normalised linear Rec.709 colour of blackbodies (vectorised over T)."""
    lam = np.arange(360.0, 831.0, 2.0)
    xb, yb, zb = _cmf(lam)
    h, c, k = 6.62607015e-34, 2.99792458e8, 1.380649e-23
    lm = lam * 1e-9

    def xyz(Tv):
        Tv = np.atleast_1d(Tv)[:, None]
        B = 1.0 / (lm ** 5 * np.expm1(h * c / (lm * k * Tv)))
        X, Y, Z = (B * xb).sum(1), (B * yb).sum(1), (B * zb).sum(1)
        return np.stack([X / Y, np.ones_like(Y), Z / Y], 1)

    w = xyz(np.array([white_K])) @ XYZ2RGB.T
    rgb = xyz(T) @ XYZ2RGB.T
    rgb = np.clip(rgb / w, 0, None)
    L = rgb @ np.array([0.2126, 0.7152, 0.0722])
    return rgb / L[:, None]


def bv_to_temperature(bv: np.ndarray) -> np.ndarray:
    bv = np.clip(bv, -0.4, 2.0)
    return 4600.0 * (1.0 / (0.92 * bv + 1.7) + 1.0 / (0.92 * bv + 0.62))


def colour_lut():
    Ts = np.exp(np.linspace(np.log(1500), np.log(40000), 512))
    return Ts, blackbody_rgb(Ts)


# ------------------------------------------------------------------ Tycho-2
def _parse_float(b: bytes):
    s = b.strip()
    return float(s) if s else math.nan


def read_tycho2():
    """Returns ra, dec (deg), BT, VT arrays for Tycho-2 main + supplement 1."""
    ra, de, bt, vt = [], [], [], []
    files = [f"tyc2.dat.{i:02d}.gz" for i in range(20)]
    for fn in files:
        p = fetch(TYCHO_BASE + fn, DL / "tycho2" / fn)
        with gzip.open(p, "rb") as f:
            for line in f:
                if line[13:14] == b"X":  # no mean position: use observed
                    a, d = _parse_float(line[152:164]), _parse_float(line[165:177])
                else:
                    a, d = _parse_float(line[15:27]), _parse_float(line[28:40])
                ra.append(a); de.append(d)
                bt.append(_parse_float(line[110:116])); vt.append(_parse_float(line[123:129]))
    p = fetch(TYCHO_BASE + "suppl_1.dat.gz", DL / "tycho2" / "suppl_1.dat.gz")
    with gzip.open(p, "rb") as f:
        for line in f:
            ra.append(_parse_float(line[15:27])); de.append(_parse_float(line[28:40]))
            bt.append(_parse_float(line[83:89])); vt.append(_parse_float(line[96:102]))
    return (np.array(ra), np.array(de), np.array(bt), np.array(vt))


def build_stars(gamma: float, out: Path):
    print("stars: reading Tycho-2 ...", flush=True)
    ra, de, bt, vt = read_tycho2()
    ok = np.isfinite(ra) & np.isfinite(de) & (np.isfinite(vt) | np.isfinite(bt))
    ra, de, bt, vt = ra[ok], de[ok], bt[ok], vt[ok]
    has_both = np.isfinite(bt) & np.isfinite(vt)
    bv = np.where(has_both, 0.850 * (bt - vt), 0.65)          # Tycho -> Johnson (ESA 1997)
    V = np.where(has_both, vt - 0.090 * (bt - vt), np.where(np.isfinite(vt), vt, bt - 0.5))
    T = bv_to_temperature(bv)
    Ts, lut = colour_lut()
    idx = np.clip(np.searchsorted(Ts, T), 0, len(Ts) - 1)
    rgb = lut[idx]
    flux = 10.0 ** (-0.4 * gamma * V)
    a, d = np.radians(ra), np.radians(de)
    e = np.stack([np.cos(d) * np.cos(a), np.cos(d) * np.sin(a), np.sin(d)], 1)
    g = e @ R_ICRS_GAL.T
    data = np.concatenate([g, rgb * flux[:, None]], 1).astype(np.float32)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "wb") as f:
        f.write(struct.pack("<I", len(data)))
        f.write(data.tobytes())
    print(f"stars: {len(data)} stars, V range {np.nanmin(V):.2f}..{np.nanmax(V):.2f} -> {out}", flush=True)
    meta = {"source": "Tycho-2 (CDS I/259) + supplement 1", "gamma": gamma, "count": int(len(data)),
            "flux": "10^(-0.4*gamma*V)", "frame": "galactic unit vectors"}
    out.with_suffix(".json").write_text(json.dumps(meta, indent=2))


# ------------------------------------------------------------------ Milky Way
def build_mw(out: Path):
    """Diffuse Milky Way from the original film's star-removed NASA SVS map (8-bit, gamma encoded)."""
    from PIL import Image
    import OpenEXR
    src = ROOT / "assets" / "sky" / "milkyway_diffuse.jpg"
    meta = json.loads((ROOT / "assets" / "sky" / "milkyway_diffuse.json").read_text())
    img = np.asarray(Image.open(src).convert("RGB")).astype(np.float32) / 255.0
    lin = (img ** meta["gamma"]) * meta["scale"]
    out.parent.mkdir(parents=True, exist_ok=True)
    rgba = np.concatenate([lin, np.ones_like(lin[..., :1])], 2).astype(np.float32)
    hdr = {"compression": OpenEXR.ZIP_COMPRESSION, "type": OpenEXR.scanlineimage}
    chans = {"RGBA": rgba}
    with OpenEXR.File(hdr, chans) as f:
        f.write(str(out))
    print(f"mw: {img.shape[1]}x{img.shape[0]} -> {out}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["stars", "mw", "all"])
    ap.add_argument("--gamma", type=float, default=0.8, help="star brightness compression (1 = physical)")
    a = ap.parse_args()
    if a.what in ("stars", "all"):
        build_stars(a.gamma, SKY / "stars_tycho2.bin")
    if a.what in ("mw", "all"):
        build_mw(SKY / "mw_gal.exr")


if __name__ == "__main__":
    main()

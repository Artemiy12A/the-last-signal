#!/usr/bin/env python3
"""Quick look at a tracer EXR: sum/weight layers, expose, simple filmic curve, save PNG.

  python production/tools/exr_preview.py frame.exr out.png [--exposure 0] [--layers disk,haze,sky,stars]
         [--gain disk=1,stars=2] [--grid]  (--grid saves each layer side by side)
"""
import argparse

import numpy as np
import OpenEXR
from PIL import Image


def read_layers(path):
    with OpenEXR.File(path, separate_channels=True) as f:
        ch = f.channels()
        out = {}
        names = set(k.split(".")[0] for k in ch)
        for n in names:
            if f"{n}.R" in ch:
                out[n] = np.stack([ch[f"{n}.R"].pixels, ch[f"{n}.G"].pixels, ch[f"{n}.B"].pixels], -1).astype(np.float32)
            elif n in ch:
                out[n] = ch[n].pixels.astype(np.float32)
        return out


import sys as _sys
from pathlib import Path as _P
_sys.path.insert(0, str(_P(__file__).resolve().parents[1]))
from comp.tonemap import agx, srgb_encode  # noqa: E402


def filmic(x):
    """AgX display transform (same as the compositor), display-encoded 0..1."""
    return srgb_encode(agx(np.maximum(x, 0)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("exr")
    ap.add_argument("png")
    ap.add_argument("--exposure", type=float, default=0.0)
    ap.add_argument("--layers", default="disk,haze,sky,stars")
    ap.add_argument("--gain", default="")
    ap.add_argument("--grid", action="store_true")
    a = ap.parse_args()
    L = read_layers(a.exr)
    gains = {}
    for kv in filter(None, a.gain.split(",")):
        k, v = kv.split("=")
        gains[k] = float(v)
    names = [n for n in a.layers.split(",") if n in L]
    img = sum(L[n] * gains.get(n, 1.0) for n in names)
    img = img * (2.0 ** a.exposure)
    out = (filmic(img) * 255 + 0.5).astype(np.uint8)
    if a.grid:
        tiles = [out]
        for n in names:
            tiles.append((filmic(L[n] * gains.get(n, 1.0) * 2.0 ** a.exposure) * 255 + 0.5).astype(np.uint8))
        out = np.concatenate(tiles, 0)
    Image.fromarray(out).save(a.png)
    for n in L:
        v = L[n]
        print(f"{n:6s} mean {v.mean():.4g}  p99 {np.percentile(v, 99):.4g}  max {v.max():.4g}")


if __name__ == "__main__":
    main()

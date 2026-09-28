#!/usr/bin/env python3
"""Look-development helper: render tracer variants side by side.

  python production/tools/lookdev.py out_dir --dist 70 --incl 80 --fov 36 --res 640 \
        --set disk.haze=0.002 --var disk.h_over_r=0.02,0.04 [--spp 8]

Each --var value produces one render; results are stacked into out_dir/compare.png.
"""
import argparse
import copy
import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
TRACER = ROOT / "production" / "tracer" / "build" / "tracer"
sys.path.insert(0, str(ROOT / "production" / "tools"))
from exr_preview import read_layers, filmic  # noqa: E402

BASE = {
    "spin": 0.8,
    "white_K": 6500,
    "disk": {"T_peak": 6500, "p_g": 2.0, "color_g": 1.0, "emit_gain": 3.0, "r_out": 30, "haze": 0.002, "haze_h": 0.1},
    "sky": {"map": str(ROOT / "production/cache/sky/mw_gal.exr"),
            "stars": str(ROOT / "production/cache/sky/stars_tycho2.bin"), "gain": 30.0, "stars_gain": 3e-5},
}


def set_path(d, path, val):
    keys = path.split(".")
    for k in keys[:-1]:
        d = d.setdefault(k, {})
    try:
        val = json.loads(val)
    except Exception:
        pass
    d[keys[-1]] = val


def camera(dist, incl_deg, az_deg, look=(0, 0, 0), roll_deg=0.0):
    i, a = math.radians(incl_deg), math.radians(az_deg)
    pos = [dist * math.sin(i) * math.cos(a), dist * math.sin(i) * math.sin(a), dist * math.cos(i)]
    fwd = [look[k] - pos[k] for k in range(3)]
    return {"pos": pos, "fwd": fwd, "up": [0, 0, 1]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--dist", type=float, default=70)
    ap.add_argument("--incl", type=float, default=80)
    ap.add_argument("--az", type=float, default=-90)
    ap.add_argument("--look", default="0,0,0")
    ap.add_argument("--fov", type=float, default=36)
    ap.add_argument("--res", type=int, default=640)
    ap.add_argument("--spp", type=int, default=8)
    ap.add_argument("--exposure", type=float, default=-2.0)
    ap.add_argument("--set", action="append", default=[])
    ap.add_argument("--var", default="")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    scene = copy.deepcopy(BASE)
    scene.update({"width": a.res, "height": int(round(a.res / 2.39)), "hfov_deg": a.fov, "spp": a.spp,
                  "cam": [camera(a.dist, a.incl, a.az, tuple(float(v) for v in a.look.split(",")))]})
    for s in a.set:
        k, v = s.split("=", 1)
        set_path(scene, k, v)
    variants = [("base", None)]
    if a.var:
        k, vals = a.var.split("=", 1)
        variants = [(f"{k}={v}", (k, v)) for v in vals.split(",")]
    tiles = []
    for name, kv in variants:
        sc = copy.deepcopy(scene)
        if kv:
            set_path(sc, kv[0], kv[1])
        tag = name.replace("=", "_").replace(".", "_")
        sc["out"] = str(out / f"{tag}.exr")
        (out / f"{tag}.json").write_text(json.dumps(sc, indent=1))
        r = subprocess.run([str(TRACER), str(out / f"{tag}.json")], capture_output=True, text=True)
        print(name, r.stderr.strip().splitlines()[-1] if r.stderr else "", flush=True)
        L = read_layers(sc["out"])
        img = sum(L[n] for n in ("disk", "haze", "sky", "stars") if n in L) * 2.0 ** a.exposure
        im = Image.fromarray((filmic(img) * 255 + 0.5).astype(np.uint8))
        ImageDraw.Draw(im).text((6, 4), name, fill=(200, 200, 200))
        im.save(out / f"{tag}.png")
        tiles.append(np.asarray(im))
    Image.fromarray(np.concatenate(tiles, 0)).save(out / "compare.png")


if __name__ == "__main__":
    main()

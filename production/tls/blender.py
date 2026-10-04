"""Blender ship layers: env probes from the tracer, batched Cycles renders, EXR layer loading."""
from __future__ import annotations

import json
import math
import subprocess
from pathlib import Path

import numpy as np

from . import edl, world
from .camera import Cam, norm
from .paths import BLENDER, CACHE, PROD, SKY_MAP, STARS, TRACER

def _ship_hash() -> str:
    import hashlib
    h = hashlib.sha1()
    for f in sorted((PROD / "blender" / "ship").glob("*.py")):
        h.update(f.read_bytes())
    return h.hexdigest()[:10]


SHIP_BLEND = CACHE / "ship" / f"ship_{_ship_hash()}.blend"
RENDER_SCRIPT = PROD / "blender" / "render_frame.py"
BL_SAMPLES = {"draft": 16, "preview": 48, "final": 160}
PROBE_RES = {"draft": 256, "preview": 384, "final": 512}


def probe_exr(pos_bh, t_disk: float, q: str, out: Path, seed: int = 1) -> Path:
    """Equirect HDR environment (world axes, Blender convention) seen from pos_bh, for image lighting."""
    if out.exists():
        return out
    W = PROBE_RES[q]
    sc = {
        "width": W, "height": W // 2, "projection": "world_equirect", "hfov_deg": 90.0,
        "spin": world.SPIN, "white_K": world.WHITE_K,
        "cam": [{"pos": [float(x) for x in pos_bh], "fwd": [0, 1, 0], "up": [0, 0, 1]}],
        "time": t_disk, "spp": 4, "spp_min": 2, "spp_haze": 1, "hfac": 0.16, "star_times": 1, "seed": seed,
        "disk": dict(world.DISK),
        "sky": {**world.SKY, "map": str(SKY_MAP), "stars": str(STARS), "rot": world.SKY_ROT.tolist(),
                "stars_gain": world.SKY["stars_gain"] * (W / 1920.0) ** 2},
        "output": "beauty", "out": str(out),
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    js = out.with_suffix(".json")
    js.write_text(json.dumps(sc))
    r = subprocess.run([str(TRACER), str(js)], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"probe failed: {r.stderr[-1500:]}")
    return out


def _mat(m) -> list:
    return [[float(v) for v in row] for row in np.asarray(m, float)]


def frame_job(spec, q: str, exrdir: Path) -> dict:
    """Blender job entry for one FrameSpec (spec.blender holds the shot's Blender parameters)."""
    b = spec.blender
    mod_cam = spec._cams3          # type: ignore[attr-defined]  (prev, centre, next) Cam
    ship3 = spec._ships3           # type: ignore[attr-defined]
    w = dict(b.get("world", {}))
    if b.get("probe"):
        p = b["probe"]
        w["env"] = str(probe_exr(p["pos_bh"], spec.disk_time, q, exrdir / f"probe{spec.frame:05d}.exr",
                                 seed=spec.frame + 7))
        w.setdefault("strength", p.get("strength", 1.0))
    job = {
        "out": "",
        "camera": [c.to_blender() for c in mod_cam],
        "ship": [_mat(m) for m in ship3],
        "controls": b.get("controls", {}),
        "world": w,
        "keys": b.get("keys", []),
        "hide_ship": b.get("hide_ship", False),
        "times": [spec.t - 1.0 / edl.FPS, spec.t, spec.t + 1.0 / edl.FPS],
        "props": b.get("props", []),
        "samples_scale": float(b.get("samples_scale", 1.0)),   # per-shot Blender sample budget
    }
    import hashlib
    key = hashlib.sha1((json.dumps(job, sort_keys=True) + SHIP_BLEND.name + q).encode()).hexdigest()[:10]
    job["out"] = str(exrdir / f"b{spec.frame:05d}_{key}.exr")
    return job


def run_batch(jobs: list[dict], q: str, W: int, H: int, workdir: Path):
    if not jobs:
        return
    workdir.mkdir(parents=True, exist_ok=True)
    SHIP_BLEND.parent.mkdir(parents=True, exist_ok=True)
    spp = max(8, int(round(BL_SAMPLES[q] * jobs[0].get("samples_scale", 1.0))))
    job = {"width": W, "height": H, "samples": spp, "ship_blend": str(SHIP_BLEND), "frames": jobs}
    jp = workdir / f"bjob_{Path(jobs[0]['out']).stem}.json"
    jp.write_text(json.dumps(job))
    r = subprocess.run([str(BLENDER), "-b", "--factory-startup", "-noaudio", "-P", str(RENDER_SCRIPT), "--", str(jp)],
                       capture_output=True, text=True)
    if r.returncode != 0 or "Error" in r.stderr[-400:]:
        tail = (r.stdout[-2500:] + r.stderr[-2500:])
        if not all(Path(j["out"]).exists() for j in jobs):
            raise RuntimeError(f"blender failed:\n{tail}")


def read_ship_layers(path: Path) -> dict:
    """Blender multilayer EXR -> {'ship': RGBA premultiplied, 'ship_env', 'ship_key', 'ship_lamps', 'ship_z'}."""
    import OpenEXR
    out = {}
    with OpenEXR.File(str(path), separate_channels=True) as f:
        ch = f.channels()

        def rgb(prefix):
            ks = [k for k in ch if k.endswith(prefix + ".R")]
            if not ks:
                return None
            base = ks[0][:-2]
            return np.stack([ch[base + ".R"].pixels, ch[base + ".G"].pixels, ch[base + ".B"].pixels], -1).astype(np.float32)

        comb = rgb("Combined")
        a = next((ch[k].pixels for k in ch if k.endswith("Combined.A")), None)
        if comb is not None:
            A = (a if a is not None else np.ones(comb.shape[:2])).astype(np.float32)
            out["ship"] = np.concatenate([comb, A[..., None]], -1)
        for g in ("env", "key", "lamps"):
            v = rgb(f"Combined_{g}")
            if v is not None:
                out[f"ship_{g}"] = v
        z = next((ch[k].pixels for k in ch if k.endswith("Depth.Z") or k.endswith(".Z")), None)
        if z is not None:
            out["ship_z"] = z.astype(np.float32)
    return out

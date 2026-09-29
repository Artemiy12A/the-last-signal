"""Frame renderer: shot module -> tracer EXR (+ Blender EXR) -> composite -> PNG.

  python -m tls.render frame S10 1200 --q preview            # one frame (global frame index)
  python -m tls.render shot S10 --q draft --every 12         # frames of one shot
  python -m tls.render frames 1164-1439 --q final            # any global range (farm shard)
  python -m tls.render still S10 54.0 --q final              # by film time

Outputs: production/out/<q>/<shot>/f<frame:05d>.png (8-bit sRGB; 16-bit with --png16).
"""
from __future__ import annotations

import argparse
import importlib
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field, replace
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from comp.comp import CompParams, composite, to_rgb8, to_rgb16  # noqa: E402

from . import edl, world  # noqa: E402
from .camera import Cam  # noqa: E402
from .paths import BLENDER, OUT, PROD, SKY_MAP, STARS, TRACER  # noqa: E402

QUALITY = {
    "draft":   {"W": 480,  "spp": 4,  "spp_min": 2, "spp_haze": 1, "hfac": 0.16, "bl_samples": 16, "star_times": 1},
    "preview": {"W": 960,  "spp": 8,  "spp_min": 3, "spp_haze": 2, "hfac": 0.14, "bl_samples": 48, "star_times": 1},
    "final":   {"W": 1920, "spp": 20, "spp_min": 6, "spp_haze": 3, "hfac": 0.12, "bl_samples": 192, "star_times": 3},
}
SHUTTER = 0.5 / edl.FPS      # 180 degrees


@dataclass
class FrameSpec:
    frame: int
    t: float
    cam0: Cam
    cam1: Cam
    disk_time: float = 0.0
    tracer: dict = field(default_factory=dict)   # overrides for the tracer scene (None = no tracer)
    comp: CompParams = field(default_factory=CompParams)
    blender: dict | None = None
    black: bool = False
    probe: dict | None = None                     # env probe request for Blender lighting


def load_shot(shot_id: str):
    return importlib.import_module(f"shots.{shot_id}.shot")


def make_spec(shot_id: str, frame: int, q: str) -> FrameSpec:
    t = edl.frame_time(frame)
    mod = load_shot(shot_id)
    c = mod.cam_at(t)
    c0 = mod.cam_at(t - SHUTTER / 2)
    c1 = mod.cam_at(t + SHUTTER / 2)
    p = mod.params(t, q)
    spec = FrameSpec(frame=frame, t=t, cam0=c0, cam1=c1, disk_time=p.get("disk_time", t * world.DISK_RATE),
                     tracer=p.get("tracer", {}), comp=p.get("comp", CompParams()), blender=p.get("blender"),
                     black=p.get("black", False), probe=p.get("probe"))
    spec.comp.seed = frame
    spec._cam = c  # type: ignore[attr-defined]
    dt = 1.0 / edl.FPS
    spec._cams3 = [mod.cam_at(t - dt), c, mod.cam_at(t + dt)]  # type: ignore[attr-defined]
    ship_at = getattr(mod, "ship_at", None)
    spec._ships3 = [ship_at(t - dt), ship_at(t), ship_at(t + dt)] if ship_at else [np.eye(4)] * 3  # type: ignore[attr-defined]
    return spec


def deep_merge(a: dict, b: dict) -> dict:
    out = dict(a)
    for k, v in b.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def tracer_scene(spec: FrameSpec, q: str, out_exr: Path) -> dict:
    Q = QUALITY[q]
    W = Q["W"]
    H = int(round(W / 2.39 / 2)) * 2
    sc = {
        "width": W, "height": H, "hfov_deg": spec.cam0.hfov, "spin": world.SPIN, "white_K": world.WHITE_K,
        "cam": [spec.cam0.to_tracer(), spec.cam1.to_tracer()],
        "time": spec.disk_time, "shutter_dt": SHUTTER * world.DISK_RATE,
        "spp": Q["spp"], "spp_min": Q["spp_min"], "spp_haze": Q["spp_haze"], "hfac": Q["hfac"],
        "star_times": Q["star_times"], "seed": spec.frame + 1,
        "disk": dict(world.DISK),
        "sky": {**world.SKY, "map": str(SKY_MAP), "stars": str(STARS), "rot": world.SKY_ROT.tolist()},
        "out": str(out_exr),
    }
    sc = deep_merge(sc, spec.tracer or {})
    if os.environ.get("TLS_DISK"):      # lookdev: override disk parameters, e.g. TLS_DISK='{"n_phi": 28}'
        sc["disk"].update(json.loads(os.environ["TLS_DISK"]))
    return sc


def run_tracer(sc: dict, tmpdir: Path) -> Path:
    tmpdir.mkdir(parents=True, exist_ok=True)
    js = Path(sc["out"]).with_suffix(".json")
    js.write_text(json.dumps(sc))
    r = subprocess.run([str(TRACER), str(js)], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"tracer failed: {r.stderr[-2000:]}")
    return Path(sc["out"])


def read_exr_layers(path: Path) -> dict:
    import OpenEXR
    out = {}
    with OpenEXR.File(str(path), separate_channels=True) as f:
        ch = f.channels()
        names = set(k.split(".")[0] for k in ch)
        for n in names:
            if f"{n}.R" in ch:
                out[n] = np.stack([ch[f"{n}.R"].pixels, ch[f"{n}.G"].pixels, ch[f"{n}.B"].pixels], -1).astype(np.float32)
            elif n in ch:
                out[n] = ch[n].pixels.astype(np.float32)
    return out


def save_image(path: Path, img: np.ndarray) -> Path:
    """8-bit -> PNG; 16-bit -> binary PPM (P6, maxval 65535, big-endian), which ffmpeg reads natively."""
    if img.dtype == np.uint16:
        path = path.with_suffix(".ppm")
        H, W = img.shape[:2]
        with open(path, "wb") as f:
            f.write(f"P6\n{W} {H}\n65535\n".encode())
            f.write(img.astype(">u2").tobytes())
    else:
        Image.fromarray(img).save(path)
    return path


def render_frames(shot_id: str, frames: list[int], q: str, png16: bool = False, keep_exr: bool = True,
                  outdir: Path | None = None, batch: int = 24) -> list[Path]:
    """Render frames of one shot. Blender layers are rendered in batches (one Blender process per
    batch, the ship is built/loaded once), then each frame's tracer plate and composite."""
    Q = QUALITY[q]
    W = Q["W"]
    H = int(round(W / 2.39 / 2)) * 2
    outdir = outdir or (OUT / q / shot_id)
    exrdir = outdir / "exr"
    outdir.mkdir(parents=True, exist_ok=True)
    exrdir.mkdir(parents=True, exist_ok=True)
    out = []
    for i in range(0, len(frames), batch):
        chunk = frames[i:i + batch]
        specs = [make_spec(shot_id, f, q) for f in chunk]
        jobs = []
        for s_ in specs:
            if s_.blender is not None and not s_.black:
                from . import blender as bl
                j = bl.frame_job(s_, q, exrdir)
                s_._bexr = Path(j["out"])  # type: ignore[attr-defined]
                if not s_._bexr.exists():
                    jobs.append(j)
        if jobs:
            from . import blender as bl
            t0 = time.time()
            bl.run_batch(jobs, q, W, H, exrdir)
            print(f"{shot_id} blender batch {len(jobs)} frames {time.time() - t0:.1f}s", flush=True)
        for spec in specs:
            out.append(_finish_frame(shot_id, spec, q, W, H, outdir, exrdir, png16, keep_exr))
    return out


def render_frame(shot_id: str, frame: int, q: str, png16: bool = False, keep_exr: bool = True,
                 outdir: Path | None = None) -> Path:
    return render_frames(shot_id, [frame], q, png16, keep_exr, outdir)[0]


def _finish_frame(shot_id, spec, q, W, H, outdir, exrdir, png16, keep_exr) -> Path:
    t0 = time.time()
    frame = spec.frame
    png = outdir / f"f{frame:05d}.png"
    if spec.black:
        enc = np.zeros((H, W, 3), np.float32)
        P = spec.comp
        if P.title:
            from comp.titles import draw_title
            enc = draw_title(enc, **P.title) * P.fade
        img = to_rgb16(enc) if png16 else to_rgb8(enc)
        return save_image(png, img)
    layers = {}
    if spec.tracer is not None:
        sc = tracer_scene(spec, q, exrdir / f"t{frame:05d}.exr")
        run_tracer(sc, exrdir)
        layers.update(read_exr_layers(Path(sc["out"])))
    if spec.blender is not None:
        from . import blender as bl
        bexr = getattr(spec, "_bexr", exrdir / f"b{frame:05d}.exr")
        if bexr.exists():
            layers.update(bl.read_ship_layers(bexr))
    # resolution-independent comp: scale pixel-sized effects with width
    P = replace(spec.comp)
    s = W / 1920.0
    P.coc_px *= s
    P.streak_len *= s
    P.ca *= s
    P.grain_size = max(0.5, P.grain_size * s)
    P.sprites = [dict(sp, x=sp["x"], y=sp["y"]) for sp in (P.sprites or [])]
    enc = composite(layers, P, spec.t)
    img = to_rgb16(enc) if png16 else to_rgb8(enc)
    png = save_image(png, img)
    if not keep_exr:
        for p in exrdir.glob(f"*{frame:05d}*"):
            p.unlink()
    print(f"{shot_id} f{frame} ({spec.t:.2f}s) {q} {time.time() - t0:.1f}s -> {png}", flush=True)
    return png


def parse_range(s: str) -> list[int]:
    out = []
    for part in s.split(","):
        if "-" in part:
            a, b = part.split("-")
            out += list(range(int(a), int(b) + 1))
        else:
            out.append(int(part))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["frame", "shot", "frames", "still"])
    ap.add_argument("args", nargs="*")
    ap.add_argument("--q", default="preview", choices=list(QUALITY))
    ap.add_argument("--every", type=int, default=1)
    ap.add_argument("--png16", action="store_true")
    ap.add_argument("--no-exr", action="store_true")
    a = ap.parse_args()
    sys.path.insert(0, str(PROD))
    if a.cmd == "frame":
        render_frame(a.args[0], int(a.args[1]), a.q, a.png16, not a.no_exr)
    elif a.cmd == "still":
        s = edl.SHOT_BY_ID[a.args[0]]
        f = int(round(float(a.args[1]) * edl.FPS))
        render_frame(s.id, f, a.q, a.png16, not a.no_exr)
    elif a.cmd == "shot":
        s = edl.SHOT_BY_ID[a.args[0]]
        render_frames(s.id, list(range(s.f0, s.f1, a.every)), a.q, a.png16, not a.no_exr)
    elif a.cmd == "frames":
        for f in parse_range(a.args[0])[:: a.every]:
            s = edl.shot_at(edl.frame_time(f) + 1e-6)
            render_frame(s.id, f, a.q, a.png16, not a.no_exr)


if __name__ == "__main__":
    main()

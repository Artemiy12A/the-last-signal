"""S15 beacon acceptance test, as the film renders it: disk on, final resolution, every frame.

  cd production && python shots/S15/beacon_check.py [--q final] [--frames 1776-1979] [--tracer PATH] [--out DIR]

Pass 1 finds the beacon's image per frame in a small beacon-only render (disk off: every pixel fully
sampled). Pass 2 renders the real frame (disk on, the shot's own settings) cropped to a box around it and
measures the beacon layer's flux. A frame whose flux falls far below both neighbours while the EDL keeps
the beacon lit is a dropout. (The old test rendered the beacon with the disk off, which is exactly the
case where the tracer supersamples every pixel, so it could not see dropouts on unsampled pixels.)
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tls import edl  # noqa: E402
from tls.render import QUALITY, TRACER, make_spec, read_exr_layers, tracer_scene  # noqa: E402

SHOT = edl.SHOT_BY_ID["S15"]


def _run(tracer: Path, sc: dict, out: Path) -> np.ndarray:
    sc = dict(sc, out=str(out))
    js = out.with_suffix(".json")
    js.write_text(json.dumps(sc))
    r = subprocess.run([str(tracer), str(js)], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr[-2000:])
    b = read_exr_layers(out)["beacon"]
    js.unlink()
    out.unlink()
    return b.sum(-1) if b.ndim == 3 else b


def locate(f: int, tracer: Path, tmp: Path, w_lo: int = 480) -> tuple[float, float]:
    spec = make_spec("S15", f, "draft")
    sc = tracer_scene(spec, "draft", tmp / "lo.exr")
    sc["disk"] = dict(sc.get("disk", {}), on=False)
    b = _run(tracer, sc, tmp / "lo.exr")
    j, i = np.unravel_index(np.argmax(b), b.shape)
    return (i + 0.5) / b.shape[1], (j + 0.5) / b.shape[0]


def flux(f: int, q: str, tracer: Path, tmp: Path, pos: tuple[float, float], box: int = 192,
         extinction: float | None = None) -> float:
    W = QUALITY[q]["W"]
    H = int(round(W / 2.39 / 2)) * 2
    spec = make_spec("S15", f, q)
    sc = tracer_scene(spec, q, tmp / "hi.exr")
    cx, cy = int(pos[0] * W), int(pos[1] * H)
    x0, y0 = max(0, cx - box // 2), max(0, cy - box // 2)
    sc["crop"] = [x0, y0, min(W, x0 + box), min(H, y0 + box)]
    if extinction is not None:                   # lookdev override of the shot's value
        sc["beacon"] = dict(sc["beacon"], extinction=extinction)
    return float(_run(tracer, sc, tmp / "hi.exr").sum())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--q", default="final")
    ap.add_argument("--frames", default=f"{SHOT.f0}-{SHOT.f1 - 1}")
    ap.add_argument("--tracer", type=Path, default=TRACER)
    ap.add_argument("--out", type=Path, default=Path("out/beacon_check"))
    ap.add_argument("--extinction", type=float, default=None)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    lo, hi = map(int, a.frames.split("-"))
    rows = []
    for f in range(lo, hi + 1):
        t = edl.frame_time(f)
        pos = locate(f, a.tracer, a.out)
        fl = flux(f, a.q, a.tracer, a.out, pos, extinction=a.extinction)
        rows.append((f, t, pos[0], pos[1], fl, edl.beacon_intensity(t)))
        print(f"{f} {t:6.2f} ({pos[0]:.3f},{pos[1]:.3f}) flux {fl:12.4g}", flush=True)
    fl = np.array([r[4] for r in rows])
    bad = []
    for k in range(1, len(fl) - 1):
        if fl[k] < 0.25 * min(fl[k - 1], fl[k + 1]):
            bad.append(rows[k][0])
    (a.out / f"beacon_{a.q}_{lo}-{hi}.json").write_text(json.dumps({"rows": rows, "dropouts": bad}))
    print(f"dropouts (flux < 1/4 of both neighbours): {bad or 'none'}")


if __name__ == "__main__":
    main()

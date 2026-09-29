"""Measure the S15 beacon light curve from the tracer itself, for the soundtrack.

  python -m tls.lightcurve        -> production/shots/S15/lightcurve.json  [[t, intensity, redshift], ...]

Renders the beacon layer alone (disk off, small frame) at every frame of S15; intensity is the total
beacon flux in frame normalised to the brightest frame, redshift g = T_observed / T_emitted estimated
from the colour of the light (blackbody fit)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from . import edl  # noqa: E402
from .paths import OUT, PROD  # noqa: E402
from .render import make_spec, read_exr_layers, run_tracer, tracer_scene  # noqa: E402


def colour_temperature(rgb: np.ndarray) -> float:
    sys.path.insert(0, str(PROD / "tools"))
    from build_sky import blackbody_rgb
    Ts = np.exp(np.linspace(np.log(600), np.log(40000), 400))
    lut = blackbody_rgb(Ts)
    c = rgb / max(rgb.sum(), 1e-12)
    l = lut / lut.sum(1, keepdims=True)
    return float(Ts[np.argmin(((l - c) ** 2).sum(1))])


def main():
    sys.path.insert(0, str(PROD))
    shot = edl.SHOT_BY_ID["S15"]
    mod = __import__("shots.S15.shot", fromlist=["x"])
    T_emit = 11000.0
    exrdir = OUT / "lightcurve"
    rows = []
    for f in range(shot.f0, shot.f1):
        spec = make_spec("S15", f, "draft")
        sc = tracer_scene(spec, "draft", exrdir / f"lc{f:05d}.exr")
        sc.update({"width": 320, "height": 134, "spp": 4, "spp_min": 4, "star_times": 1})
        sc["disk"]["on"] = False
        sc["sky"].pop("stars", None)
        sc["sky"].pop("map", None)
        run_tracer(sc, exrdir)
        b = read_exr_layers(Path(sc["out"])).get("beacon")
        tot = b.reshape(-1, 3).sum(0) if b is not None else np.zeros(3)
        I = float(tot @ np.array([0.2126, 0.7152, 0.0722]))
        g = colour_temperature(tot) / T_emit if I > 1e-9 else 0.0
        rows.append([round(spec.t, 4), I, round(g, 4)])
        print(f"{spec.t:6.2f}s  I={I:10.4f}  g={g:.3f}", flush=True)
    mx = max(r[1] for r in rows) or 1.0
    for r in rows:
        r[1] = round(r[1] / mx, 6)
    out = PROD / "shots" / "S15" / "lightcurve.json"
    out.write_text(json.dumps({"columns": ["film_time_s", "intensity_rel", "redshift_g"], "rows": rows}, indent=0))
    print(f"-> {out}")


if __name__ == "__main__":
    main()

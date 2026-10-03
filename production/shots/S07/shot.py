"""S07 — GLIMPSE: EDGE (37.0–41.0). Extreme telephoto on the shadow's edge: a razor-thin blazing arc
on black, turbulent gas streaming across it. No scale reference. Slow lateral drift along the arc."""
import math

import numpy as np

from comp.comp import CompParams
from tls import edl, world
from tls.camera import Cam, Track, look, norm, orbit_pos, v3

SHOT = edl.SHOT_BY_ID["S07"]
T0, T1 = SHOT.start, SHOT.end

# aim point slides along the upper-left limb of the shadow (lensed far side of the disk)
aim = Track([(T0, v3(-3.7, 0.0, 1.7)), (T1, v3(-3.1, 0.0, 2.7))])   # mostly shadow: the edge rims one side


def cam_at(t: float) -> Cam:
    p = orbit_pos(150.0, 84.0, -90.0)
    f = look(p, aim(t))
    c = Cam(fwd=f, up=v3(0, 0, 1), pos_bh=p, hfov=1.8)   # a 2.3x longer lens: the arc only
    return c.with_drift(t, 0.004, seed=7)


def params(t: float, q: str) -> dict:
    # only the brightest gas at the inner edge survives: a razor arc on black, not the disk's surface
    P = CompParams(exposure=-2.0, gains={"sky": 0.3, "stars": 0.6}, bloom=0.03, glare=0.01, streak=0.04,
                   halation=0.07, vignette=0.35, punch=0.5, look_sat=1.15, saturation=0.9, white=(1.0, 0.95, 0.88))
    return {"comp": P, "tracer": {"disk": {"octaves": 7}}}

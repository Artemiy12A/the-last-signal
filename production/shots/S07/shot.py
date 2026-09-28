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
aim = Track([(T0, v3(-5.8, 0.0, 3.2)), (T1, v3(-4.9, 0.0, 4.6))])


def cam_at(t: float) -> Cam:
    p = orbit_pos(150.0, 84.0, -90.0)
    f = look(p, aim(t))
    c = Cam(fwd=f, up=v3(0, 0, 1), pos_bh=p, hfov=4.2)
    return c.with_drift(t, 0.004, seed=7)


def params(t: float, q: str) -> dict:
    P = CompParams(exposure=-1.2, gains={"sky": 0.3, "stars": 0.6}, bloom=0.03, glare=0.01, streak=0.04,
                   halation=0.07, vignette=0.35, punch=0.2, look_sat=1.1, white=(1.0, 0.95, 0.88))
    return {"comp": P, "tracer": {"disk": {"octaves": 7}}}

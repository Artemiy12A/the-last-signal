"""S12 — UNDER THE ARCH (65.5–69.5). Grazing skim just above the turbulent disk surface, the lensed
arch towering overhead, the ship ahead."""
import math

import numpy as np

from comp.comp import CompParams
from tls import edl
from tls.camera import Cam, Track, look, norm, v3
from tls.shotkit import controls, ship_matrix

SHOT = edl.SHOT_BY_ID["S12"]
T0, T1 = SHOT.start, SHOT.end
r = Track([(T0, 31.0), (T1, 27.5)], ease=0.2)
h = Track([(T0, 0.62), (T1, 0.55)])


def cam_at(t):
    rr = float(r(t))
    a = math.radians(-96.0 + 5.0 * SHOT.local(t))
    pb = v3(rr * math.cos(a), rr * math.sin(a), float(h(t)))
    f = norm(look(pb, (0, 0, 1.0)))
    c = Cam(fwd=f, up=v3(0, 0, 1), pos_bh=pb, pos_ship=v3(8.0, -160.0, -10.0), hfov=58.0)
    return c.with_drift(t, 0.07, seed=12, vib_px=0.25)


def ship_at(t):
    return ship_matrix(yaw=-6.0, roll=8.0)


def params(t, q):
    P = CompParams(exposure=-0.9, gains={"sky": 0.5, "stars": 0.8, "ship_env": 1.0, "ship_key": 1.0, "ship_lamps": 1.3},
                   bloom=0.05, glare=0.02, streak=0.07, halation=0.07, vignette=0.34, punch=0.3, look_sat=1.3, saturation=1.1,
                   white=(1.0, 0.95, 0.88))
    bl = {"controls": controls(t, engine=0.25), "probe": {"pos_bh": [float(x) for x in cam_at(t).pos_bh], "strength": 1.0},
          "keys": []}
    return {"comp": P, "tracer": {"disk": {"octaves": 7}}, "blender": bl}

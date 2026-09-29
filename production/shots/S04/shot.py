"""S04 — WRONG STARS (21.5–28.0). Over the aft looking ahead: stars ahead stream and arc around an
empty centre as the ship moves (Einstein-ring drift). Something vast, felt before it's seen."""
import math

import numpy as np

from comp.comp import CompParams
from tls import edl
from tls.camera import Cam, Track, norm, rot, v3
from tls.shotkit import controls, ship_matrix, ship_pos_bh

SHOT = edl.SHOT_BY_ID["S04"]
T0, T1 = SHOT.start, SHOT.end
dist = Track([(T0, 420.0), (T1, 385.0)])
lat = Track([(T0, 34.0), (T1, 14.0)])          # lateral offset (M): the ring drifts across the stars
cpos = Track([(T0, v3(2.0, -46.0, 8.5)), (T1, v3(1.5, -40.0, 8.0))])


def cam_at(t):
    pb = ship_pos_bh(float(dist(t)), offset=(float(lat(t)), 0.0, 0.0))
    f = norm(rot((0, 0, 1), math.radians(4.0)) @ rot((1, 0, 0), math.radians(-3.0)) @ v3(0, 1, 0))
    c = Cam(fwd=f, up=v3(0, 0, 1), pos_bh=pb, pos_ship=cpos(t), hfov=44.0)
    return c.with_drift(t, 0.04, seed=4)


def ship_at(t):
    return ship_matrix(roll=1.0 * math.sin(0.2 * t))


def params(t, q):
    P = CompParams(exposure=0.5, gains={"sky": 1.2, "stars": 1.3, "disk": 0.0, "haze": 0.0,
                                         "ship_env": 1.0, "ship_key": 1.0, "ship_lamps": 1.0},
                   bloom=0.03, streak=0.05, streak_threshold=10.0, halation=0.04, vignette=0.34, punch=0.12,
                   white=(0.98, 0.98, 1.0), interference=0.2 * edl.interference(t))
    bl = {"controls": controls(t, engine=0.12), "world": {"color": [0.0004, 0.0005, 0.0007]},
          "keys": [{"dir": [0.1, 1.0, 0.25], "color": [1.0, 0.8, 0.6], "strength": 0.25, "angle": 2.0}]}
    return {"comp": P, "tracer": {}, "blender": bl}

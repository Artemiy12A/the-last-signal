"""S03 — LISTENING (15.5–21.5). 3/4 medium: the high-gain dish slews and locks on; the signal arrives
and the running lights stutter in sync."""
import math

import numpy as np

from comp.comp import CompParams
from tls import edl
from tls.camera import Cam, Track, ease_in_out, look, norm, smoothstep, v3
from tls.shotkit import controls, ship_matrix, ship_pos_bh, warm_key_from_hole

SHOT = edl.SHOT_BY_ID["S03"]
T0, T1 = SHOT.start, SHOT.end
az = Track([(T0, 206.0), (T1, 218.0)])
dist = Track([(T0, 92.0), (T1, 84.0)])


def cam_at(t):
    a, e = math.radians(float(az(t))), math.radians(11.0)
    d = float(dist(t))
    p = v3(d * math.cos(e) * math.cos(a), d * math.cos(e) * math.sin(a), d * math.sin(e))
    c = Cam(fwd=look(p, (0, 4.0, 0)), up=v3(0, 0, 1), pos_bh=ship_pos_bh(2400.0), pos_ship=p, hfov=48.0)
    return c.with_drift(t, 0.05, seed=3)


def ship_at(t):
    return ship_matrix(yaw=-4.0, pitch=1.5, roll=-3.0 + 0.8 * math.sin(0.25 * t))


def params(t, q):
    s = ease_in_out(smoothstep(T0 + 0.8, T0 + 3.4, t), 2.2)
    ctl = controls(t, dish_az=-38.0 + 38.0 * s, dish_el=-12.0 + 12.0 * s)
    P = CompParams(exposure=0.3, gains={"sky": 1.0, "stars": 1.2, "ship_env": 1.0, "ship_key": 1.0, "ship_lamps": 1.0},
                   bloom=0.04, streak=0.06, streak_threshold=8.0, halation=0.05, vignette=0.32, punch=0.14,
                   white=(0.97, 0.98, 1.02), interference=0.25 * edl.interference(t))
    bl = {"controls": ctl, "world": {"color": [0.0004, 0.0005, 0.0007]},
          "keys": [warm_key_from_hole(strength=1.1, color=(1.0, 0.86, 0.7), angle=1.0, dir_=(-0.3, 1.0, 0.35)),
                   {"dir": [-0.6, -0.5, 0.6], "color": [0.62, 0.72, 1.0], "strength": 0.4, "angle": 12}]}
    return {"comp": P, "tracer": {"disk": {"on": False}}, "blender": bl}

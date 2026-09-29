"""S02 — HULL (10.0–15.5). Macro glide along the hull: crinkled gold MLI, seams, stencils; the strobe
fires and lights the foil; stars behind as oval bokeh; focus pulls to the dish rim."""
import math

import numpy as np

from comp.comp import CompParams
from tls import edl
from tls.camera import Cam, Track, look, norm, smoothstep, v3
from tls.shotkit import controls, ship_matrix, ship_pos_bh, warm_key_from_hole

SHOT = edl.SHOT_BY_ID["S02"]
T0, T1 = SHOT.start, SHOT.end
pos = Track([(T0, v3(4.3, 12.2, 1.5)), (T1, v3(4.0, 19.5, 2.2))], ease=0.4)
aim = Track([(T0, v3(2.3, 14.6, 0.7)), (T1, v3(1.6, 27.5, 1.6))], ease=0.4)
focus = Track([(T0, 2.9), (T0 + 3.0, 2.9), (T0 + 4.4, 11.5), (T1, 11.5)])


def cam_at(t):
    p = pos(t)
    c = Cam(fwd=look(p, aim(t)), up=v3(0, 0, 1), pos_bh=ship_pos_bh(2600.0), pos_ship=p, hfov=34.0,
            focus=float(focus(t)), fstop=2.2)
    return c.with_drift(t, 0.06, seed=2)


def ship_at(t):
    return ship_matrix(yaw=0.0, roll=0.4 * math.sin(0.3 * t))


def params(t, q):
    c = cam_at(t)
    P = CompParams(exposure=-0.9, gains={"sky": 1.0, "stars": 1.4, "ship_env": 1.0, "ship_key": 1.0, "ship_lamps": 1.0},
                   coc_px=c.coc_inf_px(), bloom=0.04, streak=0.06, streak_threshold=8.0, halation=0.05,
                   vignette=0.34, punch=0.14, white=(0.97, 0.98, 1.02))
    bl = {"controls": controls(t), "world": {"color": [0.0004, 0.0005, 0.0007], "strength": 1.0},
          "keys": [warm_key_from_hole(strength=1.6, color=(1.0, 0.86, 0.7), angle=0.35, dir_=(0.95, 0.35, 0.28)),   # raking: crinkles alternate spec and black
                   {"dir": [0.8, -0.3, 0.55], "color": [0.62, 0.72, 1.0], "strength": 0.04, "angle": 12}]}
    return {"comp": P, "tracer": {"disk": {"on": False}}, "blender": bl}

"""S06 — GLIMPSE: LIGHT (33.5–37.0). Static close on the dish rim; for the first time warm gold light
sweeps across the foil as the ship rolls; hard shadows swing."""
import math

from comp.comp import CompParams
from tls import edl
from tls.camera import Cam, Track, look, smoothstep, v3
from tls.shotkit import controls, probe, ship_matrix, ship_pos_bh, warm_key_from_hole

SHOT = edl.SHOT_BY_ID["S06"]
T0, T1 = SHOT.start, SHOT.end
roll = Track([(T0, -38.0), (T1, 6.0)], ease=0.3)


def cam_at(t):
    p = v3(7.5, 38.5, 2.6)
    c = Cam(fwd=look(p, (1.2, 31.2, 0.4)), up=v3(0, 0, 1), pos_bh=ship_pos_bh(120.0), pos_ship=p, hfov=34.0,
            focus=9.5, fstop=4.0)
    return c.with_drift(t, 0.03, seed=6, vib_px=0.1)


def ship_at(t):
    return ship_matrix(roll=float(roll(t)), yaw=-6.0)


def params(t, q):
    c = cam_at(t)
    P = CompParams(exposure=-0.4, gains={"sky": 0.8, "stars": 1.0, "disk": 1.0, "ship_env": 0.8, "ship_key": 1.0,
                                         "ship_lamps": 1.0},
                   coc_px=c.coc_inf_px(), bloom=0.045, streak=0.07, streak_threshold=12.0, halation=0.06,
                   vignette=0.34, punch=0.16, white=(1.0, 0.96, 0.9))
    bl = {"controls": controls(t), "probe": probe(120.0, strength=1.0),
          "keys": [warm_key_from_hole(strength=4.0, color=(1.0, 0.74, 0.44), angle=1.2, dir_=(0.35, 1.0, 0.3))]}
    return {"comp": P, "tracer": {}, "blender": bl}

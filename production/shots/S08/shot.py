"""S08 — DEBRIS (41.0–46.0). The ship passes through a stream of rock and dust; rocks tumble past the
lens, rim-lit gold; shafts of light through the dust. The signal cuts out."""
import math

from comp.comp import CompParams
from tls import edl
from tls.camera import Cam, Track, look, v3
from tls.shotkit import controls, probe, ship_matrix, ship_pos_bh, warm_key_from_hole

SHOT = edl.SHOT_BY_ID["S08"]
T0, T1 = SHOT.start, SHOT.end
cp = Track([(T0, v3(-58.0, -18.0, -7.0)), (T1, v3(-52.0, 14.0, -5.0))], ease=0.2)


def cam_at(t):
    p = cp(t)
    c = Cam(fwd=look(p, (0, float(p[1]) + 16.0, 1.0)), up=v3(0, 0, 1), pos_bh=ship_pos_bh(100.0), pos_ship=p,
            hfov=44.0)
    return c.with_drift(t, 0.08, seed=8)


def ship_at(t):
    return ship_matrix(yaw=2.0, roll=4.0 + 1.5 * math.sin(0.4 * t))


def params(t, q):
    P = CompParams(exposure=-0.2, gains={"sky": 0.8, "stars": 1.0, "ship_env": 1.0, "ship_key": 1.2, "ship_lamps": 1.0},
                   bloom=0.05, glare=0.018, streak=0.07, streak_threshold=12.0, halation=0.06, vignette=0.36,
                   punch=0.18, white=(1.0, 0.95, 0.88))
    bl = {"controls": controls(t, engine=0.1), "probe": probe(100.0, strength=0.8),
          "keys": [warm_key_from_hole(strength=2.2, angle=2.5, dir_=(0.25, 1.0, 0.2))],
          "props": [{"kind": "debris", "seed": 8, "t": t}]}
    return {"comp": P, "tracer": {}, "blender": bl}

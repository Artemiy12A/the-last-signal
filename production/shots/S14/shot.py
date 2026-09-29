"""S14 — TIME (72.5–76.0). Extreme long-lens close-up of the beacon as seen from far away: each pulse
slower, the colour sinking from white to red (time dilation, felt)."""
import math

from comp.comp import CompParams
from tls import edl
from tls.camera import Cam, Track, look, smoothstep, v3
from tls.shotkit import controls, probe, ship_matrix

SHOT = edl.SHOT_BY_ID["S14"]
T0, T1 = SHOT.start, SHOT.end
aim = Track([(T0, v3(0.4, 15.9, 2.6)), (T1, v3(0.2, 15.6, 2.8))])


def cam_at(t):
    p = v3(250.0, 60.0, 330.0)
    c = Cam(fwd=look(p, aim(t)), up=v3(0, 0, 1), pos_bh=v3(0, -10.0, 1.2), pos_ship=p, hfov=2.2,
            focus=415.0, fstop=4.0)
    return c.with_drift(t, 0.004, seed=14)


def ship_at(t):
    return ship_matrix(yaw=0.0, pitch=-8.0, roll=12.0)


def params(t, q):
    u = SHOT.local(t)
    red = smoothstep(0.0, 1.0, u)
    P = CompParams(exposure=-0.8 - 1.2 * red, gains={"sky": 0.4, "stars": 0.6, "ship_env": 0.7 - 0.4 * red,
                                                     "ship_key": 0.8, "ship_lamps": 1.4},
                   white=(1.0, 0.9 - 0.35 * red, 0.8 - 0.55 * red), bloom=0.06, glare=0.02, streak=0.08,
                   halation=0.09, vignette=0.36, punch=0.22, look_sat=1.1)
    bl = {"controls": controls(t, engine=0.0, flicker=False), "probe": probe(10.0, strength=0.5), "keys": []}
    return {"comp": P, "tracer": {}, "blender": bl}

"""S06 — GLIMPSE: LIGHT (33.5–37.0). An eclipse. From just behind the high-gain dish (the ship pitched
nose-up below frame, the dish locked on the hole) we look past its back straight at the hole, which the dish hides completely. The camera slides; by parallax the
dish rim drifts across the hole and the first light breaks around its edge — the rim ignites gold, a
crescent of disk glow spills past it, the ship's body catches it in the foreground. First touch of its
light, and still nothing seen."""
import math

import numpy as np

from comp.comp import CompParams
from tls import edl
from tls.camera import Cam, Track, norm, rot, v3
from tls.shotkit import controls, probe, ship_matrix, ship_pos_bh

SHOT = edl.SHOT_BY_ID["S06"]
T0, T1 = SHOT.start, SHOT.end
D_BH = 120.0
HOLE = norm(-ship_pos_bh(D_BH))                  # direction to the hole from the ship (world = tracer axes)
PITCH = 60.0                                     # nose up: the whole ship hangs below the frame
DISH_EL = -PITCH                                 # the HGA stays locked on the hole (+el tilts it dorsal)
PIVOT = v3(0.0, 30.83, 0.0)                      # dish gimbal, ship frame
DISH_C = PIVOT + rot((1, 0, 0), math.radians(DISH_EL)) @ v3(0.0, 1.57, 0.0)   # reflector centre
RIGHT = norm(np.cross(HOLE, v3(0, 0, 1)))
UP = np.cross(RIGHT, HOLE)
slide = Track([(T0, -0.1), (T1, 3.0)], ease=0.35)   # metres up: the dish sinks and uncovers the lensed arch, a crescent along its rim
HFOV = 50.0


def ship_at(t):
    return ship_matrix(pitch=PITCH, roll=2.0)


def cam_at(t):
    d = (ship_at(t) @ [*DISH_C, 1.0])[:3]
    p = d - 18.0 * HOLE + float(slide(t)) * UP
    # the hole sits a little above centre; the dish sinks below it
    f = norm(rot(RIGHT, math.radians(3.0)) @ HOLE)
    c = Cam(fwd=f, up=v3(0, 0, 1), pos_bh=ship_pos_bh(D_BH), pos_ship=p, hfov=HFOV, focus=18.0, fstop=4.0)
    return c.with_drift(t, 0.03, seed=6)


def params(t, q):
    c = cam_at(t)
    P = CompParams(exposure=0.9, gains={"sky": 0.7, "stars": 0.8, "disk": 0.8, "haze": 0.3, "ship_env": 0.9,
                                         "ship_key": 1.1, "ship_lamps": 1.0},
                   coc_px=c.coc_inf_px(), bloom=0.05, glare=0.02, streak=0.06, streak_threshold=14.0,
                   halation=0.08, vignette=0.36, punch=0.3, look_sat=1.05, saturation=0.8, white=(1.0, 0.97, 0.93))
    bl = {"controls": controls(t, dish_el=DISH_EL), "probe": probe(D_BH, strength=1.0),
          # the hole's light from behind the dish, plus a grazing sliver from the side so the rim catches gold
          "keys": [{"dir": list(map(float, HOLE)), "color": [1.0, 0.76, 0.5], "strength": 5.0, "angle": 3.0},
                   {"dir": list(map(float, norm(HOLE + 0.55 * UP))), "color": [1.0, 0.8, 0.55], "strength": 2.5,
                    "angle": 2.0}]}
    return {"comp": P, "tracer": {}, "blender": bl}

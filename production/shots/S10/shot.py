"""S10 — THE REVEAL (48.5–60.0). Crane up over the ship; the whole black hole; slow push; hold.

Tracer camera ~72 M from the hole, 4° above the disk plane (the iconic near-edge-on view).
The first ~2.5 s the camera looks down at the ship's aft (ship layer) with the hole's light
rimming it; the tilt-up reveals the hole; then an 8 s push in with operated drift.
"""
import math

import numpy as np

from comp.comp import CompParams
from tls import edl, world
from tls.camera import Cam, Track, look, norm, orbit_pos, smoothstep, spring_follow, v3
from tls.shotkit import controls, ship_matrix

SHOT = edl.SHOT_BY_ID["S10"]
T0, T1 = SHOT.start, SHOT.end

# distance (M), inclination (deg) and look-target height (M) over time
dist = Track([(T0, 78.0), (T0 + 3.0, 76.0), (T1, 66.0)], ease=0.6)
incl = Track([(T0, 86.3), (T1, 85.6)])
tilt = Track([(T0, -9.0), (T0 + 1.2, -7.5), (T0 + 3.4, 0.0), (T1, 0.4)])     # degrees of tilt below the hole
fov = Track([(T0, 40.0), (T1, 35.0)], ease=0.5)
_tilt = spring_follow(lambda t: np.array([float(tilt(t))]), T0, T1 + 0.5, zeta=0.85, fn=0.45)


def cam_at(t: float) -> Cam:
    p = orbit_pos(float(dist(t)), float(incl(t)), -90.0)
    f = look(p, (0, 0, 0))
    r = norm(np.cross(f, (0, 0, 1)))
    u = np.cross(r, f)
    a = math.radians(float(_tilt(t)[0]))
    f2 = norm(math.cos(a) * f + math.sin(a) * u)
    c = Cam(fwd=f2, up=u, pos_bh=p, pos_ship=crane(t), hfov=float(fov(t)))
    return c.with_drift(t, 0.05, seed=10)


# the crane: from low behind the ship (its hull hides the hole) up and over it
crane = Track([(T0, v3(0.0, -34.0, 2.5)), (T0 + 1.0, v3(0.0, -35.0, 4.0)), (T0 + 3.6, v3(0.0, -38.0, 21.0)),
               (T1, v3(0.0, -44.0, 30.0))], ease=0.0)


def ship_at(t):
    return ship_matrix(pitch=0.5, roll=-1.5 + 0.5 * math.sin(0.3 * t))


def params(t: float, q: str) -> dict:
    u = SHOT.local(t)
    P = CompParams(exposure=-0.7, gains={"sky": 0.5, "stars": 0.9}, bloom=0.04, glare=0.014, streak=0.05,
                   halation=0.05, vignette=0.3, punch=0.3, look_sat=1.3, saturation=1.1, white=(1.0, 0.97, 0.92))
    # the braam lands with the reveal: a breath of overexposure that settles
    P.exposure += 0.35 * math.exp(-max(t - (T0 + 2.8), 0) / 1.2) * smoothstep(T0 + 1.8, T0 + 2.8, t)
    bl = {"controls": controls(t, engine=0.0), "probe": {"pos_bh": [float(x) for x in orbit_pos(float(dist(t)), float(incl(t)), -90.0)],
                                                        "strength": 1.0},
          "keys": [], "hide_ship": t > T0 + 5.0}
    return {"comp": P, "tracer": {}, "blender": bl}

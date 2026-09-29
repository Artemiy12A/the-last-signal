"""S01 — THE DEEP (3.0–10.0). Extreme wide starfield, the Milky Way diagonal, total stillness.
A single point of light crosses: our ship's strobe blinking the motif. Tracer sky only."""
import math

import numpy as np

from comp.comp import CompParams
from tls import edl, world
from tls.camera import Cam, Track, norm, rot, smoothstep, v3
from tls.shotkit import ship_pos_bh

SHOT = edl.SHOT_BY_ID["S01"]
T0, T1 = SHOT.start, SHOT.end
G2W = world.SKY_ROT.T                     # galactic -> world
FWD0 = norm(G2W @ world.galactic(12.0, -4.0))
yaw = Track([(T0, -0.6), (T1, 0.6)])


def cam_at(t):
    up0 = v3(0, 0, 1)
    f = rot(up0, math.radians(float(yaw(t)))) @ FWD0
    # roll the frame so the Milky Way runs corner to corner
    r = norm(np.cross(f, up0)); u = np.cross(r, f)
    a = math.radians(-18.0)
    u2 = math.cos(a) * u + math.sin(a) * r
    return Cam(fwd=f, up=u2, pos_bh=ship_pos_bh(3000.0), hfov=52.0).with_drift(t, 0.02, seed=1)


def params(t, q):
    u = SHOT.local(t)
    fade = smoothstep(T0, T0 + 1.6, t)
    x = 0.28 + 0.34 * u
    y = 0.60 - 0.05 * u
    b = edl.beacon_intensity(t)
    sprites = [
        {"x": x, "y": y, "rgb": [v * 420 * b for v in (0.85, 0.92, 1.0)], "sigma_px": 1.1},
        {"x": x - 0.0016, "y": y + 0.0004, "rgb": [6.0, 0.25, 0.12], "sigma_px": 0.8},
        {"x": x + 0.0016, "y": y + 0.0004, "rgb": [0.2, 4.0, 0.8], "sigma_px": 0.8},
    ]
    P = CompParams(exposure=0.6, gains={"sky": 0.75, "stars": 0.7}, bloom=0.03, glare=0.006, streak=0.015,
                   streak_threshold=20.0, streak_len=110.0, saturation=0.85, halation=0.03, vignette=0.32, punch=0.1, look_sat=1.0,
                   white=(0.96, 0.98, 1.03), fade=fade, sprites=sprites)
    return {"comp": P, "tracer": {"disk": {"on": False}}}

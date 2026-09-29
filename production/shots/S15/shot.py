"""S15 — THE FALL (76.0–82.5). Wide and far: our ship's beacon — a point of light — falls toward the
shadow. The tracer follows its light along real Kerr geodesics: the image slides to the shadow's edge,
a lensed second image appears, pulses stretch (time dilation), colour sinks from xenon white to red,
and it fades — frozen at the horizon. The last flash echoes around the photon ring.
"""
import math
from functools import lru_cache

import numpy as np

from comp.comp import CompParams
from tls import edl, world
from tls.camera import Cam, Track, look, norm, orbit_pos, smoothstep, v3
from tls.geodesic import fall

SHOT = edl.SHOT_BY_ID["S15"]
T0, T1 = SHOT.start, SHOT.end

X0 = [-2.2, -4.0, 9.5]         # ship start (M), high above the disk plane, between camera and hole
V0 = [0.04, 0.06, -0.16]       # coordinate velocity dx/dt
BEACON_RATE = 5.0              # M of camera coordinate time per film second
T_CAM0 = 58.0                  # camera coordinate time at the start of the shot
MOTIF_M = 6.0                  # ship proper time per motif cycle (M)


@lru_cache(maxsize=1)
def worldline():
    return fall(X0, V0, world.SPIN)


def pulses():
    """(tau_start, duration) of every strobe flash in ship proper time."""
    out = []
    tau_end = worldline()[-1, 8]
    k = 0
    while True:
        base = k * MOTIF_M
        if base > tau_end:
            break
        for off, long_ in edl.MOTIF:
            tau = base + off * MOTIF_M / edl.BEACON_CYCLE * 1.0
            out.append((tau, (edl.FLASH_LONG if long_ else edl.FLASH_SHORT) * MOTIF_M / edl.BEACON_CYCLE))
        k += 1
    return out


dist = Track([(T0, 54.0), (T1, 49.0)], ease=0.3)
aim = Track([(T0, v3(-0.8, 0, 4.9)), (T0 + 2.5, v3(-0.7, 0, 3.4)), (T1, v3(-0.5, 0, 2.4))])


def cam_at(t: float) -> Cam:
    p = orbit_pos(float(dist(t)), 85.5, -92.0)
    c = Cam(fwd=look(p, aim(t)), up=v3(0, 0, 1), pos_bh=p, hfov=34.0)
    return c.with_drift(t, 0.03, seed=15)


def params(t: float, q: str) -> dict:
    u = SHOT.local(t)
    wl = worldline()
    beacon = {
        "table": wl.tolist(), "t_cam": T_CAM0 + BEACON_RATE * (t - T0), "t_span": BEACON_RATE * 0.5 / edl.FPS,
        "sigma": 0.08, "intensity": 400.0, "T": 11000.0, "p_g": 4.0, "decay": 0.35, "steady": 0.04,
        "pulses": [list(p) for p in pulses()],
    }
    P = CompParams(exposure=-0.7 - 0.8 * smoothstep(0.55, 1.0, u), gains={"sky": 0.45, "stars": 0.8, "beacon": 1.0, "disk": 0.4, "haze": 0.4},
                   bloom=0.045, glare=0.016, streak=0.09, streak_threshold=12.0, halation=0.07, vignette=0.34,
                   punch=0.3, look_sat=1.3, saturation=1.1, white=(1.0, 0.94, 0.86))
    return {"comp": P, "tracer": {"beacon": beacon}}

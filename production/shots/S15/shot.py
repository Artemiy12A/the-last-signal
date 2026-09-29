"""S15 — THE FALL (76.0–82.5). Wide, from high above the disk: our ship's beacon — a point of light — falls toward the
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
BEACON_RATE = 3.6              # M of camera coordinate time per film second (the same fall over 9 s)
T_CAM0 = 72.0                  # camera coordinate time at the start of the shot (+14 M of light travel for the wider vantage)
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


dist = Track([(T0, 68.0), (T1, 62.0)], ease=0.3)
# higher than the reveal (S10 is 4 deg above the disk, this is 18): the disk opens into an ellipse and
# the beacon falls into it from above; the hole sits in the right third
aim = Track([(T0, v3(-6.5, 0, 6.5)), (T0 + 2.5, v3(-6.0, 0, 5.0)), (T1, v3(-5.2, 0, 3.8))])
INCL = 72.0


def cam_at(t: float) -> Cam:
    p = orbit_pos(float(dist(t)), INCL, -92.0)
    c = Cam(fwd=look(p, aim(t)), up=v3(0, 0, 1), pos_bh=p, hfov=36.0)
    return c.with_drift(t, 0.03, seed=15)


def params(t: float, q: str) -> dict:
    u = SHOT.local(t)
    wl = worldline()
    # flash timing = the EDL's motif on the steered ship clock (physics P21); position, lensing, colour
    # (T * g) and dimming (g^p_g) = the worldline, traced. Between flashes a faint ember: the ship's hull
    # and running lights, so the point never leaves the frame before the cut.
    env = edl.beacon_intensity(t)
    beacon = {
        "table": wl.tolist(), "t_cam": T_CAM0 + BEACON_RATE * (t - T0), "t_span": BEACON_RATE * 0.5 / edl.FPS,
        "sigma": 0.04, "intensity": 2200.0, "T": 6000.0, "p_g": 2.0, "decay": 0.35,
        "steady": 0.035 + env, "pulses": [],
    }
    red = smoothstep(0.35, 1.0, u)
    P = CompParams(exposure=-0.3 - 0.7 * red,
                   gains={"sky": 0.45 - 0.2 * red, "stars": 0.8 - 0.4 * red, "beacon": 1.0,
                          "disk": 0.32 - 0.16 * red, "haze": 0.3},
                   bloom=0.05, glare=0.016, streak=0.02, streak_threshold=10.0, streak_len=70.0, halation=0.08,
                   vignette=0.36, punch=0.3, look_sat=1.0, saturation=0.8 + 0.25 * red,
                   white=(1.0, 0.92 - 0.14 * red, 0.84 - 0.3 * red))
    return {"comp": P, "tracer": {"beacon": beacon}}

"""TITLE (84.5–89.0): THE LAST SIGNAL over black. Fades up on the sting, holds, breathes out."""
import math

from comp.comp import CompParams
from tls import edl
from tls.camera import Cam, smoothstep, v3

SHOT = edl.SHOT_BY_ID["TITLE"]
T0, T1 = SHOT.start, SHOT.end


def cam_at(t):
    return Cam(fwd=v3(0, 1, 0))


X, Y = 0.633, 0.595                # where the falling light was last seen (S15, BTN)


def _blink(t):
    """The motif's three shorts at the signal's tempo, as in the sound (edl.signal_pulses)."""
    v = 0.0
    for p in edl.signal_pulses():
        if p.t < T0 or p.t >= T1 or p.long:
            continue
        d = t - p.t
        on = edl.FLASH_SHORT * p.stretch
        if 0 <= d < on + 1.0:
            v = max(v, (1 - math.exp(-d / 0.04)) * (1.0 if d < on else math.exp(-(d - on) / 0.18)))
    return v


def params(t, q):
    a = smoothstep(T0 + 0.05, T0 + 0.9, t) * (1 - smoothstep(T1 - 1.1, T1 - 0.1, t))
    # a faint shiver on the sting, then steady
    a *= 1.0 - 0.25 * math.exp(-max(t - T0 - 0.1, 0) / 0.25) * (0.5 + 0.5 * math.sin(t * 90))
    # bigger and less tracked than a hairline credit: it has to survive a phone (review round 2)
    title = {"text": "THE LAST SIGNAL", "opacity": a, "glow": 0.32, "size": 0.034, "tracking": 0.5,
             "weight": 500, "y": 0.47, "color": (0.92, 0.89, 0.84),
             "ring": {"opacity": 0.09 * a, "radius": 0.36, "width": 0.0016}}
    k = 0.012 + _blink(t)
    sp = [{"x": X, "y": Y, "rgb": [200.0 * k, 55.0 * k, 16.0 * k], "sigma_px": 2.0}]
    P = CompParams(title=title, sprites=sp, bloom=0.08, glare=0.012, streak=0.0, halation=0.12, vignette=0.0,
                   punch=0.2)
    return {"black": True, "comp": P}

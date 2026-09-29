"""TITLE (84.5–89.0): THE LAST SIGNAL over black. Fades up on the sting, holds, breathes out."""
import math

from comp.comp import CompParams
from tls import edl
from tls.camera import Cam, smoothstep, v3

SHOT = edl.SHOT_BY_ID["TITLE"]
T0, T1 = SHOT.start, SHOT.end


def cam_at(t):
    return Cam(fwd=v3(0, 1, 0))


def params(t, q):
    a = smoothstep(T0 + 0.05, T0 + 0.9, t) * (1 - smoothstep(T1 - 1.1, T1 - 0.1, t))
    # a faint shiver on the sting, then steady
    a *= 1.0 - 0.25 * math.exp(-max(t - T0 - 0.1, 0) / 0.25) * (0.5 + 0.5 * math.sin(t * 90))
    # heavier than a hairline so it survives a phone and re-encoding; a faint photon ring behind it
    title = {"text": "THE LAST SIGNAL", "opacity": a, "glow": 0.32, "size": 0.029, "tracking": 0.72,
             "weight": 420, "y": 0.5, "color": (0.92, 0.89, 0.84),
             "ring": {"opacity": 0.05 * a, "radius": 0.33, "width": 0.0016}}
    return {"black": True, "comp": CompParams(title=title)}

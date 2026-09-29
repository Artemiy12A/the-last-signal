"""BTN — BUTTON (89.0–90.0). Black. Where S15 left the ship's light, frozen at the shadow's edge, one dim
red point pulses once with the last signal — the ship's strobe and the signal are now the same thing.
Then nothing."""
import math

from comp.comp import CompParams
from tls import edl
from tls.camera import Cam, smoothstep, v3

SHOT = edl.SHOT_BY_ID["BTN"]
T0, T1 = SHOT.start, SHOT.end
T_PULSE = 89.05                    # edl: the last signal pulse (sound cue "last_signal")
X, Y = 0.62, 0.52                  # where the beacon froze in the last frames of S15


def cam_at(t):
    return Cam(fwd=v3(0, 1, 0))


def params(t, q):
    dt = t - T_PULSE
    env = 0.0 if dt < 0 else (1 - math.exp(-dt / 0.06)) * math.exp(-dt / 0.45)
    env *= 1 - smoothstep(T1 - 0.25, T1 - 0.02, t)          # exact black by 90.0
    glow = 0.012 * (1 - smoothstep(T1 - 0.4, T1 - 0.05, t))  # the frozen remnant, barely there
    k = env + glow
    sp = [{"x": X, "y": Y, "rgb": [200.0 * k, 55.0 * k, 16.0 * k], "sigma_px": 2.0}]
    P = CompParams(sprites=sp, bloom=0.08, glare=0.012, streak=0.03, streak_threshold=6.0, halation=0.12,
                   vignette=0.0, grain=0.0, punch=0.2)
    return {"black": True, "comp": P}

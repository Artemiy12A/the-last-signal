"""S13 — INTERFERENCE (69.5–72.5). The ship's forward view as it accelerates: the shadow swelling,
stars compressing and blue-shifting ahead (aberration), the image tearing with the signal."""
import math

from comp.comp import CompParams
from tls import edl
from tls.camera import Cam, Track, look, norm, orbit_pos, v3

SHOT = edl.SHOT_BY_ID["S13"]
T0, T1 = SHOT.start, SHOT.end
dist = Track([(T0, 17.0), (T1, 11.5)], ease=0.5)
beta = Track([(T0, 0.25), (T1, 0.62)], ease=0.6)


def cam_at(t):
    p = orbit_pos(float(dist(t)), 83.5, -90.0)
    f = look(p, (0, 0, 0.6))
    c = Cam(fwd=f, up=v3(0, 0, 1), pos_bh=p, hfov=78.0, vel=f * float(beta(t)))
    return c.with_drift(t, 0.12, seed=13, vib_px=0.5)


def params(t, q):
    u = SHOT.local(t)
    P = CompParams(exposure=-1.2 - 0.4 * u, gains={"sky": 0.6, "stars": 1.0}, bloom=0.06, glare=0.025, streak=0.08,
                   halation=0.08, vignette=0.38, punch=0.22, look_sat=1.1, white=(1.0, 0.97, 0.95),
                   interference=edl.interference(t), ca=2.0 + 3.0 * u)
    return {"comp": P, "tracer": {"sky": {"doppler": 0.6}}}

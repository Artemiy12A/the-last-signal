"""S05 — THE PULL (28.0–33.5). Wide 3/4 rear: the ship small at left, heading for a hair-thin golden
line ringed by doubled, smeared starlight."""
import math

from comp.comp import CompParams
from tls import edl
from tls.camera import Cam, Track, norm, rot, v3
from tls.shotkit import cam_pos_for_screen, controls, probe, ship_matrix, ship_pos_bh

SHOT = edl.SHOT_BY_ID["S05"]
T0, T1 = SHOT.start, SHOT.end
dist = Track([(T0, 156.0), (T1, 146.0)])
cp = Track([(T0, v3(165.0, -430.0, -18.0)), (T1, v3(150.0, -400.0, -14.0))])


def cam_at(t):
    f = norm(rot((0, 0, 1), math.radians(7.0)) @ rot((1, 0, 0), math.radians(1.0)) @ v3(0, 1, 0))
    u = SHOT.local(t)
    ps = cam_pos_for_screen(f, (0, 0, 1), 0.2 + 0.06 * u, 0.58, 230.0 - 15.0 * u, 46.0, target=(0, 2.0, 0))
    c = Cam(fwd=f, up=v3(0, 0, 1), pos_bh=ship_pos_bh(float(dist(t)), incl=88.8), pos_ship=ps, hfov=46.0)
    return c.with_drift(t, 0.035, seed=5)


def ship_at(t):
    return ship_matrix(yaw=-38.0, pitch=2.0, roll=-8.0)


def params(t, q):
    P = CompParams(exposure=0.4, gains={"sky": 1.1, "stars": 1.2, "disk": 0.0, "haze": 0.0, "ship_env": 1.0, "ship_key": 1.0, "ship_lamps": 1.0},
                   bloom=0.035, streak=0.06, streak_threshold=10.0, halation=0.05, vignette=0.33, punch=0.14,
                   white=(1.0, 0.97, 0.94), interference=0.25 * edl.interference(t))
    bl = {"controls": controls(t, engine=0.2), "probe": probe(float(dist(t)), strength=1.0, incl=88.8),
          "keys": []}
    # no disk at all: a zero-gain disk still blocked starlight (a black bar through the shadow)
    return {"comp": P, "tracer": {"disk": {"on": False}}, "blender": bl}

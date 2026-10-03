"""S11 — SCALE (60.0–65.5). Long lens from far behind: the ship a speck silhouetted against the
blazing lensed arch; faint blue engine thread; beacon pulsing."""
import math

from comp.comp import CompParams
from tls import edl
from tls.camera import Cam, Track, look, norm, rot, v3
from tls.shotkit import cam_pos_for_screen, controls, probe, ship_matrix, ship_pos_bh

SHOT = edl.SHOT_BY_ID["S11"]
T0, T1 = SHOT.start, SHOT.end
dist = Track([(T0, 67.0), (T1, 64.0)])
cp = Track([(T0, v3(-40.0, -1300.0, -62.0)), (T1, v3(-30.0, -1240.0, -58.0))])


def cam_at(t):
    # review round 2: from just below the disk plane, against the lower lensed ring (S10/S12 look from above)
    pb = ship_pos_bh(float(dist(t)), incl=95.5)
    f = norm(look(pb, (0, 0, -3.0)))
    u = SHOT.local(t)
    ps = cam_pos_for_screen(f, (0, 0, 1), 0.34 + 0.03 * u, 0.84, 2700.0 - 100.0 * u, 16.0)   # ~9% of frame, on the bright band under the shadow
    c = Cam(fwd=f, up=v3(0, 0, 1), pos_bh=pb, pos_ship=ps, hfov=16.0)
    return c.with_drift(t, 0.035, seed=11)


def ship_at(t):
    return ship_matrix(yaw=-78.0, pitch=2.0 + 0.3 * math.sin(0.2 * t), roll=-6.0)   # broadside: its profile reads


def params(t, q):
    P = CompParams(exposure=0.6, gains={"sky": 0.4, "stars": 0.8, "ship_env": 1.0, "ship_key": 1.0, "ship_lamps": 4.0},
                   bloom=0.045, glare=0.016, streak=0.06, halation=0.06, vignette=0.3, punch=0.4, look_sat=1.15, saturation=0.85,
                   white=(1.0, 0.96, 0.9))
    bl = {"controls": controls(t, engine=0.1), "probe": probe(float(dist(t)), strength=1.0, incl=95.5), "keys": []}
    return {"comp": P, "tracer": {}, "blender": bl}

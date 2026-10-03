"""S14 — LAST LOOK (72.5–76.0). Macro on the dorsal beacon, the motif's source, sharp in the foreground;
behind it the hole fills the frame as soft oval bokeh — the shadow and the lensed arch, 10 M away. The
strobe fires against the blaze: an echo of S02's first flash in the dark. Its clock is just beginning to
slow (edl.ship_rate x1 -> x1.2 here, what r ~ 10 M really gives); the next shot pulls out to watch this
same light fall."""
import math

from comp.comp import CompParams
from tls import edl
from tls.camera import Cam, Track, norm, v3
from tls.shotkit import cam_pos_for_screen, controls, probe, ship_matrix, ship_pos_bh

SHOT = edl.SHOT_BY_ID["S14"]
T0, T1 = SHOT.start, SHOT.end
BEACON = v3(0.0, 15.73, 2.751)        # flush xenon dome (ship_build: review round 2)
HFOV = 40.0
dist = Track([(T0, 4.2), (T1, 3.4)], ease=0.3)                 # slow push onto the lamp
fwd = Track([(T0, v3(-0.34, 1.0, -0.075)), (T1, v3(-0.3, 1.0, -0.06))], ease=0.3)   # just above the hull top, the lamp against the shadow


def cam_at(t):
    f = norm(fwd(t))
    d = float(dist(t))
    b = (ship_at(t) @ [*BEACON, 1.0])[:3]                     # the lamp where the posed ship carries it
    p = cam_pos_for_screen(f, (0, 0, 1), 0.60, 0.37, d, HFOV, target=b)   # where S15's point of light starts: a match cut
    c = Cam(fwd=f, up=v3(0, 0, 1), pos_bh=ship_pos_bh(10.0), pos_ship=p, hfov=HFOV, focus=d, fstop=2.0)
    return c.with_drift(t, 0.05, seed=14, vib_px=0.3)


def ship_at(t):
    return ship_matrix(yaw=80.0, pitch=-3.0, roll=6.0)   # broadside to the hole: the hull falls away


def params(t, q):
    c = cam_at(t)
    P = CompParams(exposure=-1.0, gains={"sky": 0.4, "stars": 0.6, "disk": 0.6, "haze": 0.6,
                                         "ship_env": 1.0, "ship_key": 1.0, "ship_lamps": 1.2},
                   coc_px=c.coc_inf_px(), white=(1.0, 0.95, 0.9), bloom=0.03, glare=0.006, streak=0.0,  # the lens is 50 px wide here: a streak would be a bar
                  
                   streak_threshold=30.0, streak_len=140.0, halation=0.08, vignette=0.36, punch=0.4, look_sat=1.15, saturation=0.85)
    bl = {"controls": controls(t, engine=0.0, flicker=False), "probe": probe(10.0, strength=1.0),
          "keys": [{"dir": [-0.15, 1.0, 0.3], "color": [1.0, 0.8, 0.6], "strength": 1.2, "angle": 25.0}]}
    return {"comp": P, "tracer": {}, "blender": bl}

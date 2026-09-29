"""S09 — BREATH (46.0–48.5). Near-silence. Low behind the ship: its dish silhouetted against a glowing
veil of dust with the hole's light behind it."""
from comp.comp import CompParams
from tls import edl
from tls.camera import Cam, Track, look, v3
from tls.shotkit import controls, ship_matrix, ship_pos_bh

SHOT = edl.SHOT_BY_ID["S09"]
T0, T1 = SHOT.start, SHOT.end
cp = Track([(T0, v3(1.2, -22.0, 3.9)), (T1, v3(1.0, -19.0, 3.7))])


def cam_at(t):
    p = cp(t)
    f = look(p, (0.0, 52.0, -0.2))
    c = Cam(fwd=f, up=v3(0, 0, 1), pos_bh=ship_pos_bh(86.0), pos_ship=p, hfov=34.0)
    return c.with_drift(t, 0.03, seed=9)


def ship_at(t):
    return ship_matrix()


def params(t, q):
    P = CompParams(exposure=-1.0, gains={"sky": 0.3, "stars": 0.4, "disk": 0.6, "haze": 3.0,
                                         "ship_env": 0.6, "ship_key": 0.5, "ship_lamps": 1.0},
                   coc_px=70.0, bloom=0.08, glare=0.03, streak=0.04, halation=0.06, vignette=0.4, punch=0.2,
                   white=(1.0, 0.93, 0.84))
    bl = {"controls": controls(t, engine=0.0, flicker=False), "world": {"color": [0.0, 0.0, 0.0]},
          "keys": [{"dir": [0.0, 1.0, 0.15], "color": [1.0, 0.72, 0.45], "strength": 1.5, "angle": 6.0}]}
    return {"comp": P, "tracer": {"disk": {"haze": 0.02, "haze_h": 0.25}}, "blender": bl}

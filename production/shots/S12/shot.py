"""S12 — UNDER THE ARCH (65.5–69.5). Grazing skim a third of a mass above the turbulent disk at
r ~ 15 M, sweeping against the flow: the surface rushes underneath, the lensed arch towers overhead
filling the top of frame, the ship a silhouette far ahead. Dutch angle, hull-borne vibration."""
import math

import numpy as np

from comp.comp import CompParams
from tls import edl
from tls.camera import Cam, Track, look, norm, rot, v3
from tls.shotkit import controls, ship_matrix

SHOT = edl.SHOT_BY_ID["S12"]
T0, T1 = SHOT.start, SHOT.end
r = Track([(T0, 16.5), (T1, 14.0)], ease=0.2)
h = Track([(T0, 0.9), (T1, 0.75)])   # high enough that rays to the hole clear the disk's upper layers
az = Track([(T0, -84.0), (T1, -104.0)], ease=0.15)   # against the disk's rotation: relative speed


def cam_at(t):
    rr = float(r(t))
    a = math.radians(float(az(t)))
    pb = v3(rr * math.cos(a), rr * math.sin(a), float(h(t)))
    f = norm(look(pb, (0, 0, 4.6)))           # look up: the disk floor is a low horizon, the arch towers
    up = norm(rot(f, math.radians(-9.0)) @ v3(0, 0, 1))
    c = Cam(fwd=f, up=up, pos_bh=pb, pos_ship=v3(8.0, -160.0, -10.0), hfov=72.0)
    return c.with_drift(t, 0.08, seed=12, vib_px=0.35)


def ship_at(t):
    return ship_matrix(yaw=-6.0, roll=8.0)


def params(t, q):
    P = CompParams(exposure=0.3, gains={"sky": 0.4, "stars": 0.8, "ship_env": 1.0, "ship_key": 1.0, "ship_lamps": 1.3},
                   bloom=0.05, glare=0.02, streak=0.07, halation=0.07, vignette=0.34, punch=0.4, look_sat=1.15, saturation=0.85,
                   white=(1.0, 0.95, 0.88))
    bl = {"controls": controls(t, engine=0.08), "probe": {"pos_bh": [float(x) for x in cam_at(t).pos_bh], "strength": 1.0},
          "keys": []}
    # the camera is inside the haze layer: thin it so the shadow stays black
    return {"comp": P, "tracer": {"disk": {"octaves": 7, "haze": 0.0005}}, "blender": bl}

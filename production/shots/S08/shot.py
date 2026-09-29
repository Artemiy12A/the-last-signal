"""S08 — DEBRIS (41.0–46.0). Long lens from 360 m: the ship, a third of the frame, holds course while a
stream of infalling rock overtakes it towards the unseen light at frame left. Rocks are raked gold from
the left (3/4 back light, 60 degrees off the lens axis); near rocks sweep through the lens as soft blurs;
three far boulders up-light of the ship cut shadow wedges through the dust. The signal cuts out."""
import math

import numpy as np

from comp.comp import CompParams
from tls import edl
from tls.camera import Cam, Track, norm, v3
from tls.shotkit import cam_pos_for_screen, controls, probe, ship_matrix, ship_pos_bh

SHOT = edl.SHOT_BY_ID["S08"]
T0, T1 = SHOT.start, SHOT.end
HFOV = 28.0
az = Track([(T0, 35.5), (T1, 41.0)], ease=0.25)      # view azimuth from +X (deg): slow orbit for parallax
dist = Track([(T0, 400.0), (T1, 335.0)], ease=0.25)  # slow push
EL = -7.0                                            # looking slightly down
VEL = v3(3.0, 44.0, -1.5)                            # rock stream relative to the ship (m/s): overtaking
LIGHT = norm(v3(-0.1, 1.0, 0.25))                    # towards the disk's light (off frame left)
TARGET = v3(0.0, 2.0, 0.0)


def _fwd(t):
    a, e = math.radians(az(t)), math.radians(EL)
    return v3(math.cos(e) * math.cos(a), math.cos(e) * math.sin(a), math.sin(e))


def cam_at(t):
    f = _fwd(t)
    p = cam_pos_for_screen(f, (0, 0, 1), 0.63, 0.54, float(dist(t)), HFOV, target=TARGET)
    c = Cam(fwd=f, up=v3(0, 0, 1), pos_bh=ship_pos_bh(100.0), pos_ship=p, hfov=HFOV,
            focus=float(dist(t)), fstop=1.4)
    return c.with_drift(t, 0.05, seed=8)


def ship_at(t):
    return ship_matrix(yaw=3.0, roll=5.0 + 1.5 * math.sin(0.4 * t))


def _in_frustum(rng, tau, dmin, dmax, k=1.25):
    c = cam_at(tau)
    r, u, f = c.basis()
    th = math.tan(math.radians(HFOV) / 2)
    d = rng.uniform(dmin, dmax)
    x = rng.uniform(-k, k) * th * d
    y = rng.uniform(-k, k) * th * d * 804 / 1920
    return c.pos_ship + f * d + r * x + u * y, d, c


def _rock(rng, p, tau, size, spin_scale=1.0):
    ax = rng.normal(size=3)
    shape = [1.0, float(rng.uniform(0.45, 0.9)), float(rng.uniform(0.3, 0.7))]
    spin = float(spin_scale * rng.uniform(-1.0, 1.0) / max(size, 0.4) ** 0.5)
    return [*map(float, p - VEL * tau), float(size), *map(float, ax), spin, *shape]


def _rocks(seed=8):
    """A sparse stream, not an asteroid field: a few rocks cross close to the lens (soft, fast), a scatter
    of mid-ground rocks gives depth, three far boulders up-light of the ship cast shadow wedges through the
    dust. Each rock is placed in the frustum at a chosen moment of the shot and moved back along the
    stream to t=0."""
    rng = np.random.default_rng(seed)
    out = []
    # near: crossing the lens at spread-out moments
    for i, tau in enumerate(np.linspace(T0 + 0.3, T1 - 0.2, 7) + rng.uniform(-0.2, 0.2, 7)):
        p, d, c = _in_frustum(rng, tau, 12.0, 70.0, k=0.8)
        out.append(_rock(rng, p, tau, rng.uniform(0.5, 2.2), 2.0))
    # mid-ground scatter, keeping a clear line of sight to the ship
    while len(out) < 7 + 64:
        tau = rng.uniform(T0 - 0.5, T1 + 0.5)
        p, d, c = _in_frustum(rng, tau, 90.0, 950.0)
        los = norm(TARGET - c.pos_ship)
        off = p - c.pos_ship
        lateral = np.linalg.norm(off - los * (off @ los))
        if lateral < 55.0 and 0 < off @ los < np.linalg.norm(TARGET - c.pos_ship) + 80:
            continue
        size = float(min(1.2 * (1 - rng.uniform(0, 0.97)) ** (-1 / 1.5), 9.0))
        out.append(_rock(rng, p, tau, size))
    # boulders up-light of the ship
    for k, (sz, dx, dz) in enumerate([(34.0, -60.0, 10.0), (22.0, 50.0, -25.0), (28.0, -10.0, 60.0)]):
        p = TARGET + LIGHT * (230.0 + 70.0 * k) + v3(dx, 0.0, dz)       # where it is mid-shot
        out.append([*map(float, p - VEL * (T0 + T1) / 2), sz, 0.3, 1.0, 0.2, 0.02, 1.0, 0.7, 0.55])
    return out


ROCKS = _rocks()


def params(t, q):
    P = CompParams(exposure=0.3, gains={"sky": 0.5, "stars": 0.45, "ship_env": 0.8, "ship_key": 1.2, "ship_lamps": 1.0},
                   bloom=0.04, glare=0.015, streak=0.06, streak_threshold=14.0, halation=0.06, vignette=0.38,
                   punch=0.3, look_sat=1.15, white=(1.0, 0.95, 0.88))
    bl = {"controls": controls(t, engine=0.1), "probe": probe(100.0, strength=0.35),
          "keys": [{"dir": list(map(float, LIGHT)), "color": [1.0, 0.74, 0.46], "strength": 9.0, "angle": 1.2}],
          "props": [{"kind": "debris", "t": t, "rocks": ROCKS, "vel": list(map(float, VEL)),
                     "dust_box": {"center": [0.0, 80.0, 20.0], "size": [1100.0, 1100.0, 420.0]},
                     "dust_density": 0.0007, "dust_scale": 0.012, "dust_range": [0.56, 0.8], "dust_stretch": [1.0, 0.22, 1.0],
                     "dust_aniso": 0.6, "dust_color": [0.85, 0.8, 0.72]}]}
    return {"comp": P, "tracer": {}, "blender": bl}

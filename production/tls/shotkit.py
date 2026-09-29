"""Shared helpers for shot modules: ship pose, EDL-driven ship lights, probes, sprites, projection."""
from __future__ import annotations

import math

import numpy as np

from . import edl, world
from .camera import Cam, norm, rot, v3

# The ship's distance from the hole (M) by shot, for continuity (approach along -Y towards +Y).
SHIP_D = {
    "S01": 3000.0, "S02": 2600.0, "S03": 2400.0, "S04": 400.0, "S05": 150.0, "S06": 120.0,
    "S08": 100.0, "S09": 86.0, "S10": 78.0, "S11": 66.0, "S12": 30.0, "S13": 16.0, "S14": 10.0,
}
APPROACH_INCL = 86.0     # degrees from the spin axis: 4 deg above the disk plane
APPROACH_AZ = -90.0      # coming in from -Y


def ship_pos_bh(d: float, incl: float = APPROACH_INCL, az: float = APPROACH_AZ, offset=(0, 0, 0)) -> np.ndarray:
    i, a = math.radians(incl), math.radians(az)
    return v3(d * math.sin(i) * math.cos(a), d * math.sin(i) * math.sin(a), d * math.cos(i)) + v3(*offset)


def ship_matrix(yaw=0.0, pitch=0.0, roll=0.0, pos=(0, 0, 0)) -> np.ndarray:
    """Ship root matrix (Blender world, metres). yaw about +Z, pitch about ship +X, roll about ship +Y.
    With zero angles the ship's bow (+Y) points at the hole along the approach."""
    R = rot((0, 0, 1), math.radians(yaw)) @ rot((1, 0, 0), math.radians(pitch)) @ rot((0, 1, 0), math.radians(roll))
    M = np.eye(4)
    M[:3, :3] = R
    M[:3, 3] = pos
    return M


def controls(t: float, beacon_gain=1.0, engine=0.0, dish_az=0.0, dish_el=0.0, running=1.0, nav=1.0,
             interior=0.4, flicker=True) -> dict:
    """Ship light controls from the EDL: strobe = beacon flashes; running/interior lights stutter when the
    signal hits (edl.interference)."""
    b = edl.beacon_intensity(t) * beacon_gain
    k = 0.0
    if flicker:
        amt = edl.interference(t)
        # deterministic stutter: a fast pseudo-random square-ish wave while the signal is hitting
        s = math.sin(t * 57.0) * math.sin(t * 23.3 + 1.7) + 0.35 * math.sin(t * 131.0)
        k = amt * (0.5 + 0.5 * math.tanh(4 * s))
    return {"beacon": b, "nav": nav * (1 - 0.7 * k), "running": running * (1 - 0.9 * k), "engine": engine,
            "interior": interior * (1 - 0.8 * k), "dish_az_deg": dish_az, "dish_el_deg": dish_el}


def probe(d: float, strength=1.0, **kw) -> dict:
    return {"pos_bh": [float(x) for x in ship_pos_bh(d, **kw)], "strength": strength}


def warm_key_from_hole(strength=2.0, color=(1.0, 0.78, 0.52), angle=4.0, dir_=(0, 1, 0.07)) -> dict:
    """Artistic sun lamp standing in for the disk's light (towards the hole = +Y)."""
    return {"dir": list(norm(dir_)), "color": list(color), "strength": strength, "angle": angle}


def project(cam: Cam, p_world, W=1920, H=804):
    """Pinhole projection of a world point (Blender metres, relative to the same origin as cam.pos_ship)
    -> (x, y) in 0..1 image coords, depth. None if behind."""
    r, u, f = cam.basis()
    d = np.asarray(p_world, float) - cam.pos_ship
    z = d @ f
    if z <= 1e-6:
        return None
    t = math.tan(math.radians(cam.hfov) / 2)
    sx = (d @ r) / z / t
    sy = (d @ u) / z / t * (W / H)
    return (0.5 + 0.5 * sx, 0.5 - 0.5 * sy, z)


def cam_pos_for_screen(fwd, up, sx: float, sy: float, dist: float, hfov: float, target=(0, 0, 0),
                       W=1920, H=804) -> np.ndarray:
    """Camera position (Blender metres) such that `target` appears at image coords (sx, sy) in 0..1,
    `dist` metres away, for a camera looking along fwd with the given up vector."""
    f = norm(fwd)
    r = norm(np.cross(f, up))
    u = np.cross(r, f)
    t = math.tan(math.radians(hfov) / 2)
    x = (2 * sx - 1) * t
    y = (1 - 2 * sy) * t * H / W
    d = norm(f + x * r + y * u)
    return np.asarray(target, float) - dist * d

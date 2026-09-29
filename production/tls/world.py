"""Story geography shared by every shot (continuity): black hole, sky orientation, ship approach.

Tracer space: M units, black hole at the origin, spin axis +Z, disk in the XY plane.
The ship approaches from -Y heading +Y, a few degrees above the disk plane.
"""
from __future__ import annotations

import math

import numpy as np

from .camera import norm, v3

SPIN = 0.8
WHITE_K = 6500.0


def galactic(l_deg: float, b_deg: float) -> np.ndarray:
    l, b = math.radians(l_deg), math.radians(b_deg)
    return v3(math.cos(b) * math.cos(l), math.cos(b) * math.sin(l), math.sin(b))


def sky_rotation(fwd_gal=(-24.0, 7.0), up_gal=(-24.0, 97.0), roll_deg=-28.0) -> np.ndarray:
    """World -> galactic rotation: world +Y (towards the hole along the approach) looks at galactic
    (l, b) = fwd_gal, world +Z is rolled by roll_deg from galactic 'up' so the Milky Way band crosses
    the frame diagonally."""
    f = galactic(*fwd_gal)
    u0 = galactic(*up_gal)
    u0 = norm(u0 - f * np.dot(u0, f))
    r0 = np.cross(f, u0)
    a = math.radians(roll_deg)
    u = math.cos(a) * u0 + math.sin(a) * r0
    r = np.cross(f, u)        # world +X
    # columns: images of world x, y, z in galactic coordinates
    return np.stack([r, f, u], axis=1)


SKY_ROT = sky_rotation()

# default physical/look parameters of the black hole (overridable per shot)
DISK = {
    "T_peak": 6500, "p_T": 4.0, "p_g": 2.0, "color_g": 1.0, "emit_gain": 3.0,
    "r_out": 22.0, "taper": 0.35, "h_over_r": 0.012, "kappa": 4.0,
    "haze": 0.002, "haze_h": 0.1, "flow_period": 0.35, "n_phi": 16,
    "clumps": 0.9, "lanes": 1.0, "arms": 0.45,
}
SKY = {"gain": 4.0, "stars_gain": 3e-5, "star_max_radius": 0.006}

# film seconds -> disk time (M). Slow and stately; ISCO orbit (~35 M) takes ~25 s of screen time.
DISK_RATE = 1.4

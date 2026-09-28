"""Small vector / easing helpers used by the timeline."""
from __future__ import annotations

import math

import numpy as np


def v3(*a) -> np.ndarray:
    if len(a) == 1:
        return np.asarray(a[0], dtype=np.float64)
    return np.array(a, dtype=np.float64)


def norm(v) -> np.ndarray:
    v = np.asarray(v, dtype=np.float64)
    return v / max(float(np.linalg.norm(v)), 1e-12)


def clamp(x, lo=0.0, hi=1.0):
    return lo if x < lo else hi if x > hi else x


def lerp(a, b, t):
    return a + (b - a) * t


def smoothstep(e0, e1, x):
    t = clamp((x - e0) / (e1 - e0))
    return t * t * (3.0 - 2.0 * t)


def ease_in_out(t):
    t = clamp(t)
    return t * t * (3.0 - 2.0 * t)


def ease_in_out_cubic(t):
    t = clamp(t)
    return 4 * t * t * t if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2


def ease_out_cubic(t):
    t = clamp(t)
    return 1 - (1 - t) ** 3


def ease_in_cubic(t):
    t = clamp(t)
    return t * t * t


def ease_out_expo(t):
    t = clamp(t)
    return 1.0 if t >= 1 else 1 - 2 ** (-10 * t)


def rot(axis, ang) -> np.ndarray:
    """Rodrigues rotation matrix."""
    a = norm(axis)
    K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    return np.eye(3) + math.sin(ang) * K + (1 - math.cos(ang)) * (K @ K)


def look_at(pos, target, up=(0.0, 1.0, 0.0), roll=0.0) -> np.ndarray:
    """Camera basis as columns (right, up, forward). Screen x grows to the right."""
    f = norm(np.asarray(target, float) - np.asarray(pos, float))
    r = norm(np.cross(np.asarray(up, float), f))
    u = np.cross(f, r)
    c, s = math.cos(roll), math.sin(roll)
    r2 = c * r + s * u
    u2 = -s * r + c * u
    return np.stack([-r2, u2, f], axis=1)


def orbit(dist, azimuth_deg, elevation_deg) -> np.ndarray:
    """Position on a sphere around the origin; azimuth 0 = -z axis."""
    az = math.radians(azimuth_deg)
    el = math.radians(elevation_deg)
    return v3(dist * math.cos(el) * math.sin(az), dist * math.sin(el), -dist * math.cos(el) * math.cos(az))


def value_noise1(x: float, seed: int = 0) -> float:
    """Smooth 1D value noise in [-1, 1] (deterministic)."""
    i = math.floor(x)
    f = x - i

    def h(n):
        n = (n * 374761393 + seed * 668265263) & 0xFFFFFFFF
        n = ((n ^ (n >> 13)) * 1274126177) & 0xFFFFFFFF
        return ((n ^ (n >> 16)) & 0xFFFF) / 32767.5 - 1.0

    u = f * f * (3 - 2 * f)
    return h(i) * (1 - u) + h(i + 1) * u


def shake(t: float, amp: float, freq: float = 1.0, seed: int = 0) -> np.ndarray:
    """Handheld-style camera shake as small (yaw, pitch, roll) angles in radians."""
    if amp <= 0:
        return np.zeros(3)
    out = []
    for k in range(3):
        s = 0.0
        for o, w in ((1.0, 1.0), (2.3, 0.45), (5.1, 0.2)):
            s += w * value_noise1(t * freq * o * 3.0 + 17.0 * k, seed + k * 7 + int(o * 10))
        out.append(s)
    return np.array(out) * amp

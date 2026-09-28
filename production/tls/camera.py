"""Camera language: keyed paths, a damped-spring "operator", 1/f drift, lens model.

World axes are Z-up and shared by the tracer (black-hole units, M) and Blender (ship units, m):
a camera is an orientation (fwd, up) plus a position in each space.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np


def v3(*a) -> np.ndarray:
    if len(a) == 1:
        return np.asarray(a[0], dtype=float)
    return np.array(a, dtype=float)


def norm(v) -> np.ndarray:
    v = np.asarray(v, dtype=float)
    n = np.linalg.norm(v)
    return v / n if n > 0 else v


def smoothstep(a, b, x):
    t = min(1.0, max(0.0, (x - a) / (b - a))) if b != a else float(x >= b)
    return t * t * (3 - 2 * t)


def ease_in_out(t, p=2.0):
    t = min(1.0, max(0.0, t))
    return t ** p / (t ** p + (1 - t) ** p) if 0 < t < 1 else t


def rot(axis, ang) -> np.ndarray:
    axis = norm(axis)
    x, y, z = axis
    c, s = math.cos(ang), math.sin(ang)
    C = 1 - c
    return np.array([[c + x * x * C, x * y * C - z * s, x * z * C + y * s],
                     [y * x * C + z * s, c + y * y * C, y * z * C - x * s],
                     [z * x * C - y * s, z * y * C + x * s, c + z * z * C]])


# ------------------------------------------------------------------ keyed tracks
@dataclass
class Track:
    """Piecewise cubic (Catmull-Rom) through keys [(t, value)], clamped at the ends.
    Values can be scalars or vectors. `ease` optionally warps time between the first and last key."""
    keys: list
    ease: float = 0.0     # 0 = linear time; >0 = ease-in-out strength over the whole track

    def __call__(self, t: float):
        ks = self.keys
        ts = [k[0] for k in ks]
        vs = [np.asarray(k[1], dtype=float) for k in ks]
        if len(ks) == 1:
            return vs[0]
        if self.ease > 0:
            u = (t - ts[0]) / (ts[-1] - ts[0])
            u = min(1.0, max(0.0, u))
            u = ease_in_out(u, 1.0 + self.ease)
            t = ts[0] + u * (ts[-1] - ts[0])
        if t <= ts[0]:
            return vs[0]
        if t >= ts[-1]:
            return vs[-1]
        i = max(0, min(len(ts) - 2, int(np.searchsorted(ts, t) - 1)))
        t0, t1 = ts[i], ts[i + 1]
        p0, p1 = vs[i], vs[i + 1]
        pm = vs[i - 1] if i > 0 else p0 - (p1 - p0)
        pp = vs[i + 2] if i + 2 < len(vs) else p1 + (p1 - p0)
        tm = ts[i - 1] if i > 0 else t0 - (t1 - t0)
        tp = ts[i + 2] if i + 2 < len(ts) else t1 + (t1 - t0)
        h = t1 - t0
        m0 = (p1 - pm) / (t1 - tm) * h
        m1 = (pp - p0) / (tp - t0) * h
        u = (t - t0) / h
        u2, u3 = u * u, u * u * u
        return (2 * u3 - 3 * u2 + 1) * p0 + (u3 - 2 * u2 + u) * m0 + (-2 * u3 + 3 * u2) * p1 + (u3 - u2) * m1


def spring_follow(target, t0: float, t1: float, zeta: float = 0.8, fn: float = 0.5, dt: float = 1 / 480,
                  lead: float = 0.0):
    """Simulate a damped spring (critically-ish damped operator) following target(t) over [t0 - 2 s, t1].
    Returns a callable f(t) interpolating the simulated response. `lead` pre-rolls the target."""
    w = 2 * math.pi * fn
    start = t0 - 2.0
    n = int(math.ceil((t1 - start) / dt)) + 2
    x = np.asarray(target(start + lead), dtype=float).copy()
    v = np.zeros_like(x)
    ts = np.empty(n)
    xs = np.empty((n,) + x.shape)
    for i in range(n):
        t = start + i * dt
        ts[i] = t
        xs[i] = x
        a = w * w * (np.asarray(target(t + lead), dtype=float) - x) - 2 * zeta * w * v
        v = v + a * dt
        x = x + v * dt

    def f(t):
        u = (t - start) / dt
        i = int(min(max(math.floor(u), 0), n - 2))
        fr = min(max(u - i, 0.0), 1.0)
        return xs[i] * (1 - fr) + xs[i + 1] * fr
    return f


def pink_drift(t: float, amp: float, seed: int, fmin=0.05, fmax=2.0, n=10) -> float:
    """Band-limited 1/f noise (sum of sines, amplitude ~ 1/f), deterministic, roughly unit RMS * amp."""
    rng = np.random.default_rng(seed)
    fs = np.exp(np.linspace(math.log(fmin), math.log(fmax), n))
    ph = rng.uniform(0, 2 * math.pi, n)
    a = 1.0 / fs
    a = a / math.sqrt((a * a).sum() / 2)
    return float(amp * np.sum(a * np.sin(2 * math.pi * fs * t + ph)))


def vibration(t: float, amp: float, seed: int, fmin=8.0, fmax=15.0, n=6) -> float:
    rng = np.random.default_rng(seed + 991)
    fs = rng.uniform(fmin, fmax, n)
    ph = rng.uniform(0, 2 * math.pi, n)
    return float(amp * np.sum(np.sin(2 * math.pi * fs * t + ph)) / math.sqrt(n / 2))


# ------------------------------------------------------------------ camera state
@dataclass
class Cam:
    fwd: np.ndarray
    up: np.ndarray = field(default_factory=lambda: v3(0, 0, 1))
    pos_bh: np.ndarray = field(default_factory=lambda: v3(0, -80, 0))    # tracer space (M)
    pos_ship: np.ndarray = field(default_factory=lambda: v3(0, -30, 0))  # Blender space (m), ship at origin
    hfov: float = 40.0              # degrees, horizontal
    focus: float = 1e9              # m (Blender space)
    fstop: float = 8.0
    vel: np.ndarray = field(default_factory=lambda: v3(0, 0, 0))         # fraction of c (tracer boost)

    def basis(self):
        f = norm(self.fwd)
        r = norm(np.cross(f, self.up))
        u = np.cross(r, f)
        return r, u, f

    def with_drift(self, t: float, amp_deg: float, seed: int, roll_frac=0.3, vib_px=0.0, width=1920):
        """Apply operated drift (and optional hull vibration) as small rotations."""
        r, u, f = self.basis()
        yaw = math.radians(pink_drift(t, amp_deg, seed))
        pitch = math.radians(pink_drift(t, amp_deg, seed + 17))
        roll = math.radians(pink_drift(t, amp_deg * roll_frac, seed + 31))
        if vib_px > 0:
            pa = math.radians(self.hfov) / width
            yaw += vibration(t, vib_px * pa, seed + 5)
            pitch += vibration(t, vib_px * pa, seed + 7)
        R = rot(u, -yaw) @ rot(r, pitch) @ rot(f, roll)
        c = Cam(**{**self.__dict__})
        c.fwd = R @ f
        c.up = R @ u
        return c

    def focal_mm(self, sensor_w_mm=36.0) -> float:
        return sensor_w_mm / (2 * math.tan(math.radians(self.hfov) / 2))

    def coc_inf_px(self, width=1920, sensor_w_mm=36.0) -> float:
        """Blur-circle diameter (px) of objects at infinity when focused at self.focus."""
        f = self.focal_mm(sensor_w_mm) / 1000.0
        if self.focus >= 1e6:
            return 0.0
        A = f / self.fstop
        return (A / self.focus) / (math.radians(self.hfov) / width) * 1.0

    def to_tracer(self) -> dict:
        return {"pos": [float(x) for x in self.pos_bh], "fwd": [float(x) for x in norm(self.fwd)],
                "up": [float(x) for x in norm(self.up)], "vel": [float(x) for x in self.vel]}

    def to_blender(self) -> dict:
        return {"pos": [float(x) for x in self.pos_ship], "fwd": [float(x) for x in norm(self.fwd)],
                "up": [float(x) for x in norm(self.up)], "hfov": self.hfov, "focus": self.focus,
                "fstop": self.fstop}


def look(pos, target, up=(0, 0, 1)) -> np.ndarray:
    return norm(np.asarray(target, float) - np.asarray(pos, float))


def orbit_pos(dist: float, incl_deg: float, az_deg: float) -> np.ndarray:
    """Position at distance dist, inclination from the +Z spin axis, azimuth from +X."""
    i, a = math.radians(incl_deg), math.radians(az_deg)
    return v3(dist * math.sin(i) * math.cos(a), dist * math.sin(i) * math.sin(a), dist * math.cos(i))

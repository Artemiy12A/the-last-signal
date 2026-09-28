"""Timelike geodesics in Kerr-Schild coordinates (same metric and conventions as the tracer).

Used for the ship's fall in S15: integrate proper time, record (t, x, y, z, u^mu, tau).
"""
from __future__ import annotations

import math

import numpy as np


def ks_r(x, y, z, a):
    b = x * x + y * y + z * z - a * a
    return math.sqrt(0.5 * (b + math.sqrt(b * b + 4 * a * a * z * z)))


def ks_geom(x, y, z, a):
    r = ks_r(x, y, z, a)
    den = r * r + a * a
    f = 2 * r ** 3 / (r ** 4 + a * a * z * z)
    l = np.array([1.0, (r * x + a * y) / den, (r * y - a * x) / den, z / r])
    return r, f, l


def metric(x, y, z, a):
    r, f, l = ks_geom(x, y, z, a)
    eta = np.diag([-1.0, 1, 1, 1])
    return eta + f * np.outer(l, l)


def inv_metric(x, y, z, a):
    r, f, l = ks_geom(x, y, z, a)
    eta = np.diag([-1.0, 1, 1, 1])
    lu = eta @ l
    return eta - f * np.outer(lu, lu)


def _H(xs, p, a):
    return 0.5 * p @ inv_metric(*xs, a) @ p


def rhs(state, a, eps=1e-6):
    """state = [t, x, y, z, p_t, p_x, p_y, p_z]; derivative w.r.t. proper time."""
    xs = state[1:4]
    p = state[4:8]
    gi = inv_metric(*xs, a)
    dx = gi @ p                       # dx^mu/dtau
    dp = np.zeros(4)
    for i in range(3):                # dp_i/dtau = -dH/dx^i (central differences)
        e = np.zeros(3); e[i] = eps
        dp[i + 1] = -(_H(xs + e, p, a) - _H(xs - e, p, a)) / (2 * eps)
    return np.concatenate([dx, dp])


def fall(x0, v0, a, r_stop_factor=1.002, dtau=0.02, max_tau=400.0):
    """Integrate a timelike geodesic from position x0 (3,) with coordinate 3-velocity v0 = dx/dt.
    Returns array rows [t, x, y, z, u^t, u^x, u^y, u^z, tau]."""
    x0 = np.asarray(x0, float)
    g = metric(*x0, a)
    v = np.array([1.0, *v0])
    n = -(v @ g @ v)
    if n <= 0:
        raise ValueError("initial velocity not timelike")
    u = v / math.sqrt(n)
    p = g @ u
    st = np.concatenate([[0.0], x0, p])
    rp = 1 + math.sqrt(1 - a * a)
    rows = []
    tau = 0.0
    while tau < max_tau:
        xs = st[1:4]
        r = ks_r(*xs, a)
        u = inv_metric(*xs, a) @ st[4:8]
        rows.append([st[0], *xs, *u, tau])
        if r < rp * r_stop_factor:
            break
        h = dtau * min(1.0, (r - rp) / 1.0 + 0.02)
        k1 = rhs(st, a)
        k2 = rhs(st + 0.5 * h * k1, a)
        k3 = rhs(st + 0.5 * h * k2, a)
        k4 = rhs(st + h * k3, a)
        st = st + h / 6 * (k1 + 2 * k2 + 2 * k3 + k4)
        tau += h
    return np.array(rows)

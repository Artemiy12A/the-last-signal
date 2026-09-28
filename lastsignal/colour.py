"""Colour science helpers."""
from __future__ import annotations

import numpy as np

# XYZ -> linear sRGB / Rec.709 primaries (D65)
XYZ_TO_RGB = np.array([
    [3.2404542, -1.5371385, -0.4985314],
    [-0.9692660, 1.8760108, 0.0415560],
    [0.0556434, -0.2040259, 1.0572252],
])


def _g(x, mu, s1, s2):
    s = np.where(x < mu, s1, s2)
    return np.exp(-0.5 * ((x - mu) / s) ** 2)


def cie_cmf(lam_nm: np.ndarray):
    """CIE 1931 2-degree colour matching functions, multi-lobe fit
    (Wyman, Sloan & Shirley 2013, JCGT 2(2))."""
    x = (1.056 * _g(lam_nm, 599.8, 37.9, 31.0) + 0.362 * _g(lam_nm, 442.0, 16.0, 26.7)
         - 0.065 * _g(lam_nm, 501.1, 20.4, 26.2))
    y = 0.821 * _g(lam_nm, 568.8, 46.9, 40.5) + 0.286 * _g(lam_nm, 530.9, 16.3, 31.1)
    z = 1.217 * _g(lam_nm, 437.0, 11.8, 36.0) + 0.681 * _g(lam_nm, 459.0, 26.0, 13.8)
    return x, y, z


def blackbody_rgb(T: float) -> np.ndarray:
    """Linear Rec.709 chromaticity of a blackbody, normalised to luminance 1."""
    lam = np.linspace(380.0, 780.0, 401)
    l_m = lam * 1e-9
    h, c, k = 6.62607015e-34, 2.99792458e8, 1.380649e-23
    spd = 1.0 / (l_m ** 5 * (np.exp(h * c / (l_m * k * T)) - 1.0))
    x, y, z = cie_cmf(lam)
    X, Y, Z = (spd * x).sum(), (spd * y).sum(), (spd * z).sum()
    rgb = XYZ_TO_RGB @ np.array([X, Y, Z]) / Y
    return np.clip(rgb, 0.0, None)


def blackbody_lut(n: int = 512, t_min: float = 800.0, t_max: float = 40000.0) -> np.ndarray:
    """LUT indexed by log temperature, matching blackbody() in scene.frag."""
    ts = np.exp(np.linspace(np.log(t_min), np.log(t_max), n))
    return np.stack([blackbody_rgb(t) for t in ts])

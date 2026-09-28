"""ITU-R BS.1770-4 / EBU R128 loudness: K-weighting, momentary, short-term, integrated, LRA."""
from __future__ import annotations

import numpy as np
from scipy import signal as sps

from dsp import SR

# BS.1770 K-weighting coefficients at 48 kHz
_SHELF_B = [1.53512485958697, -2.69169618940638, 1.19839281085285]
_SHELF_A = [1.0, -1.69065929318241, 0.73248077421585]
_HP_B = [1.0, -2.0, 1.0]
_HP_A = [1.0, -1.99004745483398, 0.99007225036621]


def k_weight(x: np.ndarray) -> np.ndarray:
    y = sps.lfilter(_SHELF_B, _SHELF_A, x, axis=0)
    return sps.lfilter(_HP_B, _HP_A, y, axis=0)


def _power_blocks(x: np.ndarray, win: float, hop: float) -> tuple[np.ndarray, np.ndarray]:
    """Mean-square K-weighted power summed over channels for sliding windows. Returns (t_end, p)."""
    y = k_weight(x if x.ndim == 2 else x[:, None])
    p = (y * y).sum(axis=1)
    cs = np.concatenate([[0.0], np.cumsum(p)])
    w = int(round(win * SR))
    h = int(round(hop * SR))
    ends = np.arange(w, len(p) + 1, h)
    pw = (cs[ends] - cs[ends - w]) / w
    return ends / SR, pw


def lufs(p):
    return -0.691 + 10.0 * np.log10(np.maximum(p, 1e-30))


def momentary(x: np.ndarray, hop: float = 0.1):
    """Momentary loudness (400 ms), returns (t_centre, LUFS)."""
    t, p = _power_blocks(x, 0.4, hop)
    return t - 0.2, lufs(p)


def short_term(x: np.ndarray, hop: float = 0.1):
    """Short-term loudness (3 s), returns (t_centre, LUFS)."""
    t, p = _power_blocks(x, 3.0, hop)
    return t - 1.5, lufs(p)


def integrated(x: np.ndarray) -> float:
    _, p = _power_blocks(x, 0.4, 0.1)           # 75 % overlap gating blocks
    l = lufs(p)
    p = p[l > -70.0]
    if len(p) == 0:
        return -np.inf
    rel = lufs(p.mean()) - 10.0
    p2 = p[lufs(p) > rel]
    return float(lufs(p2.mean()))


def lra(x: np.ndarray) -> float:
    """Loudness range (EBU Tech 3342): 10th..95th percentile of gated short-term loudness."""
    _, p = _power_blocks(x, 3.0, 0.1)
    l = lufs(p)
    l = l[l > -70.0]
    if len(l) == 0:
        return 0.0
    rel = lufs((10 ** ((l + 0.691) / 10)).mean()) - 20.0
    l = l[l > rel]
    return float(np.percentile(l, 95) - np.percentile(l, 10))

"""DSP primitives for the soundtrack (numpy/scipy only, 48 kHz, float64).

Conventions: mono signals are 1-D arrays, stereo signals are (n, 2) arrays. Frequencies may be
scalars or per-sample arrays. Every random source is seeded by name (`rng("hull_creak")`) so the
render is deterministic.
"""
from __future__ import annotations

import zlib
from functools import lru_cache

import numpy as np
from scipy import signal as sps
from scipy.ndimage import minimum_filter1d

SR = 48000
TWO_PI = 2.0 * np.pi


# ------------------------------------------------------------------------------------ basics
def n_of(t: float) -> int:
    """Sample index of time t (s)."""
    return int(round(t * SR))


def tt(n: int) -> np.ndarray:
    return np.arange(n) / SR


def rng(name: str) -> np.random.Generator:
    return np.random.default_rng(zlib.crc32(name.encode("utf-8")))


def db(x: float) -> float:
    return 10.0 ** (x / 20.0)


def to_db(x, floor: float = -150.0):
    return np.maximum(20.0 * np.log10(np.maximum(np.abs(x), 1e-30)), floor)


def smoothstep(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


def stereo(x: np.ndarray) -> np.ndarray:
    return x if x.ndim == 2 else np.stack([x, x], axis=1)


def mono(x: np.ndarray) -> np.ndarray:
    return x if x.ndim == 1 else 0.5 * (x[:, 0] + x[:, 1])


def pan_gains(p: float) -> tuple[float, float]:
    """Equal-power pan, p in [-1, 1]; centre = -3 dB per side."""
    a = (np.clip(p, -1.0, 1.0) + 1.0) * np.pi / 4.0
    return float(np.cos(a)), float(np.sin(a))


def pan(x: np.ndarray, p) -> np.ndarray:
    """Pan a mono signal; p may be a scalar or a per-sample array."""
    a = (np.clip(p, -1.0, 1.0) + 1.0) * np.pi / 4.0
    return np.stack([x * np.cos(a), x * np.sin(a)], axis=1)


def place(buf: np.ndarray, sig: np.ndarray, t0: float, gain: float = 1.0, p: float = 0.0) -> None:
    """Mix a mono (panned by p) or stereo signal into a stereo buffer starting at time t0."""
    if sig.ndim == 1:
        gl, gr = pan_gains(p)
        sig = np.stack([sig * gl, sig * gr], axis=1)
    i0 = n_of(t0)
    if i0 < 0:
        sig = sig[-i0:]
        i0 = 0
    i1 = min(i0 + len(sig), len(buf))
    if i1 > i0:
        buf[i0:i1] += sig[: i1 - i0] * gain


def fade(n: int, a: int = 0, r: int = 0) -> np.ndarray:
    """Unit window with raised-cosine fade-in of a samples and fade-out of r samples."""
    w = np.ones(n)
    if a > 0:
        a = min(a, n)
        w[:a] *= 0.5 - 0.5 * np.cos(np.pi * np.arange(a) / a)
    if r > 0:
        r = min(r, n)
        w[n - r:] *= 0.5 + 0.5 * np.cos(np.pi * (np.arange(r) + 1) / r)
    return w


def curve(n: int, points, t0: float = 0.0, kind: str = "lin") -> np.ndarray:
    """Piecewise curve over n samples from [(t, v), ...] (times absolute, t0 = start of buffer).

    kind="lin" interpolates linearly, "db" interpolates the values in dB (values given in dB,
    output linear), "exp" interpolates log-values (for frequencies)."""
    ts = np.array([p[0] for p in points], dtype=float) - t0
    vs = np.array([p[1] for p in points], dtype=float)
    t = tt(n)
    if kind == "db":
        return 10.0 ** (np.interp(t, ts, vs) / 20.0)
    if kind == "exp":
        return np.exp(np.interp(t, ts, np.log(vs)))
    return np.interp(t, ts, vs)


# -------------------------------------------------------------------------------- oscillators
def phase(freq, n: int | None = None, phase0: float = 0.0) -> np.ndarray:
    """Running phase in radians for a (possibly time-varying) frequency."""
    f = np.asarray(freq, dtype=np.float64)
    if f.ndim == 0:
        return TWO_PI * f * tt(n) + phase0
    return TWO_PI * np.cumsum(f) / SR + phase0


def sine(freq, n: int | None = None, phase0: float = 0.0) -> np.ndarray:
    return np.sin(phase(freq, n, phase0))


def saw(freq, n: int | None = None, phase0: float = 0.0) -> np.ndarray:
    """Band-limited sawtooth (polyBLEP), freq scalar or per-sample. phase0 in cycles (0..1)."""
    f = np.asarray(freq, dtype=np.float64)
    if f.ndim == 0:
        f = np.full(n, float(f))
    dt = f / SR
    ph = (np.cumsum(dt) + phase0) % 1.0
    y = 2.0 * ph - 1.0
    m = ph < dt
    x = ph[m] / dt[m]
    y[m] -= x + x - x * x - 1.0
    m = ph > 1.0 - dt
    x = (ph[m] - 1.0) / dt[m]
    y[m] -= x * x + x + x + 1.0
    return y


def white(n: int, r: np.random.Generator) -> np.ndarray:
    return r.standard_normal(n)


def colored(n: int, r: np.random.Generator, slope_db_oct: float = -3.0) -> np.ndarray:
    """Noise with a power slope in dB/octave (-3 pink, -6 brown-ish), unit RMS."""
    m = 1 << int(np.ceil(np.log2(max(n, 2))))
    spec = r.standard_normal(m // 2 + 1) + 1j * r.standard_normal(m // 2 + 1)
    f = np.fft.rfftfreq(m, 1.0 / SR)
    f[0] = f[1]
    spec *= (f / 1000.0) ** (slope_db_oct / 20.0 / np.log10(2.0))
    spec[0] = 0.0
    x = np.fft.irfft(spec, m)[:n]
    return x / (np.sqrt(np.mean(x * x)) + 1e-12)


# ------------------------------------------------------------------------------------ filters
@lru_cache(maxsize=512)
def _butter(kind: str, f, order: int):
    return sps.butter(order, f, btype=kind, fs=SR, output="sos")


def _clampf(f):
    return min(max(float(f), 5.0), SR * 0.49)


def lp(x, f, order: int = 2, zero_phase: bool = False):
    sos = _butter("lowpass", _clampf(f), order)
    return sps.sosfiltfilt(sos, x, axis=0) if zero_phase else sps.sosfilt(sos, x, axis=0)


def hp(x, f, order: int = 2, zero_phase: bool = False):
    sos = _butter("highpass", _clampf(f), order)
    return sps.sosfiltfilt(sos, x, axis=0) if zero_phase else sps.sosfilt(sos, x, axis=0)


def bp(x, lo, hi, order: int = 2, zero_phase: bool = False):
    sos = _butter("bandpass", (_clampf(lo), _clampf(hi)), order)
    return sps.sosfiltfilt(sos, x, axis=0) if zero_phase else sps.sosfilt(sos, x, axis=0)


def rbj(kind: str, f: float, q: float):
    """RBJ biquad coefficients (b, a) normalised."""
    f = _clampf(f)
    w0 = TWO_PI * f / SR
    c, s = np.cos(w0), np.sin(w0)
    al = s / (2.0 * q)
    if kind == "lp":
        b = [(1 - c) / 2, 1 - c, (1 - c) / 2]
    elif kind == "hp":
        b = [(1 + c) / 2, -(1 + c), (1 + c) / 2]
    elif kind == "bp":        # constant 0 dB peak gain
        b = [al, 0.0, -al]
    else:
        raise ValueError(kind)
    a = [1 + al, -2 * c, 1 - al]
    return np.array(b) / a[0], np.array(a) / a[0]


def tv_filter(x: np.ndarray, fc, q: float = 0.707, kind: str = "lp", block: int = 64) -> np.ndarray:
    """Time-varying biquad (block-wise coefficients, carried state). fc: array (len(x)) or scalar."""
    n = len(x)
    fc = np.broadcast_to(np.asarray(fc, dtype=float), (n,))
    y = np.empty_like(x)
    zi = np.zeros((2,) + x.shape[1:])
    for i0 in range(0, n, block):
        i1 = min(n, i0 + block)
        b, a = rbj(kind, fc[(i0 + i1) // 2], q)
        y[i0:i1], zi = sps.lfilter(b, a, x[i0:i1], axis=0, zi=zi)
    return y


def resonators(x: np.ndarray, modes) -> np.ndarray:
    """Parallel constant-peak bandpass resonators [(freq, q, gain), ...]."""
    y = np.zeros_like(x)
    for f, q, g in modes:
        b, a = rbj("bp", f, q)
        y += g * sps.lfilter(b, a, x, axis=0)
    return y


def allpass(x: np.ndarray, d: int, g: float) -> np.ndarray:
    b = np.zeros(d + 1)
    a = np.zeros(d + 1)
    b[0], b[d] = g, 1.0
    a[0], a[d] = 1.0, g
    return sps.lfilter(b, a, x, axis=0)


def decorrelate(x: np.ndarray, seed: str) -> np.ndarray:
    """Mono -> decorrelated mono (Schroeder allpass cascade), same spectrum."""
    r = rng("decorr:" + seed)
    y = x
    for _ in range(4):
        y = allpass(y, int(r.uniform(0.0025, 0.0125) * SR), 0.55)
    return y


def widen(x_mono: np.ndarray, width, seed: str) -> np.ndarray:
    """Mono -> stereo with M/S width (0 = mono, 1 = wide). Sums back to mono exactly."""
    s = decorrelate(x_mono, seed) * width
    return np.stack([x_mono + s, x_mono - s], axis=1) * 0.7071


def ms_width(x: np.ndarray, w) -> np.ndarray:
    """Scale the side signal of a stereo buffer by w (scalar or per-sample)."""
    m = 0.5 * (x[:, 0] + x[:, 1])
    s = 0.5 * (x[:, 0] - x[:, 1]) * w
    return np.stack([m + s, m - s], axis=1)


def delay(x: np.ndarray, d_s: float) -> np.ndarray:
    d = int(round(d_s * SR))
    if d <= 0:
        return x.copy()
    return np.concatenate([np.zeros((d,) + x.shape[1:]), x[:-d]], axis=0)


def vdelay(x: np.ndarray, d_s: np.ndarray) -> np.ndarray:
    """Variable (fractional) delay of a mono signal, d_s per-sample seconds."""
    n = len(x)
    pos = np.arange(n) - d_s * SR
    return np.interp(pos, np.arange(n), x, left=0.0, right=0.0)


# ----------------------------------------------------------------------------- nonlinearities
def sat(x, drive: float = 2.0):
    return np.tanh(drive * x) / np.tanh(drive)


def freq_shift(x: np.ndarray, df) -> np.ndarray:
    """Single-sideband frequency shift (Hz, scalar or per-sample) of a mono signal."""
    n = len(x)
    m = 1 << int(np.ceil(np.log2(max(n, 2))))
    a = sps.hilbert(x, N=m)[:n]
    ph = phase(df, n)
    return np.real(a * np.exp(1j * ph))


def crush(x: np.ndarray, bits: float, hold: int) -> np.ndarray:
    """Bit reduction + sample-and-hold decimation (digital tearing)."""
    q = 2.0 ** (bits - 1)
    y = np.round(x * q) / q
    if hold > 1:
        idx = (np.arange(len(x)) // hold) * hold
        y = y[idx]
    return y


# ------------------------------------------------------------------------------- envelopes
def env_follow(x: np.ndarray, t_smooth: float = 0.02) -> np.ndarray:
    """RMS envelope (zero-phase one-pole-ish smoothing via butter LP on x^2)."""
    p = lp(x * x, 1.0 / (TWO_PI * t_smooth), order=2, zero_phase=True)
    return np.sqrt(np.maximum(p, 0.0))


def ar(n: int, attack: float, hold: float, tau: float) -> np.ndarray:
    """Attack (raised cosine, s) -> hold (s) -> exponential release (time constant tau, s)."""
    t = tt(n)
    e = np.ones(n)
    if attack > 0:
        m = t < attack
        e[m] = 0.5 - 0.5 * np.cos(np.pi * t[m] / attack)
    m = t > attack + hold
    e[m] = np.exp(-(t[m] - attack - hold) / tau)
    return e


# ------------------------------------------------------------------------------------ reverb
def make_ir(rt60_low: float, rt60_high: float, predelay: float = 0.04, n_er: int = 10,
            er_span: float = 0.08, shared: float = 0.1, seed: str = "void",
            length: float | None = None) -> np.ndarray:
    """Synthetic stereo IR (research_sota.md §3.3): octave-band decays, pre-delay, sparse early
    reflections, decorrelated channels with a little shared component, unit energy per channel."""
    r = rng("ir:" + seed)
    centres = [63, 125, 250, 500, 1000, 2000, 4000, 8000]
    rts = np.exp(np.interp(np.log(centres), np.log([63, 8000]), np.log([rt60_low, rt60_high])))
    length = length or 1.05 * rt60_low
    n = n_of(length)
    t = tt(n)
    common = r.standard_normal(n)
    out = np.zeros((n, 2))
    for ch in range(2):
        z = (1 - shared) * r.standard_normal(n) + shared * common
        acc = np.zeros(n)
        for k, (fc, rt) in enumerate(zip(centres, rts)):
            if k == 0:
                band = lp(z, fc * 1.414, order=4, zero_phase=True)
            elif k == len(centres) - 1:
                band = hp(z, fc / 1.414, order=4, zero_phase=True)
            else:
                band = bp(z, fc / 1.414, fc * 1.414, order=3, zero_phase=True)
            acc += band * np.exp(-6.91 * t / rt)
        # early reflections
        for _ in range(n_er):
            te = r.uniform(0.004, er_span)
            i = n_of(te)
            if i < n:
                acc[i] += r.choice([-1.0, 1.0]) * r.uniform(0.3, 1.0) * np.exp(-te / 0.05) * 8.0 / np.sqrt(n_er)
        acc *= fade(n, a=n_of(0.004))
        out[:, ch] = acc
    pd = n_of(predelay)
    out = np.concatenate([np.zeros((pd, 2)), out], axis=0)
    out /= np.sqrt(np.sum(out * out, axis=0, keepdims=True)) + 1e-12
    return out


def convolve(x: np.ndarray, ir: np.ndarray) -> np.ndarray:
    """Stereo (or mono->stereo) convolution, output trimmed to len(x) + len(ir) - 1."""
    x = stereo(x)
    return np.stack([sps.oaconvolve(x[:, c], ir[:, c]) for c in range(2)], axis=1)


def reverb_send(buf: np.ndarray, ir: np.ndarray, wet: float, hp_hz: float = 90.0) -> np.ndarray:
    """Return the wet signal (same length as buf) for a send of `wet` into `ir`, HP'd."""
    w = convolve(buf, ir)[: len(buf)]
    if hp_hz:
        w = hp(w, hp_hz, order=2)
    return w * wet


# ----------------------------------------------------------------------- resampling helpers
def varispeed(x: np.ndarray, pos: np.ndarray) -> np.ndarray:
    """Read signal x (mono or stereo) at fractional sample positions pos (tape-style)."""
    idx = np.arange(len(x))
    if x.ndim == 1:
        return np.interp(pos, idx, x, left=0.0, right=0.0)
    return np.stack([np.interp(pos, idx, x[:, c], left=0.0, right=0.0) for c in range(x.shape[1])], axis=1)


def resample_to(x: np.ndarray, sr_in: int) -> np.ndarray:
    if sr_in == SR:
        return x
    g = np.gcd(sr_in, SR)
    return sps.resample_poly(x, SR // g, sr_in // g, axis=0)


def granular(src: np.ndarray, n_out: int, pos_start: float, pos_end: float, pitch: float,
             grain: float, density: float, seed: str, jitter: float = 0.02) -> np.ndarray:
    """Granular time-stretch/pitch-shift of a mono source.

    Output has n_out samples; the read position moves linearly from pos_start to pos_end
    (seconds in src); each grain is resampled by `pitch` (0.5 = an octave down)."""
    r = rng("gran:" + seed)
    out = np.zeros(n_out)
    gl = n_of(grain)
    win = np.hanning(gl)
    n_grains = int(density * n_out / SR)
    src_idx = np.arange(len(src))
    for k in range(n_grains):
        to = r.uniform(0, n_out - gl) if n_grains > 1 else 0
        u = to / max(n_out - 1, 1)
        ps = (pos_start + (pos_end - pos_start) * u + r.uniform(-jitter, jitter)) * SR
        read = ps + np.arange(gl) * pitch
        if read[0] < 0 or read[-1] >= len(src) - 1:
            continue
        g = np.interp(read, src_idx, src) * win
        i0 = int(to)
        out[i0:i0 + gl] += g
    return out * np.sqrt(1.0 / max(density * grain, 1e-6))


# --------------------------------------------------------------------- dynamics / mastering
def _smooth_attack_release(x: np.ndarray, att: float, rel: float, rate: float) -> np.ndarray:
    """One-pole smoothing with separate attack/release coefficients (control rate)."""
    a_att = np.exp(-1.0 / (att * rate))
    a_rel = np.exp(-1.0 / (rel * rate))
    y = np.empty_like(x)
    s = float(x[0])
    xs = x.tolist()
    for i, v in enumerate(xs):
        a = a_att if v > s else a_rel
        s = a * s + (1.0 - a) * v
        y[i] = s
    return y


def compressor(x: np.ndarray, thresh_db: float, ratio: float, attack: float = 0.03,
               release: float = 0.3, knee_db: float = 6.0, ctrl_rate: int = 1000) -> tuple[np.ndarray, np.ndarray]:
    """Feed-forward RMS bus compressor. Returns (output, gain_db_per_sample)."""
    n = len(x)
    hop = SR // ctrl_rate
    m = x if x.ndim == 1 else np.max(np.abs(x), axis=1)
    nb = (n + hop - 1) // hop
    pad = np.zeros(nb * hop)
    pad[:n] = m * m if x.ndim == 1 else (x * x).mean(axis=1)
    lvl = 10 * np.log10(pad.reshape(nb, hop).mean(axis=1) + 1e-20)
    lvl = _smooth_attack_release(lvl, attack, release, ctrl_rate)
    over = lvl - thresh_db
    gr = np.where(over <= -knee_db / 2, 0.0,
                  np.where(over >= knee_db / 2, over * (1 - 1 / ratio),
                           (1 - 1 / ratio) * (over + knee_db / 2) ** 2 / (2 * knee_db)))
    g_db = -gr
    tc = (np.arange(nb) + 0.5) * hop
    g_s = np.interp(np.arange(n), tc, g_db)
    g = 10 ** (g_s / 20)
    return (x * g[:, None] if x.ndim == 2 else x * g), g_s


def true_peak_env(x: np.ndarray, os: int = 4) -> np.ndarray:
    """Per-sample true-peak magnitude (max over channels and oversampled phases)."""
    x = stereo(x)
    up = sps.resample_poly(x, os, 1, axis=0)
    pk = np.abs(up).max(axis=1)
    n = len(x)
    pk = pk[: n * os].reshape(n, os).max(axis=1)
    return np.maximum(pk, np.abs(x).max(axis=1))


def true_peak_db(x: np.ndarray) -> float:
    return float(to_db(true_peak_env(x).max()))


def limiter(x: np.ndarray, ceiling_db: float = -1.2, lookahead: float = 0.004,
            release: float = 0.15) -> tuple[np.ndarray, np.ndarray]:
    """Look-ahead true-peak brickwall limiter. Returns (output, gain)."""
    n = len(x)
    c = db(ceiling_db)
    pk = true_peak_env(x)
    g_req = np.minimum(1.0, c / np.maximum(pk, 1e-12))
    L = max(2, 2 * (int(lookahead * SR) // 2))      # even: exact forward window [m, m+L]
    # forward-looking min over [m, m+L]
    h = minimum_filter1d(g_req, size=L + 1, origin=-(L // 2), mode="nearest")
    # causal box average over [m-L, m] keeps g <= g_req everywhere
    cs = np.concatenate([[0.0], np.cumsum(h)])
    idx = np.arange(n)
    lo = np.maximum(idx - L, 0)
    gbox = (cs[idx + 1] - cs[lo]) / (idx + 1 - lo)
    gbox = np.minimum(gbox, h)
    # release: gain reduction decays exponentially, never below what gbox requires
    a = np.exp(-1.0 / (release * SR))
    gr = (1.0 - gbox).tolist()
    y = np.empty(n)
    s = 0.0
    for i, v in enumerate(gr):
        s = v if v > s * a else s * a
        y[i] = s
    g = 1.0 - y
    return x * g[:, None], g

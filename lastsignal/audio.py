"""Soundtrack synthesis (48 kHz stereo). Every cue is driven by timeline.py.

Design
  0.0 - 4.0   deep-space bed (sub drone, distant hiss), the signal pings
  4.0 / 8.25  sub thumps under the text cards
  5.3 - 9.3   the signal stretches (redshift), static, a rising tension bed
  9.3 - 9.4   a breath of silence
  9.4         BRAAM: detuned saw stack through an opening filter, sub drop
  9.4 - 16.6  awe pad (C minor), lifting to A-flat major at the scale shot
  16.6 - 17.6 the signal peaks: pings accelerate, everything rises and distorts
  17.6        hard cut to digital silence
  18.1        title impact, and the last signal alone in a long echo
"""
from __future__ import annotations

import wave
from pathlib import Path

import numpy as np
from scipy import signal as sps

from .timeline import CUT_TO_BLACK, DURATION, FINAL_PING, HITS, PINGS, TITLE_IN

SR = 48000
N = int(DURATION * SR)
RNG = np.random.default_rng(1977)  # Voyager launch year; deterministic output


# ------------------------------------------------------------------ primitives
def t_axis(n: int) -> np.ndarray:
    return np.arange(n) / SR


def place(buf: np.ndarray, sig: np.ndarray, t0: float, gain: float = 1.0):
    """Add a mono or stereo signal into a stereo buffer at time t0."""
    i0 = int(round(t0 * SR))
    if sig.ndim == 1:
        sig = np.stack([sig, sig], axis=1)
    if i0 < 0:
        sig = sig[-i0:]
        i0 = 0
    i1 = min(i0 + len(sig), len(buf))
    if i1 > i0:
        buf[i0:i1] += sig[: i1 - i0] * gain


def saw_blep(freq: np.ndarray, phase0: float = 0.0) -> np.ndarray:
    """Band-limited sawtooth (polyBLEP), freq may vary per sample."""
    dt = np.asarray(freq, dtype=np.float64) / SR
    ph = (np.cumsum(dt) + phase0) % 1.0
    y = 2.0 * ph - 1.0
    dt = np.broadcast_to(dt, ph.shape)
    m = ph < dt
    x = ph[m] / dt[m]
    y[m] -= x + x - x * x - 1.0
    m = ph > 1.0 - dt
    x = (ph[m] - 1.0) / dt[m]
    y[m] -= x * x + x + x + 1.0
    return y


def sine(freq, n=None, phase0=0.0) -> np.ndarray:
    freq = np.asarray(freq, dtype=np.float64)
    if freq.ndim == 0:
        return np.sin(2 * np.pi * freq * t_axis(n) + phase0)
    return np.sin(2 * np.pi * np.cumsum(freq) / SR + phase0)


def env_adsr(n: int, a: float, d: float, s: float, r: float, hold: float) -> np.ndarray:
    t = t_axis(n)
    e = np.where(t < a, t / max(a, 1e-6), 1.0)
    dec = np.clip((t - a) / max(d, 1e-6), 0, 1)
    e = np.where(t >= a, 1.0 + (s - 1.0) * dec, e)
    rel = np.clip((t - hold) / max(r, 1e-6), 0, 1)
    return e * (1.0 - rel)


def butter(x: np.ndarray, kind: str, f, order: int = 2) -> np.ndarray:
    sos = sps.butter(order, f, btype=kind, fs=SR, output="sos")
    return sps.sosfilt(sos, x, axis=0)


def sweep_lowpass(x: np.ndarray, cutoff: np.ndarray, block: int = 256) -> np.ndarray:
    """Time-varying 2-pole lowpass (block-wise coefficient updates, state carried)."""
    y = np.empty_like(x)
    zi = np.zeros((1, 2))
    for i in range(0, len(x), block):
        fc = float(np.clip(cutoff[min(i, len(cutoff) - 1)], 20.0, SR * 0.45))
        sos = sps.butter(2, fc, btype="low", fs=SR, output="sos")
        y[i:i + block], zi = sps.sosfilt(sos, x[i:i + block], zi=zi)
    return y


def pink(n: int) -> np.ndarray:
    white = RNG.standard_normal(n)
    f = np.fft.rfftfreq(n, 1 / SR)
    spec = np.fft.rfft(white)
    spec[1:] /= np.sqrt(f[1:])
    spec[0] = 0
    p = np.fft.irfft(spec, n)
    return p / (np.abs(p).max() + 1e-9)


def reverb_ir(seconds: float, rt60: float, predelay: float = 0.02, bright: float = 0.5) -> np.ndarray:
    """Stereo, decorrelated, frequency-damped noise impulse response."""
    n = int(seconds * SR)
    t = t_axis(n)
    out = []
    for _ in range(2):
        nz = RNG.standard_normal(n)
        lo = butter(nz, "low", 1500)
        hi = nz - lo
        tau = rt60 / 6.91
        ir = lo * np.exp(-t / tau) + bright * hi * np.exp(-t / (tau * 0.45))
        ir *= np.clip(t / 0.01, 0, 1)
        pd = int(predelay * SR)
        ir = np.concatenate([np.zeros(pd), ir])[:n]
        out.append(ir)
    ir = np.stack(out, axis=1)
    return ir / np.sqrt((ir ** 2).sum(axis=0, keepdims=True))


def convolve(x: np.ndarray, ir: np.ndarray) -> np.ndarray:
    if x.ndim == 1:
        x = np.stack([x, x], axis=1)
    y = np.stack([sps.fftconvolve(x[:, c], ir[:, c])[: len(x)] for c in range(2)], axis=1)
    return y


def pingpong(x: np.ndarray, delay: float, fb: float, taps: int = 8, damp: float = 3500.0) -> np.ndarray:
    """Stereo ping-pong echo of a mono signal."""
    d = int(delay * SR)
    y = np.zeros((len(x) + d * taps, 2))
    cur = x.copy()
    for k in range(1, taps + 1):
        cur = butter(cur, "low", damp) * fb
        y[k * d:k * d + len(cur), k % 2] += cur
    return y[: len(x) + d * taps]


# ------------------------------------------------------------------ cues
def ping_voice(pitch: float, gain: float) -> np.ndarray:
    """The signal: a pure, slightly metallic beep. Low pitch = stretched echo."""
    stretched = pitch < 0.7
    dur = 1.6 if stretched else 0.5
    n = int(dur * SR)
    t = t_axis(n)
    f0 = 1318.5 * pitch
    if stretched:
        f = f0 * (1.0 - 0.16 * (1 - np.exp(-t / 0.5)))  # sagging, redshifted
        amp = np.exp(-t / 0.45) * np.clip(t / 0.03, 0, 1)
    else:
        f = np.full(n, f0)
        amp = np.exp(-t / 0.075) * np.clip(t / 0.0015, 0, 1)
    mod = 0.35 * np.exp(-t / 0.05) * sine(f * 1.5)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR + mod) * amp
    x += 0.18 * np.sin(2 * np.pi * np.cumsum(f * 2.0) / SR) * amp ** 1.6
    click = RNG.standard_normal(n) * np.exp(-t / 0.002) * 0.15
    x += butter(click, "high", 3000)
    return x * gain


def sub_thump(dur: float = 2.0, f_hi: float = 62.0, f_lo: float = 34.0, decay: float = 0.7) -> np.ndarray:
    n = int(dur * SR)
    t = t_axis(n)
    f = f_lo + (f_hi - f_lo) * np.exp(-t / 0.12)
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / decay) * np.clip(t / 0.004, 0, 1)
    nz = butter(RNG.standard_normal(n), "low", 400) * np.exp(-t / 0.05) * 0.35
    return np.tanh(1.6 * (body + nz)) / np.tanh(1.6)


def braam(dur: float = 6.0) -> np.ndarray:
    """Massive low brass-like hit: detuned saw stack through an opening filter."""
    n = int(dur * SR)
    t = t_axis(n)
    notes = [32.70, 65.41, 98.00, 130.81, 155.56]  # C1 C2 G2 C3 Eb3
    x = np.zeros(n)
    for i, f in enumerate(notes):
        for det in (-0.09, -0.03, 0.03, 0.09):
            fr = f * 2 ** (det / 12.0) * (1.0 - 0.012 * np.exp(-t / 0.3))
            x += saw_blep(np.full(n, 0.0) + fr, RNG.random()) * (0.9 if i < 2 else 0.55)
    cutoff = 90 + 2200 * np.exp(-t / 0.55) * np.clip(t / 0.09, 0, 1) + 260 * np.exp(-t / 2.5)
    y = sweep_lowpass(x * 0.12, cutoff)
    y = np.tanh(2.2 * y)
    amp = np.clip(t / 0.035, 0, 1) * (0.35 + 0.65 * np.exp(-t / 1.1)) * np.clip((dur - t) / 1.2, 0, 1)
    y *= amp
    sub = np.sin(2 * np.pi * np.cumsum(32.7 + 30 * np.exp(-t / 0.2)) / SR) * np.exp(-t / 2.2) * np.clip(t / 0.01, 0, 1)
    impact = butter(RNG.standard_normal(n), "low", 900) * np.exp(-t / 0.18) * 0.4
    return y * 0.9 + sub * 0.75 + impact


def pad(chord: list[float], dur: float, attack: float, release: float, bright: float = 900.0) -> np.ndarray:
    n = int(dur * SR)
    t = t_axis(n)
    L = np.zeros(n)
    R = np.zeros(n)
    for f in chord:
        for k, det in enumerate((-0.12, -0.05, 0.0, 0.05, 0.12)):
            fr = f * 2 ** (det / 12.0) * (1 + 0.0015 * np.sin(2 * np.pi * (0.13 + 0.05 * k) * t))
            v = saw_blep(np.full(n, 0.0) + fr, RNG.random())
            pan = (k - 2) / 2.0 * 0.7
            L += v * (1 - pan) * 0.5
            R += v * (1 + pan) * 0.5
    cut = bright * (0.6 + 0.4 * np.clip(t / (attack * 1.5), 0, 1))
    L = sweep_lowpass(L, cut)
    R = sweep_lowpass(R, cut)
    e = np.clip(t / attack, 0, 1) ** 2 * np.clip((dur - t) / release, 0, 1)
    return np.stack([L * e, R * e], axis=1) / (len(chord) * 5)


def riser(dur: float) -> np.ndarray:
    """Noise sweep + rising Shepard-ish tones, ending abruptly."""
    n = int(dur * SR)
    t = t_axis(n)
    u = t / dur
    nz = RNG.standard_normal(n)
    fc = 200 * (1 + 30 * u ** 2.2)
    y = sweep_lowpass(nz, fc) * (u ** 2.4)
    tones = np.zeros(n)
    for k in range(4):
        f = 110 * 2 ** k * 2 ** (u * 1.0)
        w = np.exp(-((np.log2(f) - np.log2(440)) ** 2) / 2.0)
        tones += np.sin(2 * np.pi * np.cumsum(f) / SR) * w
    tones *= u ** 2.0 * 0.25
    tremolo = 1 + 0.35 * np.sin(2 * np.pi * (3 + 9 * u ** 2) * t)
    return (y * 0.5 + tones) * tremolo


def static_bed(dur: float) -> np.ndarray:
    """Radio static: band-limited hiss with sparse crackle."""
    n = int(dur * SR)
    hiss = butter(RNG.standard_normal(n), "band", (900, 5200)) * 0.25
    crack = (RNG.random(n) < 0.0009) * RNG.standard_normal(n) * 3.0
    crack = butter(crack, "band", (1500, 9000))
    wobble = 0.6 + 0.4 * sine(0.37, n) * sine(0.11, n)
    return (hiss + crack) * wobble


# ------------------------------------------------------------------ the mix
def render_soundtrack(out: Path) -> Path:
    mix = np.zeros((N, 2))
    wet_big = np.zeros((N, 2))   # send to the long "space" reverb
    t = t_axis(N)

    # --- deep-space bed
    drone = (sine(36.7, N) * 0.55 + sine(55.0, N) * 0.35 * (0.6 + 0.4 * sine(0.07, N))
             + sine(73.4, N) * 0.12 * (0.5 + 0.5 * sine(0.19, N, 1.0)))
    hiss = butter(pink(N), "band", (60, 1800)) * 0.25
    bed = drone * 0.25 + hiss * 0.12
    bed_env = np.clip(t / 2.5, 0, 1) * (1.0 + 0.8 * np.clip((t - 5.3) / 4.0, 0, 1))
    bed_env *= np.where(t < 9.3, 1.0, np.where(t < 16.7, 0.55, 0.9))
    mix += np.stack([bed * bed_env, bed * bed_env * 0.97], axis=1)

    # --- static, more intense as the signal distorts
    st = static_bed(DURATION)
    st_env = 0.02 + 0.05 * np.clip((t - 5.3) / 3.0, 0, 1) * (t < 9.33) + 0.12 * ((t > 16.62) & (t < CUT_TO_BLACK))
    st_env *= np.clip(t / 1.0, 0, 1)
    mix += np.stack([st * st_env, np.roll(st, 911) * st_env], axis=1)

    # --- the signal
    dry_pings = np.zeros(N)
    for tp, pitch, g in PINGS:
        v = ping_voice(pitch, g)
        seg = np.zeros(N)
        i0 = int(tp * SR)
        seg[i0:i0 + len(v)] = v[: max(0, min(len(v), N - i0))]
        dry_pings += seg
    peak_zone = (t > 16.6) & (t < CUT_TO_BLACK)
    dry_pings *= np.where(peak_zone, 1.0 + 1.5 * np.clip((t - 16.6) / 1.0, 0, 1), 1.0)
    dry_pings = np.where(peak_zone, np.tanh(dry_pings * 2.5) / 1.8, dry_pings)
    echoes = pingpong(dry_pings, 0.29, 0.5, taps=7)[:N]
    mix += np.stack([dry_pings, dry_pings], axis=1) * 0.5 + echoes * 0.32
    wet_big += np.stack([dry_pings, dry_pings], axis=1) * 0.5

    # --- text card thumps
    for key in ("card1", "card2"):
        th = sub_thump(2.2)
        place(mix, th, HITS[key], 0.3)
        place(wet_big, th, HITS[key], 0.12)

    # --- tension riser into the reveal, then a breath of silence
    r_start, r_end = 5.3, 9.33
    rs = riser(r_end - r_start)
    place(mix, np.stack([rs, np.roll(rs, 331)], axis=1), r_start, 0.32)
    place(wet_big, rs, r_start, 0.15)

    # --- BRAAM
    b = braam(6.5)
    # the breath: everything drops away for a beat before the hit
    br0, br1 = int((HITS["reveal"] - 0.12) * SR), int(HITS["reveal"] * SR)
    duck = np.ones(N)
    duck[br0:br1] = np.linspace(1.0, 0.03, br1 - br0)
    mix *= duck[:, None]
    wet_big *= duck[:, None]
    place(mix, np.stack([b, np.roll(b, 240)], axis=1), HITS["reveal"], 0.8)
    place(wet_big, b, HITS["reveal"], 0.28)

    # --- awe pad: C minor, lifting to A-flat major at the scale shot
    p1 = pad([130.81, 155.56, 196.00, 233.08, 311.13], 5.6, 1.6, 1.2, bright=1100)
    place(mix, p1, 9.45, 0.55)
    place(wet_big, p1, 9.45, 0.35)
    p2 = pad([103.83, 130.81, 155.56, 207.65, 261.63, 392.0], 3.6, 0.5, 0.25, bright=1600)
    place(mix, p2, HITS["scale"] - 0.05, 0.85)
    place(wet_big, p2, HITS["scale"] - 0.05, 0.4)
    swell = braam(3.0) * 0.5
    place(mix, np.stack([swell, np.roll(swell, 200)], axis=1), HITS["scale"], 0.6)
    # high shimmer on the lift
    n_sh = int(2.6 * SR)
    ts = t_axis(n_sh)
    sh = sum(sine(f, n_sh) for f in (1567.98, 2093.0, 2637.0)) * np.clip(ts / 0.8, 0, 1) * np.exp(-ts / 1.6) * 0.05
    place(mix, sh, HITS["scale"] + 0.1)
    place(wet_big, sh, HITS["scale"] + 0.1, 0.6)

    # --- the peak: rising tone + noise wall, hard stop at the cut
    pk0 = 16.62
    npk = int((CUT_TO_BLACK - pk0) * SR)
    tp = t_axis(npk)
    u = tp / tp[-1]
    tone = np.sin(2 * np.pi * np.cumsum(500 * 2 ** (u * 2.6)) / SR) * u ** 1.5 * 0.35
    wall = sweep_lowpass(RNG.standard_normal(npk), 300 + 9000 * u ** 2) * u ** 2 * 0.5
    low = saw_blep(np.full(npk, 55.0) * (1 + 0.5 * u)) * 0.3 * u
    pkm = np.tanh(2.0 * (tone + wall + low))
    place(mix, np.stack([pkm, np.roll(pkm, 157)], axis=1), pk0, 0.5)

    # --- reverb
    ir = reverb_ir(5.0, 4.2)
    mix += convolve(wet_big.mean(axis=1), ir) * 0.55 * duck[:, None]

    # --- HARD CUT: true digital silence
    cut0 = int(CUT_TO_BLACK * SR)
    mix[cut0:] = 0.0

    # --- title: impact + the last signal alone
    title = np.zeros((N, 2))
    th = sub_thump(3.0, f_hi=70, f_lo=30, decay=1.2)
    place(title, th, TITLE_IN, 0.32)
    ring = pad([65.41, 98.0, 130.81, 196.0], 1.95, 0.08, 0.6, bright=700)
    place(title, ring, TITLE_IN, 0.16)
    last = ping_voice(1.0, 0.9)
    lp = np.zeros(N)
    i0 = int(FINAL_PING * SR)
    lp[i0:i0 + len(last)] = last[: N - i0]
    title += np.stack([lp, lp], axis=1) * 0.35
    title += pingpong(lp, 0.37, 0.6, taps=6)[:N] * 0.25
    title_wet = convolve(title.mean(axis=1), reverb_ir(5.0, 5.5, bright=0.4)) * 0.4
    title += title_wet
    fade = np.clip((DURATION - t) / 0.5, 0, 1)
    title *= fade[:, None]
    title[:int(TITLE_IN * SR)] = 0.0
    mix += title

    # --- master: DC/sub cleanup, glue, peak limiting
    mix = butter(mix, "high", 22, order=2)
    mix[cut0:int(TITLE_IN * SR)] = 0.0
    mix = np.tanh(mix * 1.15) / np.tanh(1.15)
    peak = np.abs(mix).max()
    mix *= 10 ** (-1.0 / 20) / max(peak, 1e-9)

    out.parent.mkdir(parents=True, exist_ok=True)
    pcm = (np.clip(mix, -1, 1) * 32767).astype("<i2")
    with wave.open(str(out), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    return out

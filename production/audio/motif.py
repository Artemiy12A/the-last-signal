"""THE SIGNAL and OUR BEACON: one parametric voice, two distances.

The motif (3 short + 1 long) comes from the EDL. Every pulse is rendered by `voice(long, stretch,
redshift)`: all *times* in the voice scale by `stretch` and all *frequencies* by `redshift`. So:

  * our ship's beacon  = voice(s=1,   g=1)      a crisp 660.7 Hz FM tick, dry, close, mono-ish
  * the distant signal = voice(s=4.5, g=1/4.5)  the same tick slowed x4.5 and lowered to D3
    (146.8 Hz), carried by a radio channel and a vast convolution tail
  * the falling beacon (t > 72.5 s): the EDL's own stretch/redshift per flash (1.16, 3.1, 4.2, 6.5)
    move the tick continuously into the signal: the ship becomes the signal.

Timbre: 2-operator FM with a tritone (sqrt 2) modulator ratio -> an inharmonic bell whose strongest
partials sit at 0.414 f, f and 2.414 f (a minor tenth either side of the root: the "distinctive
interval"). The morph weight w(s) (0 at s = 1, 1 from s = 4.5) blends in the deep partials
(0.414 f and a D1 sub two octaves under the root), the radio channel, stereo width and the tail.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

import dsp
from dsp import SR, n_of, tt

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tls import edl  # noqa: E402

SIGNAL_ROOT = 146.832                          # D3: the received signal's root
F_BEACON = SIGNAL_ROOT * edl.SIGNAL_STRETCH    # 660.7 Hz: the beacon's own root
FM_RATIO = np.sqrt(2.0)                        # tritone modulator: inharmonic, "wrong"
FM_INDEX = 1.8


def morph_weight(s: float) -> float:
    """0 for the ship's own clock, 1 once the pulse is as stretched as the received signal."""
    return float(dsp.smoothstep((s - 1.0) / (edl.SIGNAL_STRETCH - 1.0)))


def voice(long: bool, s: float, g: float, seed: str, detune_cents: float = 0.0):
    """One motif pulse. Returns (mono signal, amplitude envelope). Times x s, frequencies x g."""
    w = morph_weight(s)
    f0 = F_BEACON * g * 2 ** (detune_cents / 1200.0)
    body = (edl.FLASH_LONG if long else edl.FLASH_SHORT) * s
    att = 0.0015 * s ** 1.5
    tau = (0.06 if long else 0.03) * s
    n = n_of(att + body + 7.0 * tau)
    t = tt(n)
    span = att + body + 2.0 * tau
    # pitch: a quick downward chirp into the note, then a sag (a whole semitone on the long pulse)
    chirp = 1.0 + 0.22 * np.exp(-t / (0.004 * s))
    sag_st = 1.0 if long else 0.3
    sag = 2.0 ** (-sag_st / 12.0 * dsp.smoothstep(t / span))
    ph = dsp.phase(f0 * chirp * sag)
    idx = FM_INDEX * (0.3 + 0.7 * np.exp(-t / (0.03 * s)))
    tone = np.sin(ph + idx * np.sin(FM_RATIO * ph))
    deep = np.sin((FM_RATIO - 1.0) * ph)             # reinforces the 0.414 f lower sideband
    sub = np.sin(0.25 * ph)                          # two octaves under the root (D1 for the signal)
    env = dsp.ar(n, att, body, tau)
    env_sub = dsp.ar(n, att * 4.0 + 0.01 * w, body, tau * 2.0)
    x = env * (tone + 0.4 * w * deep) + 0.24 * w * env_sub * sub
    # the click: a tiny HP noise burst (stretched and lowered with everything else)
    r = dsp.rng("click:" + seed)
    click = dsp.hp(r.standard_normal(n) * np.exp(-t / (0.0006 * s)), 2500.0 * g, order=2)
    x = x + 0.55 * click
    # the ship's own tick is a little driven (electronic edge); the far signal is clean
    x = (1.0 - w) * dsp.sat(x, 1.8) + w * x
    return x, env


def radio(x: np.ndarray, env: np.ndarray, seed: str, rough: float = 1.0) -> np.ndarray:
    """A radio channel for one pulse: band-limit, SSB mistuning (heterodyne), drive, AM crackle,
    dropouts, a carrier whistle and the squelch hiss opening under the pulse."""
    r = dsp.rng("radio:" + seed)
    n = len(x)
    t = tt(n)
    y = dsp.bp(x, 190.0, 3300.0, order=3)
    # SSB mistuning: the whole spectrum shifted a few Hz, drifting -> beats against the clean tone
    df0 = r.uniform(4.0, 11.0) * r.choice([-1.0, 1.0])
    y = dsp.freq_shift(y, df0 * (1.0 + 0.35 * np.sin(dsp.TWO_PI * r.uniform(0.3, 0.9) * t)))
    y = dsp.sat(1.6 * y, 2.0)
    # AM flutter (8-40 Hz) and crackle
    flutter = dsp.bp(r.standard_normal(n), 8.0, 40.0, order=2)
    flutter /= np.abs(flutter).max() + 1e-9
    y *= 1.0 - 0.28 * rough * (0.5 + 0.5 * flutter)
    env_s = dsp.lp(env, 12.0, order=1)
    # dropouts: 12-45 ms gaps, ~2.5 per second of pulse
    dur = n / SR
    gate = np.ones(n)
    for _ in range(r.poisson(2.5 * dur * rough)):
        c = r.uniform(0, n)
        half = r.uniform(0.006, 0.022) * SR
        m = np.abs(np.arange(n) - c) < half
        gate[m] = 1.0 - 0.85 * r.uniform(0.6, 1.0)
    gate = dsp.lp(gate, 250.0, order=1, zero_phase=True)
    y *= gate
    # crackle impulses riding the envelope
    cr = np.zeros(n)
    k = r.poisson(14.0 * dur * rough)
    pos = r.integers(0, n, k)
    cr[pos] = r.pareto(2.5, k) * r.choice([-1.0, 1.0], k) * 0.18
    cr = dsp.bp(cr, 900.0, 5200.0, order=2) * (0.25 + env_s)
    # carrier whistle (heterodyne of an off-channel carrier), slowly drifting
    fw = r.uniform(1350.0, 2250.0) * (1.0 + 0.025 * np.sin(dsp.TWO_PI * r.uniform(0.2, 0.6) * t))
    whistle = 0.05 * np.sin(dsp.phase(fw)) * dsp.lp(env, 4.0, order=1)
    # squelch hiss: the receiver noise floor lifts while a carrier is present
    hiss = dsp.bp(r.standard_normal(n), 320.0, 3000.0, order=2) * 0.07 * dsp.lp(env, 6.0, order=1)
    return (y + cr + whistle + hiss) * gate ** 0.5


def signal_pulse(p, seed: str, rough: float = 1.0):
    """Received-signal pulse (distant): returns (clean_mono, radio_mono, w)."""
    r = dsp.rng("sigdet:" + seed)
    x, env = voice(p.long, p.stretch, p.redshift, seed, detune_cents=r.uniform(-4, 4))
    w = morph_weight(p.stretch)
    return x, radio(x, env, seed, rough), w

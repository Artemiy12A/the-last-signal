"""Sound elements. Each EDL cue kind has a handler `cue_<kind>(mix, cue)`; the continuous layers
(signal pulses, beacon flashes, radio interference) are driven directly from the EDL functions.

Levels are in dBFS before mastering (the master normalises to -14 LUFS afterwards). The tonal
centre is D: signal root D3, beacon root 4.5 x D3, braam / sub / title on D1-D2.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

import dsp
import motif
from dsp import SR, db, n_of, tt
from motif import edl

D1, A1, D2, A2, D3, E3, F3, A3 = 36.708, 55.0, 73.416, 110.0, 146.832, 164.814, 174.614, 220.0

# ------------------------------------------------------------------------ per-shot mix tables
# beacon: (gain, pan, nearness 0..1)  -- nearness = brighter, drier; far = darker, more tail
BEACON_SHOT = {
    "BLK0": (0.0, 0.0, 0.0), "S01": (0.28, None, 0.1), "S02": (0.7, 0.25, 1.0),
    "S03": (0.55, -0.2, 0.7), "S04": (0.45, 0.0, 0.5), "S05": (0.3, -0.55, 0.2),
    "S06": (0.6, 0.1, 0.8), "S07": (0.0, 0.0, 0.0), "S08": (0.35, 0.0, 0.6),
    "S09": (0.55, 0.0, 0.7), "S10": (0.12, 0.0, 0.3), "S11": (0.3, 0.0, 0.1),
    "S12": (0.35, 0.1, 0.5), "S13": (0.45, 0.0, 0.6), "S14": (1.0, 0.0, 1.0),
    "S15": (1.0, 0.0, 0.3),
}
# how hard the signal couples into the ship's electronics (scales edl.interference for sound)
SHIP_COUPLING = {
    "BLK0": 0.45, "S01": 0.4, "S02": 0.45, "S03": 1.0, "S04": 0.6, "S05": 0.65, "S06": 0.6,
    "S07": 0.6, "S08": 0.3, "S09": 0.2, "S10": 0.5, "S11": 0.55, "S12": 0.6, "S13": 1.0,
    "S14": 0.3, "S15": 0.2,
}
def S(shot_id: str, default: float) -> float:
    """Start time of a shot from the EDL (so every level curve follows a re-timed edit)."""
    sh = edl.SHOT_BY_ID.get(shot_id)
    return sh.start if sh else default


def cue_time(kind: str, default: float) -> float:
    return next((c.t for c in edl.CUES if c.kind == kind), default)


T_SLOW = cue_time("time_stretch", 72.5)      # where the world starts slowing

SIGNAL_DB = -17.0          # received signal, pulse gain 1 (before the act offset below)
# act offset for the signal (dB): quiet and sparse in Act I, full from the reveal on
SIGNAL_ACT = [(0.0, -10.5), (S("S01", 3.0), -10.0), (S("S02", 10.0), -12.0), (S("S04", 21.5), -12.0), (S("S05", 28.0), -10.0),
              (S("S06", 33.5), -8.0), (S("S08", 41.0), -6.0), (S("S10", 48.5), -3.0), (edl.DURATION, -3.0)]
BEACON_DB = -34.0          # the ship's tick at nearness 1
RING_ECHO_DELAY = 3.0      # s after the last beacon flash (cinema: physical ~16 M is ~6.6 s)
WARP_BETA = 0.45           # sound time-dilation = (dtau/dt)^beta (cinema: physical beta = 1)


def signal_act(t: float) -> float:
    return float(np.interp(t, [a for a, _ in SIGNAL_ACT], [b for _, b in SIGNAL_ACT]))


LIGHTCURVE = Path(__file__).resolve().parents[1] / "shots" / "S15" / "lightcurve.json"


def flashes_from_lightcurve(path: Path, t0: float, t1: float) -> list:
    """Beacon flashes measured from the tracer's S15 light curve: JSON [[film_time, intensity,
    redshift], ...]. Each prominent peak (in log intensity) becomes a flash: onset at the half-rise
    point, stretch = 1/redshift, long/short from the flash's proper-time width, gain from the
    peak intensity (compressed, ^0.3, relative to the first S15 flash)."""
    from scipy.signal import find_peaks, peak_widths
    data = np.array(json.loads(path.read_text()), dtype=float)
    data = data[np.argsort(data[:, 0])]
    m = (data[:, 0] >= t0 - 0.5) & (data[:, 0] < t1)
    t, inten, red = data[m, 0], np.maximum(data[m, 1], 0.0), np.clip(data[m, 2], 1e-3, 1.0)
    if len(t) < 5 or inten.max() <= 0:
        return []
    li = np.log10(inten + inten.max() * 1e-5)
    pk, _ = find_peaks(li, prominence=0.3)
    if len(pk) == 0:
        return []
    wid, _, left, _ = peak_widths(inten, pk, rel_height=0.5)
    dt = np.median(np.diff(t))
    ref = inten[pk[0]]
    out = []
    for p_, w_, l_ in zip(pk, wid, left):
        t_on = float(np.interp(l_, np.arange(len(t)), t))
        if not (t0 <= t_on < t1):
            continue
        g = float(np.interp(t_on, t, red))
        s = max(1.0, 1.0 / g)
        long_ = (w_ * dt * g) > 0.5 * (edl.FLASH_SHORT + edl.FLASH_LONG)
        gain = float(np.clip((inten[p_] / ref) ** 0.3, 0.08, 1.0))
        out.append(edl.Pulse(t_on, bool(long_), s, gain, g, "beacon"))
    return out


def beacon_flashes() -> tuple[list, bool]:
    """edl.beacon_flashes(), with S15's flashes replaced by the measured light curve if present."""
    fl = edl.beacon_flashes()
    s15 = edl.SHOT_BY_ID.get("S15")
    if s15 is None or not LIGHTCURVE.exists():
        return fl, False
    meas = flashes_from_lightcurve(LIGHTCURVE, s15.start, s15.end)
    if not meas:
        return fl, False
    keep = [f for f in fl if not (s15.start <= f.t < s15.end)]
    return sorted(keep + meas, key=lambda p: p.t), True


def shot_value(table, t, default):
    return table.get(edl.shot_at(t).id, default)


def ctrl_curve(fn, t0: float, t1: float, rate: int = 1000) -> tuple[np.ndarray, np.ndarray]:
    ts = np.arange(t0, t1, 1.0 / rate)
    return ts, np.array([fn(t) for t in ts])


def to_samples(ts, vs, t0: float, n: int) -> np.ndarray:
    return np.interp(t0 + tt(n), ts, vs)


def abs_sine(f: float, t0: float, n: int, phase0: float = 0.0) -> np.ndarray:
    """Sine phase-locked to absolute film time (so overlapping layers on one pitch never cancel)."""
    return np.sin(dsp.TWO_PI * f * (t0 + tt(n)) + phase0)


def saw_stack(f, n: int, voices: int, spread_cents, seed: str) -> np.ndarray:
    """Detuned band-limited saw stack; f and spread may be per-sample arrays."""
    r = dsp.rng("stack:" + seed)
    offs = np.linspace(-1.0, 1.0, voices) + r.uniform(-0.15, 0.15, voices)
    y = np.zeros(n)
    for o in offs:
        y += dsp.saw(np.asarray(f) * 2 ** (o * np.asarray(spread_cents) / 1200.0), n, r.uniform())
    return y / np.sqrt(voices)


# ============================================================================ continuous layers
def room_tone(mix, t_in: float, dur: float) -> None:
    """Near-inaudible air and receiver hiss under everything until the hard cut; D1 sub rising in the black."""
    t_end = mix.silence[0]
    n = n_of(t_end)
    r = dsp.rng("room")
    hiss = dsp.bp(dsp.colored(n, r, -3.0), 150.0, 5000.0, order=2)
    wob = 1.0 + 0.2 * np.sin(dsp.TWO_PI * 0.07 * tt(n))
    env = dsp.smoothstep((tt(n) - t_in) / dur) * wob
    x = hiss * env * db(-62)
    mix.add("drones", dsp.widen(x, 0.9, "room"), 0.0)
    # BLK0: the sub rises out of nothing (hands over to drone_deep on the same phase)
    m = n_of(t_in + dur + 0.6)
    e = dsp.curve(m, [(0.0, -80), (t_in + dur, -47), (t_in + dur + 0.6, -47)], kind="db")
    e *= dsp.fade(m, 0, n_of(0.6))
    sub = (abs_sine(D1, 0.0, m) + 0.18 * abs_sine(2 * D1, 0.0, m)) * e
    mix.add("drones", sub, 0.0)


def signal_layer(mix) -> None:
    """The received signal: every edl.signal_pulses() pulse, radio-carried, wide, long tail."""
    for i, p in enumerate(edl.signal_pulses()):
        rough = 0.6 + 0.6 * shot_value(SHIP_COUPLING, p.t, 0.5)
        clean, rad, w = motif.signal_pulse(p, f"sig{i}", rough)
        g = db(SIGNAL_DB + signal_act(p.t)) * p.gain
        clean_st = dsp.widen(clean, 0.65 * w, f"sig{i}")
        r = dsp.rng(f"sigpan{i}")
        y = clean_st * (1.0 - 0.35 * w) + dsp.pan(rad, r.uniform(-0.15, 0.15)) * 0.9 * w
        mix.add("signal", y, p.t, g, sends={"void": 0.6})
        mix.event(p.t, "signal_pulse", long=p.long, gain=round(p.gain, 3))


def beacon_layer(mix) -> None:
    """Our ship's strobe tick: every edl.beacon_flashes() flash. After 72.5 s each flash carries the
    EDL's stretch/redshift, so the tick itself slows and sinks into the signal's voice."""
    flashes, measured = beacon_flashes()
    if measured:
        mix.event(edl.SHOT_BY_ID["S15"].start, "s15_lightcurve", path=str(LIGHTCURVE))
    for i, f in enumerate(flashes):
        shot = edl.shot_at(f.t)
        gain, p, near = BEACON_SHOT.get(shot.id, (0.3, 0.0, 0.5))
        w = motif.morph_weight(f.stretch)
        if gain <= 0 and w <= 0:
            continue
        if p is None:                       # S01: the ship crosses the frame
            p = -0.65 + 1.3 * shot.local(f.t)
        seed = f"bcn{i}"
        x, env = motif.voice(f.long, f.stretch, f.redshift, seed)
        if near < 1.0:
            x = dsp.lp(x, 2200.0 + 14000.0 * near ** 2, order=2)
        if w > 0:
            x = x * (1.0 - 0.35 * w) + motif.radio(x, env, seed, 0.5 + 0.5 * w) * 0.9 * w
        y = dsp.widen(x, 0.08 + 0.6 * w, seed)
        y = y * np.array(dsp.pan_gains(p * (1 - w))) * 1.4142
        # level: the ship's small tick grows into the signal's size as it stretches
        lvl_db = (1 - w) * (BEACON_DB + 20 * np.log10(max(gain, 1e-3)) - 6.0 * (1 - near)) \
            + w * (SIGNAL_DB + signal_act(f.t) + 1.0) + 20 * np.log10(max(f.gain, 1e-3))
        mix.add("beacon", y, f.t, db(lvl_db),
                sends={"hull": 0.22 * (1 - w) * near, "void": 0.05 + 0.25 * (1 - near) * (1 - w) + 0.6 * w})
        mix.event(f.t, "beacon_flash", long=f.long, stretch=round(f.stretch, 3), redshift=round(f.redshift, 3),
                  level_db=round(lvl_db, 1))
    mix.flashes = flashes


def interference_layer(mix) -> None:
    """Receiver hiss, static, crackle, heterodyne sweeps, electrical stutter, Cassini chirps,
    all driven by edl.interference(t) x ship coupling; width follows the interference."""
    t_end = mix.silence[0]
    n = n_of(t_end)
    ts, iv = ctrl_curve(edl.interference, 0.0, t_end)
    kv = np.array([shot_value(SHIP_COUPLING, t, 0.5) for t in ts])
    kv = dsp.lp(kv, 20.0, order=1, zero_phase=True)
    jv = np.clip(iv * kv, 0.0, 1.0)
    mix.jv = (ts, jv)
    J = to_samples(ts, jv, 0.0, n)
    t = tt(n)
    r = dsp.rng("interf")
    fade_in = dsp.smoothstep(t / 3.0)
    # 1. receiver hiss (always there, very low) + lift with interference
    hiss = dsp.bp(dsp.colored(n, r, -2.0), 800.0, 7000.0, order=2)
    a_hiss = (db(-67) + db(-40) * J ** 1.5) * fade_in
    # 2. static bed: spiky random AM on band noise
    spk = dsp.bp(r.standard_normal(n), 20.0, 220.0, order=2)
    spk = np.abs(spk / (np.abs(spk).max() + 1e-9)) ** 3
    spk /= np.sqrt(np.mean(spk ** 2)) + 1e-9
    static = dsp.bp(r.standard_normal(n), 500.0, 6000.0, order=2) * spk
    a_static = db(-40) * J ** 1.4
    bed = hiss * a_hiss + static * a_static
    autopan = 0.55 * np.sin(dsp.TWO_PI * 0.09 * t)
    y = dsp.pan(bed, autopan) * 1.4142
    y = y + dsp.widen(bed * 0.5, 1.0, "bed")
    # 3. crackle impulses: rate follows J^2
    lam_max = 170.0
    k = r.poisson(lam_max * t_end)
    pos = np.sort(r.uniform(0, n - 1, k)).astype(int)
    keep = r.uniform(0, 1, k) < (1.5 + 160.0 * J[pos] ** 2) / lam_max
    pos = pos[keep]
    amp = r.pareto(2.2, len(pos)) * r.choice([-1.0, 1.0], len(pos)) * db(-30) * (0.25 + J[pos])
    pans = r.uniform(-1, 1, len(pos))
    cl = np.zeros((n, 2))
    gl = np.cos((pans + 1) * np.pi / 4)
    gr = np.sin((pans + 1) * np.pi / 4)
    cl[pos, 0] += amp * gl
    cl[pos, 1] += amp * gr
    cl = dsp.hp(cl, 1200.0, order=2) + 0.4 * dsp.bp(cl, 180.0, 900.0, order=2)
    y = y + cl
    mix.add("interference", y * fade_in[:, None], 0.0, sends={"void": 0.12})
    # 4. heterodyne sweeps at pulses that hit hard
    sig = [p for p in edl.signal_pulses() if p.t < t_end]
    for i, p in enumerate(sig):
        jp = float(np.interp(p.t + 0.05, ts, jv))
        if jp < 0.28:
            continue
        rr = dsp.rng(f"het{i}")
        for kk in range(1 + int(jp > 0.6)):
            d = rr.uniform(0.6, 1.4) * (1.6 if p.long else 1.0)
            m = n_of(d)
            up = rr.uniform() < 0.35
            f1, f2 = rr.uniform(2300, 3400), rr.uniform(550, 1100)
            if up:
                f1, f2 = f2, f1
            f = dsp.curve(m, [(0, f1), (d, f2)], kind="exp")
            s = np.sin(dsp.phase(f)) + 0.25 * np.sin(2 * dsp.phase(f))
            s *= np.sin(np.pi * np.clip(tt(m) / d, 0, 1)) ** 2
            s = dsp.sat(s, 1.5) * db(-33) * jp
            direction = rr.choice([-1.0, 1.0])
            pn = direction * np.linspace(-0.85, 0.85, m)
            st = dsp.pan(s, pn)
            # Haas: the far side trails by up to 9 ms as it moves
            hd = 0.009 * np.abs(pn)
            far = np.where(pn > 0, 0, 1)
            st[:, 0] = np.where(far == 0, dsp.vdelay(st[:, 0], hd), st[:, 0])
            st[:, 1] = np.where(far == 1, dsp.vdelay(st[:, 1], hd), st[:, 1])
            mix.add("interference", st, p.t + rr.uniform(0.0, 0.25) + 0.3 * kk, sends={"void": 0.35})
    # 5. electrical stutter (the ship's lights stutter in sync) where coupling is strong
    buzz_env = np.clip((J - 0.22) / 0.5, 0, 1) * (to_samples(ts, kv, 0.0, n) > 0.9)
    if buzz_env.max() > 0:
        i0 = int(np.argmax(buzz_env > 0))
        i1 = n - int(np.argmax(buzz_env[::-1] > 0))
        m = i1 - i0
        rs = dsp.rng("stutter")
        buzz = dsp.saw(96.0 + 1.5 * np.sin(dsp.TWO_PI * 0.7 * tt(m)), m) + 0.5 * dsp.saw(192.3, m)
        buzz = dsp.sat(dsp.bp(buzz, 140.0, 3200.0, order=2) * 2.0, 2.0)
        rate = rs.uniform(9, 17)
        gate = (np.sin(dsp.TWO_PI * rate * tt(m) + 3 * np.sin(dsp.TWO_PI * 1.3 * tt(m))) > 0.2).astype(float)
        gate = dsp.lp(gate, 400.0, order=1)
        buzz *= gate * buzz_env[i0:i1] * db(-35)
        mix.add("interference", dsp.widen(buzz, 0.3, "buzz"), i0 / SR, p=0.0, sends={"hull": 0.3})
    # 6. Cassini SKR chirps, only where the signal is coupling (S03 and friends)
    skr = mix.recording("cassini_skr")
    if skr is not None:
        src = skr
        a = np.clip(J - 0.15, 0, 1) ** 1.2 * (to_samples(ts, kv, 0.0, n) > 0.55)
        if a.max() > 0:
            idx = np.arange(n) % (len(src) - 1)
            ch = dsp.bp(src[(idx + n_of(11.0)) % len(src)], 250.0, 2600.0, order=2)
            ch = ch / (np.sqrt(np.mean(ch ** 2)) + 1e-9)
            mix.add("interference", dsp.widen(ch * a * db(-38), 0.8, "skr"), 0.0, sends={"void": 0.25})


# ============================================================================ hits and swells
def hit_layers(level: float, body_f: float = D2, sub_f: float = 46.0, tail: float = 1.6, seed: str = "hit"):
    """transient + body + sub + tail (research_sota.md §3.2). Returns (mono transient/body, mono sub, mono tail)."""
    r = dsp.rng(seed)
    n = n_of(tail * 3.0 + 0.5)
    t = tt(n)
    tr = dsp.hp(r.standard_normal(n) * np.exp(-t / 0.0025), 2500.0, order=2) * 0.45
    tr += np.sin(dsp.TWO_PI * 1800.0 * t) * np.exp(-t / 0.0012) * 0.5      # the click, 1-2 ms
    f = body_f * (1.0 + np.exp(-t / 0.015))
    body_env = (1 - np.exp(-t / 0.002)) * np.exp(-t / 0.2)
    body = np.sin(dsp.phase(f)) * body_env
    mid = dsp.bp(dsp.sat(body * 3.0, 3.0), 200.0, 800.0, order=2) * np.exp(-t / 0.12) * 0.55
    sub = np.sin(dsp.phase(sub_f * (1 + 0.15 * np.exp(-t / 0.05)))) * (1 - np.exp(-t / 0.008)) * np.exp(-t / 0.9)
    rumble = dsp.lp(dsp.colored(n, r, -6.0), 160.0, order=2) * np.exp(-t / tail) * 0.18
    rumble *= 1 - np.exp(-t / 0.03)
    return (tr * 0.5 + body + mid) * level, sub * level, rumble * level


def cue_low_hit(mix, cue) -> None:
    lvl = cue.params.get("level", 0.7)
    a, sub, rumble = hit_layers(1.0, seed=f"hit{cue.t}")
    g = db(-7.0) * lvl
    mix.add("fx", dsp.widen(a, 0.35, f"hit{cue.t}"), cue.t, g, sends={"hall": 0.45})
    mix.add("fx", sub, cue.t, g * 0.85)
    mix.add("fx", dsp.widen(rumble, 1.0, f"rum{cue.t}"), cue.t, g, sends={"hall": 0.3})
    mix.duck_at(cue.t, 5.0 * lvl, 1.4)
    mix.hits.append(cue.t)


def cue_reverse_swell(mix, cue) -> None:
    """Reverse reverb of the coming hit, ending exactly on the hit sample; its loud part (and a
    sub 'inhale') starts at the cue time: the J-cut lead (cue.t .. hit = 6-12 frames)."""
    hit_t = cue.params["hit"]
    lead = hit_t - cue.t
    kinds = [c.kind for c in edl.CUES if abs(c.t - hit_t) < 1e-6]
    big = "braam" in kinds
    a, sub, _ = hit_layers(1.0, seed=f"swell{hit_t}")
    src = a[: n_of(0.25)] + (0.6 * braam_attack() if big else 0.0)
    wet = dsp.convolve(src, mix.ir["void"])
    rev = wet[::-1]
    L = n_of(float(np.clip(3.0 * lead, 0.8, 2.0)))           # the lead + a little run-up
    rev = rev[-L:] if len(rev) >= L else np.concatenate([np.zeros((L - len(rev), 2)), rev])
    rev = rev * dsp.smoothstep(tt(L) / (L / SR * 0.8))[:, None]
    rev /= np.abs(rev).max() + 1e-9
    t0 = hit_t - L / SR
    g = db(-12.0 if big else -16.0)
    mix.add("music", rev, t0, g)
    # sub inhale + noise suck from the cue time to the hit
    m = n_of(lead + 0.35)
    tl = tt(m)
    u = np.clip(tl / (lead + 0.35), 0, 1)
    inh = np.sin(dsp.phase(28.0 + 20.0 * u ** 2)) * u ** 3
    suck = dsp.tv_filter(dsp.colored(m, dsp.rng(f"suck{hit_t}"), -3.0), 200.0 * 16 ** u, 1.5, "bp") * u ** 4
    x = inh * db(-14 if big else -19) + suck * db(-22 if big else -27)
    x *= dsp.fade(m, 0, n_of(0.004))
    mix.add("music", dsp.widen(x, 0.6, f"suck{hit_t}"), hit_t - m / SR)
    mix.event(cue.t, "reverse_swell_lead", hit=hit_t, lead_frames=round(lead * edl.FPS, 2))


# ============================================================================ Act I / II
def cue_room_tone_in(mix, cue) -> None:
    room_tone(mix, cue.t, cue.params.get("dur", 3.0))


def cue_drone_deep(mix, cue) -> None:
    """Act I: cold and hollow -- a D1 sub, a thin D2/A2 beating pair, faint air. Sparse on purpose."""
    t0, t1 = cue.t, cue.params["until"]
    n = n_of(t1 - t0 + 0.4)
    t = t0 + tt(n)
    lvl = dsp.curve(n, [(t0, -44), (S("S02", 10.0), -43), (S("S03", 15.5), -41), (S("S04", 21.5), -40),
                         (S("S06", 33.5), -37), (t1, -38)], t0, "db")
    breath = 1.0 + 0.17 * np.sin(dsp.TWO_PI * 0.043 * t + 1.0)
    env = lvl * breath * dsp.fade(n, n_of(0.3), n_of(0.8))
    sub = (abs_sine(D1, t0, n) + 0.18 * abs_sine(2 * D1, t0, n)) * env
    mix.add("drones", sub, t0)
    hol = dsp.curve(n, [(t0, -56), (S("S03", 15.5), -52), (S("S04", 21.5), -50), (t1, -49)], t0, "db") * dsp.fade(n, n_of(2.0), n_of(0.8))
    L = abs_sine(D2 - 0.05, t0, n) + 0.6 * abs_sine(A2 + 0.04, t0, n, 1.0)
    R = abs_sine(D2 + 0.06, t0, n, 0.5) + 0.6 * abs_sine(A2 - 0.05, t0, n, 2.0)
    mix.add("drones", np.stack([L, R], 1) * hol[:, None], t0, sends={"void": 0.2})
    r = dsp.rng("air")
    air = dsp.bp(dsp.colored(n, r, -3.0), 2500.0, 9000.0, order=2)
    air *= db(-58) * dsp.fade(n, n_of(3.0), n_of(1.0)) * (1 + 0.4 * np.sin(dsp.TWO_PI * 0.05 * t))
    mix.add("drones", dsp.pan(air, 0.6 * np.sin(dsp.TWO_PI * 0.031 * t)) * 1.4, t0)
    nb = dsp.bp(dsp.colored(n, dsp.rng("nb"), -3.0), 60.0, 300.0, order=2)
    nb *= dsp.curve(n, [(t0, -61), (S("S04", 21.5), -57), (t1, -56)], t0, "db") * dsp.fade(n, n_of(2.0), n_of(0.8))
    mix.add("drones", dsp.widen(nb, 0.8, "nb"), t0)


def cue_hull_creak(mix, cue) -> None:
    """Thermal stress in the hull: stick-slip friction into metal modes, plus a low groan."""
    r = dsp.rng("creak")
    dur = 2.6
    n = n_of(dur)
    t = tt(n)
    exc = np.zeros(n)
    for ph0, ph1 in ((0.05, 1.1), (1.35, 2.2)):
        tt0 = ph0
        while tt0 < ph1:
            u = (tt0 - ph0) / (ph1 - ph0)
            rate = 18 + 70 * np.sin(np.pi * u)
            exc[n_of(tt0)] += r.uniform(0.3, 1.0) * r.choice([-1, 1])
            tt0 += r.exponential(1.0 / rate)
    modes = [(83, 25, 1.0), (131, 30, 0.8), (197, 35, 0.7), (263, 40, 0.55), (347, 45, 0.5),
             (452, 50, 0.4), (611, 55, 0.3), (877, 60, 0.22), (1240, 70, 0.15), (1810, 80, 0.1)]
    ring = dsp.resonators(exc, modes)
    f = dsp.curve(n, [(0, 52), (1.1, 44), (1.35, 49), (2.2, 41), (dur, 40)])
    groan = dsp.bp(dsp.saw(f, n), 90.0, 600.0, order=2)
    genv = np.clip(np.sin(np.pi * np.clip(t / 1.15, 0, 1)), 0, 1) ** 2 + \
        0.8 * np.clip(np.sin(np.pi * np.clip((t - 1.35) / 0.9, 0, 1)), 0, 1) ** 2
    x = ring * 0.5 + groan * genv * 0.35
    x = x / (np.abs(x).max() + 1e-9) * dsp.fade(n, n_of(0.02), n_of(0.3))
    mix.add("fx", dsp.widen(x, 0.3, "creak"), cue.t, db(-35), p=0.3, sends={"hull": 0.35, "void": 0.08})


def cue_dish_servo(mix, cue) -> None:
    """The high-gain dish slews and locks: motor whine, gear mesh, bearing noise, lock clunk."""
    dur = cue.params.get("dur", 2.4)
    n = n_of(dur + 0.1)
    t = tt(n)
    fm = dsp.curve(n, [(0, 55), (0.35, 172), (1.0, 178), (1.7, 174), (dur - 0.35, 170), (dur, 70), (dur + 0.1, 60)])
    fm = fm * (1 + 0.006 * np.sin(dsp.TWO_PI * 5.5 * t))
    motor = dsp.bp(dsp.saw(fm, n), 150.0, 2600.0, order=2) * 0.35 + 0.1 * np.sin(dsp.phase(7 * fm))
    r = dsp.rng("servo")
    bearing = dsp.bp(r.standard_normal(n), 1500.0, 5000.0, order=2) * (0.5 + 0.5 * np.sin(dsp.phase(fm / 4)))
    x = (motor + 0.06 * bearing) * dsp.fade(n, n_of(0.06), n_of(0.09))
    mix.add("fx", dsp.widen(x, 0.2, "servo"), cue.t, db(-39), p=-0.2, sends={"hull": 0.3})
    # lock clunk
    m = n_of(1.2)
    tm = tt(m)
    cl = dsp.hp(r.standard_normal(m) * np.exp(-tm / 0.003), 2000.0) * 0.5
    cl += np.sin(dsp.phase(110 * (1 + 0.5 * np.exp(-tm / 0.01)))) * np.exp(-tm / 0.06)
    exc = np.zeros(m)
    exc[0] = 1.0
    cl += dsp.resonators(exc, [(412, 60, 0.9), (667, 70, 0.6), (1033, 80, 0.5), (1580, 90, 0.35)]) * 6.0
    cl /= np.abs(cl).max()
    mix.add("fx", dsp.widen(cl, 0.2, "clunk"), cue.t + dur, db(-31), p=-0.2, sends={"hull": 0.4})
    mix.event(cue.t + dur, "dish_lock")


def cue_lensing_swell(mix, cue) -> None:
    """Act II unease: detuned D2/A2 stacks that widen their beating and bend down 1.5 semitones,
    a bending D1, and the Juno Ganymede plasma-wave recording reversed an octave down (it falls)."""
    t0, t1 = cue.t, cue.params["until"]
    D = t1 - t0
    n = n_of(D)
    u = tt(n) / D
    bend = 2.0 ** (-1.5 / 12.0 * u ** 1.6)
    spread = 4.0 + 24.0 * u
    fc = 140.0 * (700.0 / 140.0) ** u
    lvl = db(-56 + 28 * u ** 1.5) * dsp.fade(n, n_of(0.5), n_of(0.03))
    st = np.zeros((n, 2))
    for c in range(2):
        y = saw_stack(D2 * bend, n, 6, spread, f"lens{c}") + 0.7 * saw_stack(A2 * bend, n, 6, spread, f"lensA{c}")
        st[:, c] = dsp.tv_filter(y, fc, 0.9, "lp", 128)
    mix.add("drones", st * lvl[:, None] * 0.5, t0, sends={"void": 0.25})
    sub = np.sin(dsp.phase(D1 * bend) + dsp.TWO_PI * D1 * t0) * db(-44 + 16 * u ** 1.4) * dsp.fade(n, n_of(0.5), n_of(0.03))
    mix.add("drones", sub, t0)
    gan = mix.recording("juno_ganymede")
    if gan is not None:
        g = dsp.mono(gan)
        g = dsp.lp(dsp.hp(g, 150.0, 2), 2100.0, 4)[::-1].copy()   # drop the 2.5 kHz line, reverse
        seg0, seg1 = len(g) / SR - 38.0, len(g) / SR - 6.0          # reversed: band falls ~1.5k -> 0.4k
        x = np.stack([dsp.granular(g, n, seg0, seg1, 0.5, 0.16, 36, f"gan{c}") for c in range(2)], 1)
        x = dsp.bp(x, 110.0, 1500.0, order=2)
        x /= np.sqrt(np.mean(x ** 2)) + 1e-9
        x *= (db(-52 + 21 * u ** 1.5) * dsp.fade(n, n_of(1.0), n_of(0.05)))[:, None]
        mix.add("drones", x, t0, sends={"void": 0.35})


def cue_shimmer(mix, cue) -> None:
    """S07 the razor arc: sparse glassy sine grains on the D harmonic set, high air, long tail."""
    dur = cue.params.get("dur", 4.0)
    r = dsp.rng("shimmer")
    pitches = [587.33, 880.0, 1174.66, 1318.51, 1760.0, 2349.32]
    n = n_of(dur + 1.5)
    out = np.zeros((n, 2))
    tg = 0.0
    while tg < dur:
        gd = r.uniform(0.4, 1.4)
        m = n_of(gd)
        f = r.choice(pitches) * (1 + r.uniform(-0.002, 0.002))
        g = np.sin(dsp.phase(f, m)) * np.sin(np.pi * tt(m) / gd) ** 2
        u = tg / dur
        amp = db(-40) * np.sin(np.pi * min(max(u, 0.02), 0.98)) ** 0.7 * r.uniform(0.4, 1.0)
        i = n_of(tg)
        pl = r.uniform(-0.9, 0.9)
        gl, gr = dsp.pan_gains(pl)
        out[i:i + m, 0] += g[: n - i] * gl * amp
        out[i:i + m, 1] += g[: n - i] * gr * amp
        tg += r.exponential(1 / 7.0)
    hi = dsp.bp(r.standard_normal(n), 5000.0, 10000.0, order=2) * db(-64)
    hi *= (1 + 0.5 * np.sin(dsp.TWO_PI * 9 * tt(n))) * dsp.fade(n, n_of(1.0), n_of(1.5))
    out += dsp.widen(hi, 1.0, "shimhi")
    mix.add("music", out, cue.t, sends={"void": 0.7})


def cue_debris_rumble(mix, cue) -> None:
    """S08: brown rumble + Mars wind an octave down, rock pass-bys with Doppler sweeps, dust on the hull."""
    dur = cue.params.get("dur", 5.0)
    t0 = cue.t
    n = n_of(dur)
    t = tt(n)
    r = dsp.rng("debris")
    env = dsp.curve(n, [(0, -40), (0.4, -26), (3.2, -21), (dur, -23)], kind="db") * dsp.fade(n, n_of(0.05), n_of(0.03))
    rum = dsp.lp(dsp.colored(n, r, -6.0), 110.0, order=4)
    rum /= np.sqrt(np.mean(rum ** 2)) + 1e-9
    y = dsp.widen(rum * env, 0.7, "rum")
    wind = mix.recording("insight_wind")
    if wind is not None:
        w = dsp.mono(wind)
        w = dsp.varispeed(w, np.arange(n) * 0.5 + n_of(3.0))      # an octave down
        w = dsp.hp(w, 18.0, 2)
        w /= np.sqrt(np.mean(w ** 2)) + 1e-9
        y += dsp.widen(w * env * db(-3), 0.9, "wind")
    # pass-bys
    k = 7
    times = np.sort(r.uniform(0.25, dur - 0.9, k))
    for j, tp in enumerate(times):
        d = r.uniform(0.45, 1.0)
        m = n_of(d)
        u = tt(m) / d
        fcen = 1500.0 * (280.0 / 1500.0) ** u
        s = dsp.tv_filter(dsp.colored(m, dsp.rng(f"pass{j}"), -3.0), fcen, 1.3, "bp", 64)
        s *= np.exp(-((u - 0.45) / 0.2) ** 2)
        close = r.uniform(0.3, 1.0)
        thump = np.sin(dsp.phase(58.0 * (1 + 0.4 * np.exp(-tt(m) / 0.03)))) * np.exp(-((u - 0.45) / 0.12) ** 2) * close
        direction = r.choice([-1.0, 1.0])
        st = dsp.pan(s * 1.2 + thump * 0.9, direction * np.linspace(-0.9, 0.9, m))
        i = n_of(tp)
        y[i:i + m] += st[: n - i] * db(-18) * close
    # dust on the hull
    kd = r.poisson(60 * dur)
    pos = r.integers(0, n, kd)
    keep = r.uniform(0, 1, kd) < 0.3 + 0.7 * pos / n
    dust = np.zeros((n, 2))
    pans = r.uniform(-1, 1, kd)
    a = r.uniform(0.2, 1.0, kd)
    dust[pos[keep], 0] += (a * np.cos((pans + 1) * np.pi / 4))[keep]
    dust[pos[keep], 1] += (a * np.sin((pans + 1) * np.pi / 4))[keep]
    y += dsp.hp(dust, 2500.0, 2) * db(-38)
    y[-n_of(0.025):] *= dsp.fade(n_of(0.025), 0, n_of(0.025))[:, None]
    mix.add("fx", y, t0, sends={"hull": 0.15, "void": 0.08})


def cue_near_silence(mix, cue) -> None:
    t1 = cue.t + cue.params.get("dur", 2.5)
    mix.dip(cue.t, t1, -14.0, stems=("drones", "interference"))
    mix.dip(cue.t, t1, -40.0, stems=("fx",))


# ============================================================================ the reveal
_BRAAM_CACHE: dict = {}


def braam_voice(n: int, seed: str) -> np.ndarray:
    """One channel of the braam: D minor power stack of detuned saws, saturated, filter blat."""
    t = tt(n)
    bend = 2.0 ** (-1.5 / 12.0 * dsp.smoothstep((t - 0.25) / 2.6))
    y = np.zeros(n)
    for f, a in ((D1, 1.0), (D2, 0.85), (A2, 0.6), (D3, 0.35), (F3, 0.16)):
        y += a * saw_stack(f * bend, n, 8, 12.0, f"{seed}{f}")
    y /= 1.6
    drive = 4.0 * (0.6 + 0.4 * np.exp(-t / 0.6))
    y = np.tanh(drive * y) / np.tanh(4.0)
    fc = dsp.curve(n, [(0, 110), (0.11, 2900), (0.5, 1900), (1.5, 950), (4.0, 420), (t[-1] + 1e-3, 220)], kind="exp")
    y_lp = dsp.tv_filter(y, fc, 1.25, "lp", 64)
    formant = dsp.bp(y, 500.0, 1200.0, order=2) * dsp.curve(n, [(0, 0.9), (1.5, 0.5), (t[-1] + 1e-3, 0.2)])
    return y_lp + 0.55 * formant


def braam_attack() -> np.ndarray:
    """First 250 ms of the braam (mono) for the reverse swell."""
    if "atk" not in _BRAAM_CACHE:
        m = n_of(0.25)
        _BRAAM_CACHE["atk"] = braam_voice(m, "braamL") * dsp.ar(m, 0.06, 1.0, 1.0)
    return _BRAAM_CACHE["atk"]


def cue_braam(mix, cue) -> None:
    lvl = cue.params.get("level", 1.0)
    tail = cue.params.get("tail", 7.0)
    n = n_of(tail)
    t = tt(n)
    env = dsp.ar(n, 0.06, 0.0, 1e9) * dsp.curve(n, [(0, 1.0), (0.4, 0.95), (3.5, 0.62), (tail, 0.0)])
    env *= np.exp(-np.maximum(t - 3.5, 0) / 1.3)
    st = np.stack([braam_voice(n, "braamL"), braam_voice(n, "braamR")], 1) * env[:, None]
    mix.add("music", st, cue.t, db(-9.0) * lvl, sends={"hall": 0.35})
    # impact layer on the attack
    a, sub, rumble = hit_layers(1.0, body_f=D2, sub_f=D1 * 1.25, tail=2.5, seed="braamhit")
    mix.add("fx", dsp.widen(a, 0.4, "bh"), cue.t, db(-10.0) * lvl, sends={"hall": 0.4})
    mix.add("fx", dsp.widen(rumble, 1.0, "bhr"), cue.t, db(-6.0) * lvl, sends={"hall": 0.3})
    mix.duck_at(cue.t, 9.0 * lvl, 2.8)
    mix.hits.append(cue.t)
    # the awe after the blast: a vast, slow D2/A2/D3/E3 chord that holds the reveal
    t0 = cue.t + 0.8
    t_end = next((c.t for c in edl.CUES if c.t > cue.t + 1.0), cue.t + 11.5)
    m = n_of(t_end - t0 + 1.0)
    lv = dsp.curve(m, [(t0, -60), (t0 + 3.0, -33), (t_end - 2.0, -31), (t_end, -29), (t_end + 1.0, -60)], 0.0 + t0, "db")
    ch = np.zeros((m, 2))
    for f, a_ in ((D2, 1.0), (A2, 0.8), (D3, 0.5), (E3, 0.3), (A3, 0.25)):
        for c in range(2):
            det = (-1) ** c * 0.12
            ch[:, c] += a_ * (abs_sine(f + det, t0, m, c) + 0.3 * saw_stack(f, m, 3, 7.0, f"awe{f}{c}"))
    ch = dsp.lp(ch, 900.0, order=2)
    mix.add("music", ch * lv[:, None] * 0.4, t0, sends={"void": 0.35})
    # the hole's hum under the reveal (sub arc: rebuilds from the drop toward S11)
    m2 = n_of(t_end - cue.t + 0.5)
    hv = dsp.curve(m2, [(cue.t, -70), (cue.t + 4.0, -36), (t_end, -30), (t_end + 0.5, -30)], cue.t, "db")
    hum = (abs_sine(D1, cue.t, m2) + 0.5 * abs_sine(A1, cue.t, m2, 0.3)) * hv
    mix.add("drones", hum, cue.t)


def cue_sub_drop(mix, cue) -> None:
    lvl = cue.params.get("level", 1.0)
    dur = 7.0
    n = n_of(dur)
    t = tt(n)
    f = 28.0 + (60.0 - 28.0) * np.exp(-t / 1.0)            # 60 -> 28 Hz, mostly within 3 s
    ph = dsp.phase(f)
    a = (1 - np.exp(-t / 0.008)) * np.exp(-t / 2.4) * dsp.fade(n, 0, n_of(1.0))
    x = (np.sin(ph) + db(-12) * np.sin(2 * ph) + db(-18) * np.sin(3 * ph)) * a
    mix.add("fx", x, cue.t, db(-9.0) * lvl)


# ============================================================================ Act III
def cue_tension_pad(mix, cue) -> None:
    """S11-S14: a string-like cluster (D, A, D, Eb, A) with accelerating tremolo and an opening
    filter over a growing D1 pedal. Rendered in film time; the time-stretch warps it after 72.5."""
    t0, t1 = cue.t, cue.params["until"]
    n = n_of(t1 - t0 + 0.6)
    t = t0 + tt(n)
    u = np.clip((t - t0) / (T_SLOW - t0), 0, 1)
    fc = 300.0 * (2300.0 / 300.0) ** u
    trem_rate = 5.0 + 7.0 * u ** 1.5
    trem = 1.0 - 0.35 * (0.5 + 0.5 * np.sin(np.cumsum(dsp.TWO_PI * trem_rate / SR)))
    lvl = dsp.curve(n, [(t0, -60), (t0 + 1.5, -36), (S("S12", 65.5), -30), (S("S13", 69.5), -24), (T_SLOW, -19),
                         (max(t1, T_SLOW + 0.1), -19)], t0, "db")
    lvl *= dsp.fade(n, 0, n_of(0.6))
    st = np.zeros((n, 2))
    for c in range(2):
        y = np.zeros(n)
        for f, a in ((D2, 0.8), (A2, 0.7), (D3, 0.6), (155.563, 0.45), (A3, 0.4)):
            y += a * saw_stack(f, n, 5, 9.0, f"ten{f}{c}")
        st[:, c] = dsp.tv_filter(y, fc, 0.8, "lp", 128)
    mix.add("music", st * (lvl * trem)[:, None] * 0.35, t0, sends={"void": 0.25})
    pv = dsp.curve(n, [(t0, -60), (t0 + 2.0, -32), (S("S12", 65.5), -27), (S("S13", 69.5), -22), (T_SLOW, -19),
                        (max(t1, T_SLOW + 0.1), -19)], t0, "db") * dsp.fade(n, 0, n_of(0.6))
    mix.add("drones", (abs_sine(D1, t0, n) + 0.3 * abs_sine(D2, t0, n)) * pv, t0)


def cue_whoosh(mix, cue) -> None:
    lvl = cue.params.get("level", 0.8)
    d = 2.4
    n = n_of(d)
    u = tt(n) / d
    fc = dsp.curve(n, [(0, 300), (0.45 * d, 4000), (d, 800)], kind="exp")
    x = dsp.tv_filter(dsp.colored(n, dsp.rng("whoosh"), -3.0), fc, 1.1, "bp", 64)
    x *= np.exp(-((u - 0.45) / 0.18) ** 2)
    x /= np.abs(x).max() + 1e-9
    st = dsp.pan(x, np.linspace(-0.8, 0.8, n)) * 1.4
    mix.add("fx", st, cue.t - 0.45 * d + 0.08, db(-10.0) * lvl, sends={"void": 0.2})


def cue_shepard_riser(mix, cue) -> None:
    """Shepard-Risset glissando (octave partials, Gaussian spectral window) + a sweeping noise riser."""
    t0, t1 = cue.t, cue.params["until"]
    n = n_of(t1 - t0 + 0.5)
    t = tt(n)
    oct_rate = 1.0 / 5.5
    y = np.zeros(n)
    c0 = np.log2(520.0)
    for k in range(9):
        lf = np.log2(40.0) + ((k + oct_rate * t) % 9.0)
        f = 2.0 ** lf
        a = np.exp(-0.5 * ((lf - c0) / 1.5) ** 2)
        y += a * np.sin(dsp.phase(f))
    lvl = dsp.curve(n, [(t0, -60), (t0 + 1.0, -40), (S("S13", 69.5), -32), (T_SLOW, -24), (max(t1, T_SLOW + 0.1), -22)],
                     t0, "db") * dsp.fade(n, 0, n_of(0.5))
    mix.add("music", dsp.widen(y * lvl * 0.5, 0.7, "shep"), t0, sends={"void": 0.3})
    u = np.clip(t / (T_SLOW - t0), 0, 1)
    nz = dsp.tv_filter(dsp.colored(n, dsp.rng("riser"), -3.0), 400.0 * 15 ** u, 2.0, "bp", 64)
    nv = dsp.curve(n, [(t0, -70), (t0 + 2, -46), (T_SLOW, -27), (max(t1, T_SLOW + 0.1), -27)], t0, "db") * dsp.fade(n, 0, n_of(0.5))
    mix.add("music", dsp.widen(nz * nv, 1.0, "riser"), t0, sends={"void": 0.2})


def cue_interference_burst(mix, cue) -> None:
    """S13: the signal tears the image. Bit-crushed bursts, digital squeals, stutters of the signal,
    criss-crossing heterodyne sweeps, torn low rumble, dropouts. Hard stop at the end."""
    dur = cue.params.get("dur", 3.0)
    t0 = cue.t
    n = n_of(dur)
    t = tt(n)
    u = t / dur
    ramp = 0.35 + 0.65 * u ** 1.5                     # same law as edl.interference in S13
    r = dsp.rng("burst")
    out = np.zeros((n, 2))
    # stutter source: a radio pulse of the signal
    sp = [p for p in edl.signal_pulses() if p.t < t0]
    src_c, src_r, _ = motif.signal_pulse(sp[-1], "burstsrc", 1.5) if sp else (np.zeros(n), np.zeros(n), 1)
    src = src_r + 0.5 * src_c
    skr = mix.recording("cassini_skr")
    skr = skr if skr is not None else r.standard_normal(n_of(10.0)) * 0.2
    tp = 0.0
    while tp < dur:
        uu = tp / dur
        d = r.uniform(0.02, 0.15) * (1.0 - 0.5 * uu)
        m = n_of(d)
        kind = r.choice(["noise", "square", "skr", "stutter", "gap"], p=[0.3, 0.18, 0.2, 0.2, 0.12])
        tm = tt(m)
        if kind == "noise":
            s = dsp.crush(r.standard_normal(m) * 0.5, r.uniform(3, 6), int(r.integers(3, 14)))
        elif kind == "square":
            s = np.sign(np.sin(dsp.TWO_PI * r.uniform(300, 2600) * tm)) * 0.35
            s = dsp.crush(s, 4, int(r.integers(2, 8)))
        elif kind == "skr":
            i = int(r.integers(0, len(skr) - m - 1))
            s = dsp.crush(skr[i:i + m] / (np.abs(skr).max() + 1e-9), r.uniform(4, 8), int(r.integers(1, 6)))
        elif kind == "stutter":
            sl = n_of(r.uniform(0.02, 0.06))
            i = int(r.integers(0, max(1, len(src) - sl)))
            piece = src[i:i + sl] / (np.abs(src).max() + 1e-9)
            s = np.tile(piece, m // max(sl, 1) + 1)[:m] * 0.8
        else:
            s = np.zeros(m)
        s = s * dsp.fade(m, n_of(0.001), n_of(0.002)) * ramp[min(n_of(tp), n - 1)]
        i0 = n_of(tp)
        i1 = min(n, i0 + m)
        gl, gr = dsp.pan_gains(r.uniform(-1, 1))
        out[i0:i1, 0] += s[: i1 - i0] * gl
        out[i0:i1, 1] += s[: i1 - i0] * gr
        tp += d + (r.uniform(0.0, 0.05) if kind != "gap" else 0.0) * (1 - uu)
    out = dsp.bp(out, 150.0, 9000.0, order=2) * db(-12)
    # criss-crossing heterodyne sweeps
    for k in range(9):
        d = r.uniform(0.5, 1.4)
        m = n_of(d)
        f1, f2 = r.uniform(400, 3600), r.uniform(400, 3600)
        f = dsp.curve(m, [(0, f1), (d, f2)], kind="exp")
        s = np.sin(dsp.phase(f)) * np.sin(np.pi * tt(m) / d) ** 2
        st = dsp.pan(s, np.linspace(-1, 1, m) * r.choice([-1, 1]))
        i0 = n_of(r.uniform(0, dur - 0.2))
        i1 = min(n, i0 + m)
        out[i0:i1] += st[: i1 - i0] * db(-24) * ramp[i0]
    # continuous static rising
    stat = dsp.bp(r.standard_normal((n, 2)), 400.0, 7000.0, order=2)
    spk = np.abs(dsp.bp(r.standard_normal(n), 30.0, 300.0, order=2))
    spk /= np.sqrt(np.mean(spk ** 2)) + 1e-9
    out += stat * (np.sqrt(spk) * ramp ** 2)[:, None] * db(-17)
    # torn low rumble (sub arc: the climax)
    rum = dsp.lp(dsp.colored(n, r, -6.0), 180.0, order=4)
    rum /= np.sqrt(np.mean(rum ** 2)) + 1e-9
    gate = dsp.lp((r.uniform(0, 1, n_of(dur) // 480 + 1) > 0.3).repeat(480)[:n].astype(float), 60.0, 1)
    out += dsp.widen(rum * (0.5 + 0.5 * gate) * ramp ** 1.5 * db(-9), 0.8, "tear")
    out = 0.17 * np.tanh(out * db(8.0) / 0.17)          # tearing = saturation; bounded crest factor
    out *= dsp.fade(n, n_of(0.005), n_of(0.004))[:, None]
    mix.add("interference", out, t0, sends={"void": 0.1})
    # digital dropouts across the mix, denser toward the end
    for k in range(int(10 * dur)):
        tp = t0 + dur * r.uniform() ** 0.6
        if r.uniform() < 0.55:
            mix.dropout(tp, r.uniform(0.015, 0.07))


# ============================================================================ Act IV: time
def ship_rate(t: float) -> float:
    dt = 1e-3
    return (edl.ship_clock(t + dt) - edl.ship_clock(t)) / dt


def cue_time_stretch(mix, cue) -> None:
    """72.5-82.5: the world bus slows and sinks (varispeed at (dtau/dt)^beta), the beacon's own
    flashes carry the EDL stretch; a ghost of its tone glides down with the ship's clock; the last
    flash echoes once around the ring; then the fall: a descending Shepard tone, a sinking sub and
    the roar build to the hard cut."""
    t0 = cue.t
    t1 = t0 + cue.params.get("dur", 10.0)
    mix.warp = (t0, t1)
    # the slowed world recedes as the fall takes over (output-time gain on the warped stems, dB)
    s15 = S("S15", t0 + 3.5)
    mix.warp_gain = [(t0, -3.0), (s15 - 0.2, -5.0), (s15 + 3.0, -14.0), (t1, -16.0)]
    # entry whump
    m = n_of(1.2)
    tm = tt(m)
    wh = np.sin(dsp.phase(35.0 + 85.0 * np.exp(-tm / 0.25))) * (1 - np.exp(-tm / 0.004)) * np.exp(-tm / 0.45)
    wh += dsp.lp(dsp.colored(m, dsp.rng("whump"), -6.0), 300.0) * np.exp(-tm / 0.3) * 0.2
    mix.add("fx", dsp.widen(wh, 0.5, "whump"), t0, db(-13), post=True, sends={"hall": 0.3})
    # ghost glissando: the beacon's tone frozen and sinking with the ship's clock
    n = n_of(t1 - t0)
    t = t0 + tt(n)
    ts, gv = ctrl_curve(ship_rate, t0, t1, 500)
    g = to_samples(ts, gv, t0, n)
    f = motif.F_BEACON * g
    ph = dsp.phase(f)
    tone = np.sin(ph + 0.6 * np.sin(motif.FM_RATIO * ph)) + 0.4 * np.sin((motif.FM_RATIO - 1) * ph)
    a = dsp.smoothstep((t - t0 - 0.2) / 2.0) * np.exp(-np.maximum(t - s15 - 1.0, 0) / 1.4) * (f > 30.0)
    tone = dsp.hp(tone * a, 25.0, 2)
    mix.add("beacon", dsp.widen(tone, 0.8, "ghost"), t0, db(SIGNAL_DB - 12), sends={"void": 0.7})
    # the ring echo of the last beacon flash (a measured S15 light curve already contains it)
    fl, measured = beacon_flashes()
    if measured:
        return_echo = False
    else:
        return_echo = True
    last = [f for f in fl if f.t < t1][-1]
    x, env = motif.voice(last.long, last.stretch * 1.25, last.redshift / 1.25, "echo")
    x = dsp.lp(x * 0.6 + motif.radio(x, env, "echo", 1.3) * 0.9, 1400.0, order=2)
    if return_echo:
        mix.add("beacon", dsp.widen(x, 0.5, "echo"), last.t + RING_ECHO_DELAY, db(SIGNAL_DB - 9), p=0.6,
                sends={"void": 0.9})
        mix.event(last.t + RING_ECHO_DELAY, "ring_echo", of=round(last.t, 3))
    # ---- the fall (S15): everything sinks in pitch while it grows in weight, until the hard cut
    fall0 = s15
    tf0 = fall0 - 1.0
    n = n_of(t1 - tf0)
    tl = tt(n)
    u = tl / (t1 - tf0)
    grow = dsp.curve(n, [(0, -70), (1.0, -36), (3.0, -30), (t1 - tf0 - 2.5, -19), (t1 - tf0, -9)], kind="db")
    # descending Shepard (endless fall), spectral window sinking 420 -> 140 Hz
    y = np.zeros(n)
    cen = np.log2(420.0) + np.log2(140.0 / 420.0) * u
    for k in range(8):
        lf = np.log2(25.0) + ((k - tl / 6.0) % 8.0)
        a = np.exp(-0.5 * ((lf - cen) / 1.2) ** 2)
        y += a * np.sin(dsp.phase(2.0 ** lf))
    mix.add("music", dsp.widen(y * grow * 0.7, 0.8, "fallshep"), tf0, post=True, sends={"void": 0.25})
    # redshift wash: band noise whose centre sinks 2.6 kHz -> 320 Hz (the light going red)
    r = dsp.rng("wash")
    wash = dsp.tv_filter(dsp.colored(n, r, -3.0), 2600.0 * (320.0 / 2600.0) ** u, 0.8, "bp", 128)
    wash /= np.sqrt(np.mean(wash ** 2)) + 1e-9
    mix.add("music", dsp.widen(np.tanh(wash / 2.5) * 2.5 * grow * db(-7), 1.0, "wash"), tf0, post=True, sends={"void": 0.2})
    # roar: brown noise + Mars wind two octaves down, LP sinking 600 -> 140 Hz
    r = dsp.rng("roar")
    roar = dsp.colored(n, r, -6.0)
    wind = mix.recording("insight_wind")
    if wind is not None:
        w = dsp.mono(wind)
        w = dsp.varispeed(w, np.arange(n) * 0.25 + n_of(1.0))
        roar = roar + 1.5 * w / (np.sqrt(np.mean(w ** 2)) + 1e-9)
    roar = dsp.tv_filter(roar, 600.0 * (140.0 / 600.0) ** u, 0.9, "lp", 128)
    roar /= np.sqrt(np.mean(roar ** 2)) + 1e-9
    roar = np.tanh(roar / 2.5) * 2.5
    mix.add("drones", dsp.widen(roar * grow * db(-6), 0.9, "roar"), tf0, post=True)
    # sinking sub D1 -> A0 (27.5 Hz) with 2nd harmonic
    fs = D1 * (27.5 / D1) ** u
    ph = dsp.phase(fs)
    sub = (np.sin(ph) + 0.5 * np.sin(2 * ph)) * grow * db(-3)
    mix.add("drones", sub, tf0, post=True)


def cue_hard_cut_silence(mix, cue) -> None:
    mix.event(cue.t, "hard_cut", until=cue.t + cue.params.get("dur", 2.0))


def cue_title_sting(mix, cue) -> None:
    """Deep hit + a tonal bloom made of the signal's own FM timbre (D2, D3, A3), faded to nothing by
    the end of the tail so the last pulse is alone."""
    lvl = cue.params.get("level", 1.0)
    tail = cue.params.get("tail", 4.5)
    a, sub, rumble = hit_layers(1.0, body_f=D2, sub_f=D1 * 1.25, tail=1.8, seed="title")
    g = db(-9.0) * lvl
    mix.add("fx", dsp.widen(a, 0.4, "th"), cue.t, g, post=True, sends={"hall": 0.4})
    mix.add("fx", sub, cue.t, g * 0.8, post=True)
    mix.add("fx", dsp.widen(rumble, 1.0, "thr"), cue.t, g, post=True, sends={"hall": 0.25})
    n = n_of(tail)
    t = tt(n)
    env = (1 - np.exp(-t / 0.25)) * np.exp(-t / 1.6)
    bloom = np.zeros((n, 2))
    rb = dsp.rng("bloom")
    for f, amp in ((D2, 0.8), (D3, 0.7), (A3, 0.6), (2 * D3, 0.4), (2 * A3, 0.2)):
        for c in range(2):
            ph = dsp.phase(f * (1 + (-1) ** c * 0.0007), n, rb.uniform(0, dsp.TWO_PI))
            idx = 1.2 * np.exp(-t / 0.8) + 0.3
            bloom[:, c] += amp * np.sin(ph + idx * np.sin(motif.FM_RATIO * ph))
    subd = abs_sine(D1, cue.t, n) * (1 - np.exp(-t / 0.01)) * np.exp(-t / 1.3)
    bloom = 0.8 * np.tanh(bloom * env[:, None] * 0.35 / 0.8) + subd[:, None] * 0.25
    mix.add("music", bloom, cue.t, db(2.0) * lvl, post=True, sends={"void": 0.45})
    mix.tail_end(cue.t + tail)
    mix.hits.append(cue.t)


def cue_last_signal(mix, cue) -> None:
    mix.event(cue.t, "last_signal_alone")


HANDLERS = {name[4:]: fn for name, fn in globals().items() if name.startswith("cue_")}

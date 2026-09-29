"""Edit decision list: the single source of truth for timing.

Picture (shot ranges, beacon flashes, light flicker, image interference) and sound (signal pulses,
hits, risers, silence) are both driven from here. See docs/shot_plan.md for the story.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

FPS = 24
DURATION = 90.0
NFRAMES = int(round(DURATION * FPS))
WIDTH, HEIGHT = 1920, 804          # 2.39:1 active picture


@dataclass(frozen=True)
class Shot:
    id: str
    start: float
    end: float
    title: str
    kind: str                       # "black", "shot", "title"
    layers: tuple = ()              # which renderers feed it: "tracer", "blender", "comp"

    @property
    def dur(self) -> float:
        return self.end - self.start

    @property
    def f0(self) -> int:
        return int(round(self.start * FPS))

    @property
    def f1(self) -> int:               # exclusive
        return int(round(self.end * FPS))

    def local(self, t: float) -> float:
        """0..1 progress through the shot."""
        return min(1.0, max(0.0, (t - self.start) / self.dur))


SHOTS: list[Shot] = [
    Shot("BLK0", 0.0, 3.0, "black open", "black"),
    Shot("S01", 3.0, 10.0, "The Deep", "shot", ("tracer", "blender")),
    Shot("S02", 10.0, 15.5, "Hull", "shot", ("tracer", "blender")),
    Shot("S03", 15.5, 21.5, "Listening", "shot", ("tracer", "blender")),
    Shot("S04", 21.5, 28.0, "Wrong stars", "shot", ("tracer", "blender")),
    Shot("S05", 28.0, 33.5, "The pull", "shot", ("tracer", "blender")),
    Shot("S06", 33.5, 37.0, "Glimpse: light", "shot", ("tracer", "blender")),
    Shot("S07", 37.0, 41.0, "Glimpse: edge", "shot", ("tracer",)),
    Shot("S08", 41.0, 46.0, "Debris", "shot", ("tracer", "blender")),
    Shot("S09", 46.0, 48.5, "Breath", "shot", ("tracer", "blender")),
    Shot("S10", 48.5, 60.0, "The reveal", "shot", ("tracer", "blender")),
    Shot("S11", 60.0, 65.5, "Scale", "shot", ("tracer", "blender")),
    Shot("S12", 65.5, 69.5, "Under the arch", "shot", ("tracer", "blender")),
    Shot("S13", 69.5, 72.5, "Interference", "shot", ("tracer",)),
    Shot("S14", 72.5, 76.0, "Time", "shot", ("tracer", "blender")),
    Shot("S15", 76.0, 82.5, "The fall", "shot", ("tracer",)),
    Shot("BLK1", 82.5, 84.5, "silence", "black"),
    Shot("TITLE", 84.5, 89.0, "THE LAST SIGNAL", "title"),
    Shot("BTN", 89.0, 90.0, "button", "black"),
]
SHOT_BY_ID = {s.id: s for s in SHOTS}


def shot_at(t: float) -> Shot:
    for s in SHOTS:
        if s.start <= t < s.end:
            return s
    return SHOTS[-1]


def frame_time(frame: int) -> float:
    """Time at the centre of the shutter for a frame (frame 0 covers [0, 1/24))."""
    return frame / FPS


# ---------------------------------------------------------------------------- the motif
# The beacon/signal pattern: three quick pulses and one long one, in the ship's proper time.
MOTIF = ((0.00, False), (0.18, False), (0.36, False), (0.80, True))
BEACON_CYCLE = 2.0          # s of ship proper time per motif repetition
FLASH_SHORT = 0.05          # s
FLASH_LONG = 0.28           # s
SIGNAL_STRETCH = 4.5        # the received signal is the motif slowed by this factor


@dataclass
class Pulse:
    t: float                # film time of arrival (s)
    long: bool
    stretch: float          # time-dilation factor applied to this pulse (1 = ship's own clock)
    gain: float             # 0..1
    redshift: float = 1.0   # frequency ratio g (1 = none, <1 = red-shifted)
    source: str = "signal"  # "signal" (distant, received) or "beacon" (our ship)


def _motif_train(t0: float, t1: float, cycle: float, stretch: float, gain, source: str,
                 phase: float = 0.0, g: float = 1.0) -> list[Pulse]:
    out = []
    k = math.floor((t0 - phase) / cycle) - 1
    while True:
        base = phase + k * cycle
        if base > t1:
            break
        for off, long_ in MOTIF:
            t = base + off * stretch
            if t0 <= t < t1:
                gv = gain(t) if callable(gain) else gain
                if gv > 0:
                    out.append(Pulse(t, long_, stretch, gv, g, source))
        k += 1
    return out


def signal_pulses() -> list[Pulse]:
    """The received signal (audio + interference). Slow, deep: the motif stretched x4.5."""
    cyc = BEACON_CYCLE * SIGNAL_STRETCH   # 9 s
    def gain(t):
        if t < 3.0:
            return 0.55
        if 41.0 <= t < 48.5:              # debris + breath: the signal drops out
            return 0.0
        if t >= 69.5:
            return 0.0
        # grows through Act I-II
        return min(1.0, 0.55 + 0.45 * (t - 3.0) / 38.0)
    pulses = _motif_train(0.0, 69.5, cyc, SIGNAL_STRETCH, gain, "signal", phase=0.6, g=1.0 / SIGNAL_STRETCH)
    # the button: one last slow pulse in the dark (our ship's, now)
    pulses.append(Pulse(89.05, True, SIGNAL_STRETCH, 0.8, 1.0 / SIGNAL_STRETCH, "signal"))
    return pulses


T_DILATE = 72.5     # time dilation becomes perceptible (S14)
T_FALL = 76.0       # S15: from here the tracer's measured light curve is the ship's clock
G_FALL0_DEFAULT = 0.83   # beacon redshift g at the start of S15 (ship at r ~ 10.5 M) if not yet measured


def _fall_rate_table():
    """(t, g) for t >= T_FALL: the smoothed redshift of the beacon measured by tls.lightcurve
    (shots/S15/lightcurve.json), else an exponential stand-in. g = dtau/dt, the ship's clock rate."""
    import json
    from pathlib import Path as _P
    f = _P(__file__).resolve().parents[1] / "shots" / "S15" / "lightcurve.json"
    ts = [T_FALL + i * 0.01 for i in range(0, 1401)]
    try:
        raw = json.loads(f.read_text())
        rows = raw["rows"] if isinstance(raw, dict) else raw
        pts = sorted((r[0], r[2]) for r in rows if r[2] > 0)
        # smooth the colour-fit noise: running mean over +-0.25 s
        tt = [p_[0] for p_ in pts]
        gg = []
        for i, t_ in enumerate(tt):
            w = [p_[1] for p_ in pts if abs(p_[0] - t_) <= 0.25]
            gg.append(sum(w) / len(w))
        gs = []
        for t_ in ts:
            if t_ <= tt[-1]:
                j = max(0, min(len(tt) - 2, next((k for k in range(len(tt) - 1) if tt[k + 1] >= t_), len(tt) - 2)))
                u = (t_ - tt[j]) / max(tt[j + 1] - tt[j], 1e-9)
                gs.append(gg[j] + u * (gg[j + 1] - gg[j]))
            else:   # beyond the measurement: keep sinking with the horizon's e-folding
                gs.append(gs[-1] * math.exp(-0.01 / 1.2))
    except (OSError, KeyError, ValueError, IndexError):
        gs = [G_FALL0_DEFAULT * math.exp(-(t_ - T_FALL) / 3.2) for t_ in ts]
    return ts, [max(g, 1e-3) for g in gs]


_FALL = None


def ship_rate(t: float) -> float:
    """dtau/dt of the ship's clock as the film's camera sees it (= the beacon's redshift g)."""
    global _FALL
    if t <= T_DILATE:
        return 1.0
    if _FALL is None:
        _FALL = _fall_rate_table()
    if t <= T_FALL:   # S14: the onset, easing from 1 to the value the measured fall starts with
        u = (t - T_DILATE) / (T_FALL - T_DILATE)
        return 1.0 - (1.0 - _FALL[1][0]) * u * u * (3 - 2 * u)
    ts, gs = _FALL
    i = min(int((t - T_FALL) / 0.01), len(ts) - 2)
    u = (t - ts[i]) / 0.01
    return gs[i] + min(max(u, 0.0), 1.0) * (gs[i + 1] - gs[i])


_CLOCK = None


def ship_clock(t: float) -> float:
    """Ship proper time as seen by the film's camera (the beacon's clock): the integral of ship_rate.
    Normal until S14; gentle dilation through S14 (x1 -> x1.2, what r ~ 10 M really gives); S15 follows
    the relativistic infall measured from the tracer, down to a frozen, fading clock."""
    global _CLOCK
    if t <= T_DILATE:
        return t
    if _CLOCK is None:
        dt = 0.005
        tab, tau = [T_DILATE], [T_DILATE]
        while tab[-1] < 95.0:
            t_ = tab[-1]
            tau.append(tau[-1] + dt * 0.5 * (ship_rate(t_) + ship_rate(t_ + dt)))
            tab.append(t_ + dt)
        _CLOCK = (tab, tau)
    tab, tau = _CLOCK
    i = min(int((t - T_DILATE) / 0.005), len(tab) - 2)
    u = (t - tab[i]) / 0.005
    return tau[i] + u * (tau[i + 1] - tau[i])


def beacon_flashes(t0: float = 0.0, t1: float = 82.5) -> list[Pulse]:
    """Our ship's strobe: the motif at the ship's own rate, slowed by time dilation at the end."""
    out = []
    # invert ship_clock numerically on a fine grid
    ts = [t0 + i / 480.0 for i in range(int((t1 - t0) * 480) + 1)]
    taus = [ship_clock(t) for t in ts]
    tau0, tau1 = taus[0], taus[-1]
    k = math.floor(tau0 / BEACON_CYCLE) - 1
    j = 0
    while True:
        base = k * BEACON_CYCLE
        if base > tau1:
            break
        for off, long_ in MOTIF:
            tau = base + off
            if tau0 <= tau < tau1:
                while j + 1 < len(taus) and taus[j + 1] < tau:
                    j += 1
                # linear inverse
                a, b = taus[j], taus[min(j + 1, len(taus) - 1)]
                u = 0.0 if b == a else (tau - a) / (b - a)
                t = ts[j] + u * (ts[min(j + 1, len(ts) - 1)] - ts[j])
                dt = 1e-3
                stretch = dt / max(ship_clock(t + dt) - ship_clock(t), 1e-9)
                g = 1.0 / stretch
                out.append(Pulse(t, long_, stretch, 1.0, g, "beacon"))
        k += 1
    return out


def beacon_intensity(t: float, flashes: list[Pulse] | None = None) -> float:
    """Visible strobe intensity at film time t (0..~1), xenon-like: fast attack, short decay."""
    flashes = flashes if flashes is not None else _BEACON
    v = 0.0
    for p in flashes:
        d = t - p.t
        dur = (FLASH_LONG if p.long else FLASH_SHORT) * p.stretch
        if -0.01 < d < dur + 0.5 * p.stretch:
            env = 1.0 if d < dur else math.exp(-(d - dur) / (0.035 * p.stretch))
            if d < 0:
                env = 0.0
            v = max(v, env * p.gain)
    return v


def interference(t: float) -> float:
    """0..1: how hard the signal is hitting the ship's electronics and the image at time t."""
    v = 0.0
    for p in _SIGNAL:
        d = t - p.t
        if -0.05 < d < 1.2:
            v = max(v, p.gain * math.exp(-max(d, 0) / 0.35) * (1.4 if p.long else 1.0))
    # S13: the signal peaks, continuous tearing
    s13 = SHOT_BY_ID["S13"]
    if s13.start <= t < s13.end:
        u = s13.local(t)
        v = max(v, 0.35 + 0.65 * u ** 1.5)
    return min(v, 1.0)


# ---------------------------------------------------------------------------- sound cues
@dataclass
class Cue:
    t: float
    kind: str
    params: dict = field(default_factory=dict)


CUES: list[Cue] = [
    Cue(0.0, "room_tone_in", {"dur": 3.0}),
    Cue(3.0, "drone_deep", {"until": 41.0}),
    Cue(10.0, "hull_creak", {}),
    Cue(15.5, "dish_servo", {"dur": 2.4}),
    Cue(21.5, "lensing_swell", {"until": 33.5}),
    Cue(33.2, "reverse_swell", {"hit": 33.5}),
    Cue(33.5, "low_hit", {"level": 0.6}),
    Cue(37.0, "shimmer", {"dur": 4.0}),
    Cue(41.0, "debris_rumble", {"dur": 5.0}),
    Cue(46.0, "near_silence", {"dur": 2.5}),
    Cue(48.2, "reverse_swell", {"hit": 48.5}),
    Cue(48.5, "braam", {"level": 1.0, "tail": 7.0}),
    Cue(48.5, "sub_drop", {"level": 1.0}),
    Cue(60.0, "low_hit", {"level": 0.7}),
    Cue(60.0, "tension_pad", {"until": 76.0}),
    Cue(65.5, "whoosh", {"level": 0.8}),
    Cue(66.5, "shepard_riser", {"until": 76.0}),
    Cue(69.5, "interference_burst", {"dur": 3.0}),
    Cue(72.5, "time_stretch", {"dur": 10.0}),
    Cue(82.5, "hard_cut_silence", {"dur": 2.0}),
    Cue(84.5, "title_sting", {"level": 1.0, "tail": 4.5}),
    Cue(89.05, "last_signal", {}),
]
SILENCE = [(82.5, 84.5)]              # true digital zero


_SIGNAL = signal_pulses()
_BEACON = beacon_flashes()


def summary() -> str:
    lines = [f"{s.id:6s} {s.start:5.1f}-{s.end:5.1f} ({s.dur:4.1f}s, frames {s.f0}-{s.f1 - 1})  {s.title}" for s in SHOTS]
    lines.append(f"signal pulses: {len(_SIGNAL)}  beacon flashes: {len(_BEACON)}  cues: {len(CUES)}")
    return "\n".join(lines)


if __name__ == "__main__":
    print(summary())

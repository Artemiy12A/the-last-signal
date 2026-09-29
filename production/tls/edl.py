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
    # review round 1 (2026-09-29): reveal at 46 s, S11 a 2.5 s speck, the time goes to the ending
    Shot("BLK0", 0.0, 3.0, "black open", "black"),
    Shot("S01", 3.0, 8.0, "The Deep", "shot", ("tracer", "blender")),
    Shot("S02", 8.0, 13.5, "Hull", "shot", ("tracer", "blender")),
    Shot("S03", 13.5, 19.5, "Listening", "shot", ("tracer", "blender")),
    Shot("S04", 19.5, 26.0, "Wrong stars", "shot", ("tracer", "blender")),
    Shot("S05", 26.0, 31.5, "The pull", "shot", ("tracer", "blender")),
    Shot("S06", 31.5, 35.5, "Glimpse: light", "shot", ("tracer", "blender")),
    Shot("S07", 35.5, 38.5, "Glimpse: edge", "shot", ("tracer",)),
    Shot("S08", 38.5, 43.5, "Debris", "shot", ("tracer", "blender")),
    Shot("S09", 43.5, 46.0, "Breath", "shot", ("tracer", "blender")),
    Shot("S10", 46.0, 57.5, "The reveal", "shot", ("tracer", "blender")),
    Shot("S11", 57.5, 60.0, "Scale", "shot", ("tracer", "blender")),
    Shot("S12", 60.0, 65.0, "Under the arch", "shot", ("tracer", "blender")),
    Shot("S13", 65.0, 69.0, "Interference", "shot", ("tracer",)),
    Shot("S14", 69.0, 73.5, "Last look", "shot", ("tracer", "blender")),
    Shot("S15", 73.5, 82.5, "The fall", "shot", ("tracer",)),
    Shot("BLK1", 82.5, 84.5, "silence", "black"),
    Shot("TITLE", 84.5, 88.6, "THE LAST SIGNAL", "title"),
    Shot("BTN", 88.6, 90.0, "button", "black"),
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


def _start(sid: str) -> float:
    return next(x.start for x in SHOTS if x.id == sid)


# the end restates the motif at the signal's tempo: three short pulses under the title, the long one
# in the black after it (the ship's light, now the signal)
TITLE_MOTIF_T0 = 85.1


def signal_pulses() -> list[Pulse]:
    """The received signal (audio + interference). Slow, deep: the motif stretched x4.5."""
    cyc = BEACON_CYCLE * SIGNAL_STRETCH   # 9 s
    drop0, drop1, stop = _start("S08"), _start("S10"), _start("S13")
    def gain(t):
        if t < 3.0:
            return 0.55
        if drop0 <= t < drop1:            # debris + breath: the signal drops out
            return 0.0
        if t >= stop:
            return 0.0
        # grows through Act I-II
        return min(1.0, 0.55 + 0.45 * (t - 3.0) / max(drop0 - 3.0, 1.0))
    pulses = _motif_train(0.0, stop, cyc, SIGNAL_STRETCH, gain, "signal", phase=0.6, g=1.0 / SIGNAL_STRETCH)
    for off, long_ in MOTIF:
        pulses.append(Pulse(TITLE_MOTIF_T0 + off * SIGNAL_STRETCH, long_, SIGNAL_STRETCH, 0.8 if long_ else 0.55,
                            1.0 / SIGNAL_STRETCH, "signal"))
    return pulses


T_DILATE = _start("S14")   # time dilation becomes perceptible
T_FALL = _start("S15")
# The fall's last motif plays at exactly the signal's tempo (x4.5): three shorts from T_LAST_MOTIF, the
# long flash 3.6 s later, cut to black during it. The clock is steered to get there (docs/physics.md
# P21); the picture's colour, dimming and position stay physical (the tracer's worldline).
T_LAST_MOTIF = 78.3
G_SIGNAL = 1.0 / SIGNAL_STRETCH


def ship_rate(t: float) -> float:
    """dtau/dt of the ship's clock as the film's camera sees it: 1 until S14, easing down through S14
    and S15, held at 1/4.5 from just before the last motif to the cut."""
    if t <= T_DILATE:
        return 1.0
    t_hold = T_LAST_MOTIF - 0.4
    if t >= t_hold:
        return G_SIGNAL
    u = (t - T_DILATE) / (t_hold - T_DILATE)
    # log-linear from 1 to 1/4.5 with soft ends (smoothstep in log rate)
    w = u * u * (3 - 2 * u)
    return math.exp(math.log(G_SIGNAL) * w)


_CLOCK = None


def _clock_raw(t: float) -> float:
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


def ship_clock(t: float) -> float:
    """Ship proper time as the film's camera sees it (the beacon's clock), phased so a motif starts
    exactly at T_LAST_MOTIF."""
    return _clock_raw(t) + BEACON_PHASE


BEACON_PHASE = 0.0
BEACON_PHASE = (-_clock_raw(T_LAST_MOTIF)) % BEACON_CYCLE


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


def _cues() -> list[Cue]:
    S = _start
    return [
        Cue(0.0, "room_tone_in", {"dur": 3.0}),
        Cue(S("S01"), "drone_deep", {"until": S("S08")}),
        Cue(S("S02"), "hull_creak", {}),
        Cue(S("S03"), "dish_servo", {"dur": 2.4}),
        Cue(S("S04"), "lensing_swell", {"until": S("S06")}),
        Cue(S("S06") - 0.3, "reverse_swell", {"hit": S("S06")}),
        Cue(S("S06"), "low_hit", {"level": 0.6}),
        Cue(S("S07"), "shimmer", {"dur": S("S08") - S("S07")}),
        Cue(S("S08"), "debris_rumble", {"dur": S("S09") - S("S08")}),
        Cue(S("S09"), "near_silence", {"dur": S("S10") - S("S09")}),
        Cue(S("S10") - 0.3, "reverse_swell", {"hit": S("S10")}),
        Cue(S("S10"), "braam", {"level": 1.0, "tail": 7.0}),
        Cue(S("S10"), "sub_drop", {"level": 1.0}),
        Cue(S("S11"), "low_hit", {"level": 0.7}),
        Cue(S("S11"), "tension_pad", {"until": S("S15")}),
        Cue(S("S12"), "whoosh", {"level": 0.8}),
        Cue(S("S12") + 1.0, "shepard_riser", {"until": S("S15")}),
        Cue(S("S13"), "interference_burst", {"dur": S("S14") - S("S13")}),
        Cue(S("S14"), "time_stretch", {"dur": S("BLK1") - S("S14")}),
        Cue(S("BLK1"), "hard_cut_silence", {"dur": S("TITLE") - S("BLK1")}),
        Cue(S("TITLE"), "title_sting", {"level": 1.0, "tail": 4.1}),
        Cue(TITLE_MOTIF_T0 + MOTIF[-1][0] * SIGNAL_STRETCH, "last_signal", {}),
    ]


CUES: list[Cue] = _cues()
SILENCE = [(82.5, 84.5)]              # true digital zero


_SIGNAL = signal_pulses()
_BEACON = beacon_flashes()


def summary() -> str:
    lines = [f"{s.id:6s} {s.start:5.1f}-{s.end:5.1f} ({s.dur:4.1f}s, frames {s.f0}-{s.f1 - 1})  {s.title}" for s in SHOTS]
    lines.append(f"signal pulses: {len(_SIGNAL)}  beacon flashes: {len(_BEACON)}  cues: {len(CUES)}")
    return "\n".join(lines)


if __name__ == "__main__":
    print(summary())

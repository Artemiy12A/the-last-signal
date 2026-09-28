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


def ship_clock(t: float) -> float:
    """Ship proper time as seen by the film's camera (the beacon's clock).

    Normal until S14, then time dilation stretches it; S15's exact behaviour comes from the
    relativistic infall computed for that shot, this is the editorial approximation used for sound."""
    t_slow = 72.5
    if t <= t_slow:
        return t
    # dtau/dt falls exponentially (e-folding ~ 2.2 s of film time), freezing near 82.5
    k = 2.2
    return t_slow + k * (1.0 - math.exp(-(t - t_slow) / k))


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

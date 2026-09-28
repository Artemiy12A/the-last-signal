"""THE LAST SIGNAL - edit decision list.

Everything that happens in the trailer is defined here: shots, camera moves,
disk ignition, lighting, typography and the sound events. The audio synth reads
the same event list, so picture and sound stay locked.

Units: black hole at the origin, Schwarzschild radius = 1, disk in the xz plane.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable

import numpy as np

from .mathutil import (clamp, ease_in_cubic, ease_in_out, ease_in_out_cubic, ease_out_cubic,
                       ease_out_expo, lerp, look_at, norm, orbit, rot, shake, smoothstep, v3)

DURATION = 20.0

# ----------------------------------------------------------------- sound events
# The signal: (time, pitch multiplier, gain). The probe's beacon flashes on each.
PINGS: list[tuple[float, float, float]] = [
    (1.05, 1.00, 0.55), (2.25, 1.00, 0.6), (3.45, 1.00, 0.65),
    # something is wrong: the signal is being stretched (gravitational redshift)
    (5.55, 0.97, 0.7), (6.35, 0.93, 0.72), (7.05, 0.88, 0.75), (7.62, 0.84, 0.8), (8.02, 0.80, 0.85),
    # deep, slowed echoes inside the reveal
    (11.35, 0.50, 0.45), (13.05, 0.47, 0.45),
    # scale shot: the probe keeps calling back
    (14.55, 1.00, 0.5), (15.55, 1.00, 0.55), (16.35, 1.02, 0.6),
]
# signal peak: accelerating burst that ends at the hard cut
_t, _dt = 16.62, 0.16
while _t < 17.58:
    PINGS.append((round(_t, 3), 1.0 + (_t - 16.62) * 0.9, 0.55 + (_t - 16.62) * 0.4))
    _dt *= 0.84
    _t += max(_dt, 0.035)
# the last signal, alone, over the title
FINAL_PING = 19.05
PINGS.append((FINAL_PING, 1.0, 0.9))

HITS = {  # low impacts
    "card1": 4.00,
    "card2": 8.25,
    "reveal": 9.40,
    "scale": 14.10,
    "title": 18.10,
}
CUT_TO_BLACK = 17.60
TITLE_IN = 18.10


# ----------------------------------------------------------------- the sky
def _sky_rotation() -> np.ndarray:
    """World -> galactic texture frame.

    SKY_REF (the direction of the hole as seen in S2/S3) lands on the galactic
    plane at longitude SKY_LON, with the band tilted by SKY_TILT on screen, so
    the Milky Way passes right behind the hole and gets lensed into arcs."""
    e1 = norm(SKY_REF)
    e2 = norm(v3(0, 1, 0) - e1 * e1[1])
    e3 = np.cross(e1, e2)
    A = np.stack([e1, e2, e3])  # rows: SKY_REF -> tex +x (galactic centre), up -> galactic north
    return rot((0, 1, 0), math.radians(SKY_LON)) @ rot((1, 0, 0), math.radians(SKY_TILT)) @ A


SKY_REF = -orbit(34.0, 18.5, 2.4)
SKY_LON = -34.0
SKY_TILT = 24.0


def galactic_dir(lon_deg: float, lat_deg: float) -> np.ndarray:
    """World direction of a galactic (lon, lat) as used by the sky texture."""
    lo, la = math.radians(lon_deg), math.radians(lat_deg)
    d_tex = v3(math.cos(la) * math.cos(lo), math.sin(la), math.cos(la) * math.sin(lo))
    return SKY_ROT.T @ d_tex


SKY_ROT = _sky_rotation()


# ----------------------------------------------------------------- defaults
def base_params() -> dict:
    return dict(
        scene=True,
        bh=1.0, fov=34.0,
        cam_pos=v3(0, 2, -30), cam_rot=np.eye(3),
        disk_gain=1.0, disk_ignite=100.0, disk_temp=4800.0, doppler=0.8,
        disk_in=3.0, disk_out=14.5, glow=0.06, ring_boost=1.35,
        sky_rot=SKY_ROT, sky_gain=1.0, star_gain=0.55,
        ship=0.0, ship_pos=v3(0, 0, 0), ship_rot=np.eye(3), ship_scale=0.1,
        key_dir=v3(0, 0, 1), key_col=v3(0, 0, 0), fill_col=v3(0.004, 0.005, 0.007),
        rim_col=v3(0, 0, 0), beacon=0.0, engine=0.0,
        bloom_threshold=0.9, bloom_spread=1.0, bloom_gain=0.07,
        streak_threshold=2.5, streak_gain=0.08, streak_tint=v3(0.45, 0.65, 1.0),
        ca=0.025, vignette=0.45, grain=0.018, fade=1.0, flash=0.0, glitch=0.0,
        exposure=0.55, saturation=1.0, contrast=1.08,
        lift=v3(0.0, 0.0006, 0.0014), gain=v3(1.0, 0.99, 0.97),
        text=None, text_opacity=0.0, text_color=v3(0.93, 0.90, 0.85), text_glow=0.0,
        text_sweep=-1.0, text_flicker=0.0,
    )


def beacon_env(t: float) -> float:
    """Beacon light: sharp attack on every ping, fast decay."""
    v = 0.0
    for tp, _, g in PINGS:
        d = t - tp
        if -0.02 <= d < 0.6:
            v = max(v, (0.4 + g) * math.exp(-max(d, 0.0) / 0.09))
    return v


def ping_glitch(t: float) -> float:
    v = 0.0
    for tp, _, g in PINGS:
        d = t - tp
        if 0.0 <= d < 0.2:
            v = max(v, g * math.exp(-d / 0.05))
    return v


def ship_basis(pos, facing_target, roll=0.0) -> np.ndarray:
    """Probe basis: local -z (dish opening) points at facing_target."""
    back = norm(np.asarray(pos) - np.asarray(facing_target))
    up0 = v3(0, 1, 0)
    right = norm(np.cross(up0, back))
    up = np.cross(back, right)
    c, s = math.cos(roll), math.sin(roll)
    right, up = c * right + s * up, -s * right + c * up
    return np.stack([right, up, back], axis=1)


def apply_shake(cam_rot: np.ndarray, t: float, amp: float, freq=1.0, seed=0) -> np.ndarray:
    y, p, r = shake(t, amp, freq, seed)
    return cam_rot @ rot((0, 1, 0), y) @ rot((1, 0, 0), p) @ rot((0, 0, 1), r)


# ----------------------------------------------------------------- shots
@dataclass
class Shot:
    name: str
    start: float
    end: float
    fn: Callable[[dict, float, float], None]
    label: str = ""
    keyframes: list = field(default_factory=list)  # global times worth inspecting

    def u(self, t):
        return clamp((t - self.start) / (self.end - self.start))


def s_black(P, t, u):
    P["scene"] = False
    P["fade"] = 0.0


# S1 - the void. A lone probe drifts across the Milky Way, its beacon answering a faint signal.
def s1_void(P, t, u):
    P["bh"] = 0.0
    e = ease_in_out(u)
    fwd = norm(galactic_dir(lerp(-14.0, -11.0, e), 3.0))
    gal_up = SKY_ROT.T @ v3(0, 1, 0)
    cam = v3(0, 0, 0)
    cr = look_at(cam, cam + fwd, up=gal_up, roll=math.radians(-28.0))
    P["cam_pos"] = cam
    P["cam_rot"] = apply_shake(cr, t, 0.0005, 0.4, 3)
    P["fov"] = lerp(30.0, 28.5, e)
    f, r_, u_ = cr[:, 2], cr[:, 0], cr[:, 1]
    sp = cam + f * 17.0 + r_ * lerp(1.7, 2.6, u) - u_ * lerp(1.15, 1.02, u)
    P["ship"] = 1.0
    P["ship_pos"] = sp
    P["ship_rot"] = ship_basis(sp, sp + norm(r_ * 1.2 + f * 1.0 + u_ * 0.1) * 10.0, roll=0.5)
    P["ship_scale"] = 0.42
    P["key_dir"] = norm(r_ * 0.6 + u_ * 0.35 + f * 0.9)
    P["key_col"] = v3(0.55, 0.62, 0.8) * 0.9
    P["fill_col"] = v3(0.004, 0.005, 0.008)
    P["rim_col"] = v3(0.3, 0.36, 0.5) * 0.5
    P["beacon"] = beacon_env(t) * 1.6
    P["star_gain"] = 0.55
    P["sky_gain"] = 3.2
    P["exposure"] = 0.62
    P["fade"] = smoothstep(0.75, 2.6, t)
    P["grain"] = 0.022


def card(text: str, t0: float, t1: float):
    def fn(P, t, u):
        P["scene"] = False
        P["fade"] = 1.0
        P["text"] = ("card", text)
        a = smoothstep(t0 + 0.05, t0 + 0.45, t) * (1.0 - smoothstep(t1 - 0.3, t1 - 0.02, t))
        P["text_opacity"] = a
        P["text_glow"] = 0.6
        P["text_track"] = lerp(0.40, 0.46, (t - t0) / (t1 - t0))
        P["grain"] = 0.02
        P["lift"] = v3(0.0, 0.0, 0.0)
    return fn


# S2 - something is wrong. The Milky Way bends around nothing, behind the listening probe.
def s2_wrong(P, t, u):
    e = ease_in_out(u)
    cam = orbit(lerp(41.0, 38.5, e), lerp(15.0, 21.0, e), lerp(2.0, 2.8, e))
    to_bh = norm(-cam)
    right0 = norm(np.cross(v3(0, 1, 0), to_bh))
    right0 = -right0  # screen right
    fwd = norm(to_bh * math.cos(math.radians(11.0)) - right0 * math.sin(math.radians(11.0)))
    cr = look_at(cam, cam + fwd, roll=math.radians(lerp(3.0, 0.5, e)))
    P["cam_pos"] = cam
    P["cam_rot"] = apply_shake(cr, t, lerp(0.0006, 0.003, u * u), 0.8, 11)
    P["fov"] = lerp(30.0, 28.0, e)
    f, r_, u_ = cr[:, 2], cr[:, 0], cr[:, 1]
    sp = cam + f * 6.2 - r_ * lerp(1.72, 1.6, e) - u_ * 0.42
    P["ship"] = 1.0
    P["ship_pos"] = sp
    P["ship_rot"] = ship_basis(sp, v3(0, 0, 0), roll=lerp(0.42, 0.36, e))
    P["ship_scale"] = 0.42
    ember = smoothstep(7.2, 8.25, t)
    P["disk_gain"] = 0.004 + 0.03 * ember
    P["disk_temp"] = 2400.0
    P["glow"] = 0.0
    P["key_dir"] = norm(r_ * 0.8 + u_ * 0.3 + f * 1.0)
    P["key_col"] = v3(0.5, 0.56, 0.72) * 0.6
    P["fill_col"] = v3(0.006, 0.007, 0.011)
    P["rim_col"] = v3(0.3, 0.36, 0.5) * 0.6
    P["beacon"] = beacon_env(t) * 2.0
    P["star_gain"] = 0.6
    P["sky_gain"] = 4.0
    P["exposure"] = 0.8
    P["glitch"] = ping_glitch(t) * smoothstep(6.8, 8.1, t) * 0.3
    P["fade"] = smoothstep(5.25, 5.45, t)


# S3 - the reveal. The disk ignites from the innermost stable orbit outwards.
def s3_reveal(P, t, u):
    e = ease_in_out_cubic(u)
    dist = lerp(25.0, 21.5, e)
    cam = orbit(dist, lerp(6.0, -5.0, e), lerp(1.6, 8.5, e))
    cr = look_at(cam, v3(0, lerp(-0.3, 0.6, e), 0), roll=math.radians(lerp(-1.0, -4.5, e)))
    kick = math.exp(-max(t - 9.40, 0) / 0.3) * 0.0035
    P["cam_pos"] = cam
    P["cam_rot"] = apply_shake(cr, t, 0.0006 + kick, 1.2, 21)
    P["fov"] = lerp(31.0, 33.5, e)
    ig = ease_out_cubic(clamp((t - 9.40) / 2.1))
    P["disk_ignite"] = lerp(3.0, 22.0, ig)
    P["disk_gain"] = 1.0
    P["disk_temp"] = 4800.0
    P["exposure"] = lerp(0.66, 0.56, smoothstep(9.4, 11.8, t))
    P["glitch"] = ping_glitch(t) * 0.1
    P["star_gain"] = 0.55
    P["sky_gain"] = lerp(3.2, 2.2, smoothstep(9.4, 11.0, t))


# S4 - scale. Skimming over the disk: the lensed arch towers over a speck of a probe.
def s4_scale(P, t, u):
    e = ease_in_out(u)
    cam = orbit(lerp(12.8, 12.0, e), lerp(-22.0, -18.0, e), lerp(5.2, 4.6, e))
    cr = look_at(cam, v3(0, lerp(1.25, 1.05, e), 0), roll=math.radians(lerp(5.0, 3.5, e)))
    P["cam_pos"] = cam
    P["cam_rot"] = apply_shake(cr, t, 0.0008, 0.7, 31)
    P["fov"] = lerp(58.0, 56.0, e)
    f, r_, u_ = cr[:, 2], cr[:, 0], cr[:, 1]
    sp = cam + f * lerp(3.0, 3.35, e) - r_ * lerp(0.62, 0.55, e) + u_ * lerp(0.36, 0.38, e)
    P["ship"] = 1.0
    P["ship_pos"] = sp
    P["ship_rot"] = ship_basis(sp, v3(0, 0, 0), roll=0.25)
    P["ship_scale"] = 0.05
    P["key_dir"] = norm(-sp)
    P["key_col"] = v3(1.0, 0.62, 0.3) * 1.6
    P["fill_col"] = v3(0.01, 0.009, 0.008)
    P["rim_col"] = v3(1.0, 0.62, 0.32) * 1.5
    P["beacon"] = beacon_env(t) * 1.4
    P["engine"] = 1.0
    P["exposure"] = 0.5
    P["sky_gain"] = 2.2
    P["glitch"] = ping_glitch(t) * 0.1


# S5a - the signal peaks: pushing into the photon ring
def s5a_ring(P, t, u):
    e = ease_in_cubic(u)
    cam = orbit(lerp(15.0, 12.5, e), 8.0, 3.2)
    tgt = v3(2.35, 0.95, 0.0)
    cr = look_at(cam, tgt, roll=math.radians(lerp(-8.0, -12.0, e)))
    P["cam_pos"] = cam
    P["cam_rot"] = apply_shake(cr, t, 0.004 + 0.006 * e, 2.5, 41)
    P["fov"] = lerp(15.0, 11.5, e)
    P["disk_gain"] = lerp(1.1, 1.6, e)
    P["exposure"] = lerp(0.55, 0.7, e)
    P["glitch"] = 0.12 + 0.3 * e + ping_glitch(t) * 0.4
    P["ring_boost"] = 1.8


# S5b - the probe, overwhelmed; white-out into the cut
def s5b_probe(P, t, u):
    e = ease_in_cubic(u)
    cam = orbit(19.5, -12.0, 2.4)
    cr = look_at(cam, v3(0.0, 0.2, 0.0), roll=math.radians(3.0))
    f, r_, u_ = cr[:, 2], cr[:, 0], cr[:, 1]
    P["cam_pos"] = cam
    P["cam_rot"] = apply_shake(cr, t, 0.005 + 0.01 * e, 3.0, 51)
    P["fov"] = lerp(24.0, 21.0, e)
    sp = cam + f * lerp(2.3, 2.05, e) - r_ * 0.1 - u_ * 0.1
    P["ship"] = 1.0
    P["ship_pos"] = sp
    P["ship_rot"] = ship_basis(sp, v3(0, 0, 0), roll=0.5)
    P["ship_scale"] = 0.1
    P["key_dir"] = norm(-sp)
    P["key_col"] = v3(1.0, 0.6, 0.3) * 3.0
    P["rim_col"] = v3(1.0, 0.65, 0.35) * 1.4
    P["fill_col"] = v3(0.012, 0.01, 0.009)
    P["beacon"] = beacon_env(t) * 2.0
    P["engine"] = 1.0
    P["disk_gain"] = lerp(1.4, 2.6, e)
    P["exposure"] = lerp(0.62, 1.6, e)
    P["flash"] = 2.5 * smoothstep(17.36, 17.585, t) ** 2
    P["glitch"] = 0.35 + 0.55 * e + ping_glitch(t) * 0.5


# TITLE - silence, then the name, over the faint silhouette of the hole
def s_title(P, t, u):
    e = ease_in_out(u)
    cam = orbit(lerp(46.0, 44.0, e), lerp(-2.0, 2.0, e), 1.6)
    cr = look_at(cam, v3(0, 0.05, 0), roll=0.0)
    P["cam_pos"] = cam
    P["cam_rot"] = cr
    P["fov"] = 21.0
    glow = smoothstep(18.25, 19.3, t)
    pulse = math.exp(-max(t - FINAL_PING, 0.0) / 0.35) if t >= FINAL_PING else 0.0
    P["disk_gain"] = 0.05 * glow + 0.14 * pulse
    P["ring_boost"] = 2.5
    P["disk_temp"] = 4300.0
    P["doppler"] = 0.6
    P["glow"] = 0.0
    P["disk_time"] = 40.0 + t * 2.6
    P["star_gain"] = 0.35 * glow
    P["sky_gain"] = 1.2 * glow
    P["exposure"] = 0.6
    P["vignette"] = 0.6
    P["bloom_gain"] = 0.09
    P["text"] = ("title", "THE LAST SIGNAL")
    P["text_opacity"] = smoothstep(18.22, 18.95, t)
    P["text_glow"] = 0.45 + 0.8 * pulse
    P["text_track"] = lerp(0.52, 0.60, ease_out_cubic(u))
    P["text_sweep"] = lerp(-0.15, 1.2, clamp((t - 18.45) / 1.1)) if 18.45 <= t <= 19.55 else -1.0
    P["text_flicker"] = 0.85 if FINAL_PING <= t < FINAL_PING + 0.09 else 0.0
    P["fade"] = 1.0 - smoothstep(19.45, 19.96, t)


SHOTS: list[Shot] = [
    Shot("black_open", 0.00, 0.75, s_black, "black"),
    Shot("s1_void", 0.75, 4.00, s1_void, "S1  the void", [1.1, 2.3, 3.5]),
    Shot("card1", 4.00, 5.25, card("ONE SIGNAL", 4.00, 5.25), "card", [4.6]),
    Shot("s2_wrong", 5.25, 8.25, s2_wrong, "S2  something is wrong", [5.6, 7.0, 8.05]),
    Shot("card2", 8.25, 9.40, card("FROM WHERE NOTHING ESCAPES", 8.25, 9.40), "card", [8.8]),
    Shot("s3_reveal", 9.40, 14.10, s3_reveal, "S3  the reveal", [9.5, 9.9, 10.5, 11.5, 12.8, 14.0]),
    Shot("s4_scale", 14.10, 16.70, s4_scale, "S4  scale", [14.3, 15.5, 16.6]),
    Shot("s5a_ring", 16.70, 17.12, s5a_ring, "S5  signal peaks", [16.9]),
    Shot("s5b_probe", 17.12, CUT_TO_BLACK, s5b_probe, "S5  white-out", [17.3, 17.5]),
    Shot("black_cut", CUT_TO_BLACK, TITLE_IN, s_black, "black"),
    Shot("title", TITLE_IN, DURATION, s_title, "TITLE", [18.6, 19.1, 19.4]),
]


def shot_at(t: float) -> Shot:
    for s in SHOTS:
        if s.start <= t < s.end:
            return s
    return SHOTS[-1]


def params_at(t: float, frame: int = 0) -> dict:
    P = base_params()
    s = shot_at(t)
    s.fn(P, t, s.u(t))
    P["t"] = t
    P["frame"] = frame
    P["shot"] = s.name
    # continuous disk rotation across all shots (time-lapsed orbital motion)
    P["disk_time"] = 40.0 + t * 2.6
    return P


def keyframe_times() -> list[tuple[float, str]]:
    out = []
    for s in SHOTS:
        for k in s.keyframes:
            out.append((k, s.label))
    return out

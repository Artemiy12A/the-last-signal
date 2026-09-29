"""Render THE LAST SIGNAL soundtrack from the EDL.

    python production/audio/fetch_audio.py        # once: the three real recordings (optional)
    python production/audio/make_soundtrack.py    # -> production/cache/audio/soundtrack.wav + stems/
    python production/audio/analyze.py            # -> production/audio/review/*.png + report.txt

Output: 48 kHz / 24-bit / stereo / exactly edl.DURATION seconds, -14 LUFS integrated, <= -1 dBTP,
true digital zero over edl.SILENCE. Every time comes from production/tls/edl.py.
Options: --no-recordings (pure synthesis), --out DIR.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import soundfile as sf

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import dsp  # noqa: E402
import elements  # noqa: E402
import loudness  # noqa: E402
from dsp import SR, db, n_of  # noqa: E402
from motif import edl  # noqa: E402

STEMS = ("drones", "signal", "beacon", "interference", "fx", "music")
WARP_STEMS = ("drones", "signal", "interference", "fx", "music")   # the beacon carries its own stretch
TARGET_LUFS = -14.0
CEILING_DBTP = -1.3
DEFAULT_OUT = HERE.parent / "cache" / "audio"
SRC_DIR = DEFAULT_OUT / "src"


class Mix:
    """Stem buses on the film timeline. Three layers per stem:
    dry  -- film-time content before the hard cut (warped by the time-stretch),
    post -- content designed already slowed (not warped), before the hard cut,
    end  -- content that starts after the silence (title sting, the last pulse)."""

    def __init__(self, use_recordings: bool = True):
        self.N = n_of(edl.DURATION)
        self.silence = edl.SILENCE[0] if edl.SILENCE else (edl.DURATION, edl.DURATION)
        self.layers = {k: {s: None for s in STEMS} for k in ("dry", "post", "end")}
        self.sends: dict = {}
        self.ducks: list = []
        self.dips: list = []
        self.dropouts: list = []
        self.events: list = []
        self.hits: list = []
        self.tail_ends: list = []
        self.warp = None
        self.use_recordings = use_recordings
        self._recs: dict = {}
        self.ir = {
            "void": dsp.make_ir(8.0, 2.5, predelay=0.045, n_er=10, er_span=0.09, seed="void"),
            "hall": dsp.make_ir(6.0, 2.0, predelay=0.03, n_er=12, er_span=0.07, seed="hall"),
            "hull": dsp.make_ir(0.8, 0.25, predelay=0.004, n_er=8, er_span=0.02, seed="hull", length=1.0),
        }

    # -------------------------------------------------------------------------- building
    def _buf(self, layer: str, stem: str) -> np.ndarray:
        if self.layers[layer][stem] is None:
            self.layers[layer][stem] = np.zeros((self.N, 2))
        return self.layers[layer][stem]

    def add(self, stem, sig, t0, gain=1.0, p=0.0, sends=None, post=False):
        layer = "end" if t0 >= self.silence[1] - 1e-9 else ("post" if post else "dry")
        dsp.place(self._buf(layer, stem), sig, t0, gain, p)
        for name, amt in (sends or {}).items():
            if amt <= 0:
                continue
            key = (stem, name, layer)
            if key not in self.sends:
                self.sends[key] = np.zeros((self.N, 2))
            dsp.place(self.sends[key], sig, t0, gain * amt, p)

    def recording(self, name: str):
        if not self.use_recordings:
            return None
        if name not in self._recs:
            path = SRC_DIR / f"{name}.wav"
            if not path.exists():
                print(f"  (recording {name} missing: run fetch_audio.py; layer skipped)")
                self._recs[name] = None
            else:
                x, sr = sf.read(path, always_2d=False)
                self._recs[name] = dsp.resample_to(x.astype(np.float64), sr)   # always 48 kHz
        return self._recs[name]

    def event(self, t, kind, **kw):
        self.events.append({"t": round(float(t), 4), "kind": kind, **kw})

    def duck_at(self, t, depth_db, release):
        self.ducks.append((t, depth_db, release))

    def dip(self, t0, t1, gain_db, stems):
        self.dips.append((t0, t1, gain_db, stems))

    def dropout(self, t, dur):
        self.dropouts.append((t, dur))

    def tail_end(self, t):
        self.tail_ends.append(t)

    # ------------------------------------------------------------------------- finishing
    def reverb_returns(self) -> None:
        for (stem, name, layer), buf in self.sends.items():
            nz = np.flatnonzero(np.abs(buf).max(axis=1) > 0)
            if len(nz) == 0:
                continue
            i0, i1 = nz[0], nz[-1] + 1
            wet = dsp.convolve(buf[i0:i1], self.ir[name])
            wet = dsp.hp(wet, 90.0 if name != "hull" else 150.0, order=2)
            out = self._buf(layer, stem)
            j1 = min(self.N, i0 + len(wet))
            out[i0:j1] += wet[: j1 - i0]
        self.sends.clear()

    def warp_curve(self):
        """Source positions (samples) for the time-stretch region: rate = (dtau/dt)^beta."""
        t0, t1 = self.warp
        i0, i1 = n_of(t0), n_of(t1)
        ts = np.linspace(t0, t1, 2001)
        rate = np.array([elements.ship_rate(t) for t in ts]) ** elements.WARP_BETA
        r = np.interp((np.arange(i0, i1) + 0.5) / SR, ts, rate)
        return i0, i1, i0 + np.cumsum(r) - r[0]

    def apply_warp(self) -> None:
        if not self.warp:
            return
        i0, i1, pos = self.warp_curve()
        for stem in WARP_STEMS:
            buf = self.layers["dry"][stem]
            if buf is None:
                continue
            seg = dsp.varispeed(buf, pos)
            if getattr(self, "warp_gain", None):
                wg = self.warp_gain
                g = db(np.interp(np.arange(i0, i1) / SR, [a for a, _ in wg], [b for _, b in wg]))
                seg = seg * g[:, None]
            buf[i0:i1] = seg
            buf[i1:] = 0.0
        self.event(self.warp[0], "time_stretch_start", end_rate=round(float(np.diff(pos[-2:])[0]), 4))

    def gain_curves(self) -> dict:
        """Per-stem gain: sidechain ducking under hits, dips (near-silence), digital dropouts."""
        n = self.N
        t = np.arange(n) / SR
        duck_db = np.zeros(n)
        for th, depth, rel in self.ducks:
            i = n_of(th - 0.01)
            m = n_of(rel * 5)
            tl = np.arange(m) / SR
            shape = np.minimum(1.0, tl / 0.01) * np.exp(-np.maximum(tl - 0.12, 0) / rel)
            j = min(n, i + m)
            duck_db[i:j] = np.minimum(duck_db[i:j], -depth * shape[: j - i])
        curves = {s: np.ones(n) for s in STEMS}
        for s in ("drones", "interference"):
            curves[s] *= 10 ** (duck_db / 20)
        curves["music"] *= 10 ** (0.4 * duck_db / 20)
        for t0, t1, g_db, stems in self.dips:
            w = dsp.smoothstep((t - t0) / 0.03) * (1 - dsp.smoothstep((t - t1 + 0.25) / 0.25))
            for s in stems:
                curves[s] *= 1.0 - (1.0 - db(g_db)) * w
        if self.dropouts:
            gate = np.ones(n)
            for td, d in self.dropouts:
                i, m = n_of(td), n_of(d)
                gate[i:i + m] = 0.0
            gate = dsp.lp(gate, 600.0, order=1, zero_phase=True)
            for s in ("signal", "interference", "music", "drones", "beacon"):
                curves[s] *= gate
        return curves

    def stems(self) -> dict:
        """Final per-stem buffers with the hard cut, the silence and the end fade applied."""
        s0, s1 = n_of(self.silence[0]), n_of(self.silence[1])
        cut = np.ones(self.N)
        k = n_of(0.003)                                     # 3 ms: a hard cut without a click
        cut[s0 - k:s0] = dsp.fade(k, 0, k)
        cut[s0:] = 0.0
        end_w = np.ones(self.N)
        end_w[:s1] = 0.0
        final = np.ones(self.N)                             # the last pulse fades into the end
        fe0, fe1 = n_of(edl.DURATION - 0.45), n_of(edl.DURATION - 0.015)
        final[fe0:fe1] = np.cos(0.5 * np.pi * np.arange(fe1 - fe0) / (fe1 - fe0)) ** 2
        final[fe1:] = 0.0
        title_w = np.ones(self.N)                           # the sting is gone before the last pulse
        for te in self.tail_ends:
            a, b = n_of(te - 1.4), n_of(te)
            title_w[a:b] = np.cos(0.5 * np.pi * np.arange(b - a) / (b - a)) ** 2
            title_w[b:] = 0.0
        gains = self.gain_curves()
        out = {}
        for s in STEMS:
            pre = np.zeros((self.N, 2))
            for layer in ("dry", "post"):
                if self.layers[layer][s] is not None:
                    pre += self.layers[layer][s]
            pre *= (cut * gains[s])[:, None]
            end = self.layers["end"][s]
            end = np.zeros((self.N, 2)) if end is None else end * end_w[:, None]
            if s in ("fx", "music"):
                end *= title_w[:, None]
            out[s] = (pre + end) * final[:, None]
        return out


# ================================================================================ master
def phone_harmonics(x: np.ndarray) -> np.ndarray:
    """Parallel harmonic generation of the sub band into 150-1000 Hz (research_sota.md §3.4)."""
    sub = dsp.lp(dsp.mono(x), 120.0, order=4)
    env = dsp.env_follow(sub, 0.03) * np.sqrt(2.0)
    u = np.clip(sub / np.maximum(env, 1e-5), -1.0, 1.0)
    T = [None, u, 2 * u ** 2 - 1]
    for k in range(3, 9):
        T.append(2 * u * T[-1] - T[-2])
    wts = {2: 0.5, 3: 0.35, 4: 0.22, 5: 0.14, 6: 0.09, 7: 0.06, 8: 0.04}
    h = sum(w * T[k] for k, w in wts.items()) * env
    h = dsp.bp(h, 150.0, 1000.0, order=3)
    return np.stack([h, h], axis=1)


def master_segment(x: np.ndarray, gain_db: float) -> tuple[np.ndarray, dict]:
    y = x * db(gain_db)
    y = y + phone_harmonics(y) * db(-6.0)
    y, gr = dsp.compressor(y, thresh_db=-15.0, ratio=1.6, attack=0.03, release=0.35, knee_db=10.0,
                             sc_hp=120.0)
    y, lg = dsp.limiter(y, ceiling_db=CEILING_DBTP, lookahead=0.004, release=0.12)
    return y, {"comp_max_gr_db": float(-gr.min()), "lim_max_gr_db": float(-dsp.to_db(lg.min())),
               "_comp_db": gr, "_lim_db": dsp.to_db(lg)}


def master(mix_sum: np.ndarray, silence) -> tuple[np.ndarray, float, dict]:
    """Normalise to TARGET_LUFS integrated with the limiter in the loop. The two sides of the
    silence are processed separately so no filter, compressor or limiter smears into it."""
    N = len(mix_sum)
    s0, s1 = n_of(silence[0]), n_of(silence[1])
    segs = [(0, s0), (s1, N)] if s1 > s0 else [(0, N)]
    g = TARGET_LUFS - loudness.integrated(mix_sum)
    info = {}
    for it in range(6):
        out = np.zeros_like(mix_sum)
        info = {}
        comp_db, lim_db = np.zeros(N), np.zeros(N)
        for a, b in segs:
            y, inf = master_segment(mix_sum[a:b], g)
            out[a:b] = y
            comp_db[a:b], lim_db[a:b] = inf.pop("_comp_db"), inf.pop("_lim_db")
            for k, v in inf.items():
                info[k] = max(info.get(k, 0.0), v)
        lu = loudness.integrated(out)
        if abs(lu - TARGET_LUFS) < 0.05:
            break
        g += TARGET_LUFS - lu
    out[s0:s1] = 0.0
    info["iterations"] = it + 1
    # gain-reduction traces at 20 Hz (min over each 50 ms) for the review plots
    h = SR // 20
    k = N // h
    info["_gr"] = {"rate": 20, "comp_db": np.round(comp_db[: k * h].reshape(k, h).min(1), 2).tolist(),
                   "lim_db": np.round(lim_db[: k * h].reshape(k, h).min(1), 2).tolist()}
    return out, g, info


def write_wav(path: Path, x: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), np.clip(x, -1.0, 1.0 - 2 ** -23), SR, subtype="PCM_24")


def render(out_dir: Path, use_recordings: bool = True) -> dict:
    t_start = time.time()
    mix = Mix(use_recordings)
    print(edl.summary().splitlines()[-1])
    handled = set()
    for cue in edl.CUES:
        fn = elements.HANDLERS.get(cue.kind)
        if fn is None:
            print(f"  WARNING: no handler for cue {cue.kind} at {cue.t}")
            continue
        fn(mix, cue)
        handled.add(cue.kind)
        mix.event(cue.t, cue.kind, **{k: v for k, v in cue.params.items()})
    if "room_tone_in" not in handled:
        elements.room_tone(mix, 0.0, 3.0)
    elements.signal_layer(mix)
    elements.beacon_layer(mix)
    elements.interference_layer(mix)
    print(f"  elements rendered in {time.time() - t_start:.1f}s")
    mix.reverb_returns()
    mix.apply_warp()
    stems = mix.stems()
    total = sum(stems.values())
    print(f"  stems + reverb + warp in {time.time() - t_start:.1f}s")
    out, g_db, info = master(total, mix.silence)
    # exactness checks
    s0, s1 = n_of(mix.silence[0]), n_of(mix.silence[1])
    assert len(out) == n_of(edl.DURATION)
    assert not np.any(out[s0:s1]), "silence is not digital zero"
    out_dir.mkdir(parents=True, exist_ok=True)
    write_wav(out_dir / "soundtrack.wav", out)
    # stems: the pre-master mix at the master gain (they sum to the mix before harmonics/comp/limiter)
    stem_scale = 1.0
    pk = max(np.abs(s).max() for s in stems.values()) * db(g_db)
    if pk > 0.98:
        stem_scale = 0.98 / pk
    for s, buf in stems.items():
        write_wav(out_dir / "stems" / f"{s}.wav", buf * db(g_db) * stem_scale)
    meta = {
        "duration_s": len(out) / SR, "sample_rate": SR, "bits": 24,
        "integrated_lufs": round(loudness.integrated(out), 2),
        "true_peak_dbtp": round(dsp.true_peak_db(out), 2),
        "lra_lu": round(loudness.lra(out), 2),
        "master_gain_db": round(g_db, 2), "stem_scale": round(stem_scale, 4),
        **{k: round(v, 2) for k, v in info.items() if not k.startswith("_")},
        "silence": list(mix.silence), "render_seconds": round(time.time() - t_start, 1),
        "recordings": use_recordings,
    }
    (out_dir / "render_meta.json").write_text(json.dumps(meta, indent=2))
    (out_dir / "master_gr.json").write_text(json.dumps(info["_gr"]))
    (out_dir / "cuesheet.json").write_text(json.dumps(sorted(mix.events, key=lambda e: e["t"]), indent=1))
    print(json.dumps(meta, indent=2))
    return meta


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--no-recordings", action="store_true")
    a = ap.parse_args()
    render(a.out, not a.no_recordings)


if __name__ == "__main__":
    main()

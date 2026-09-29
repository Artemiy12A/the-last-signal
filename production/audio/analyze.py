"""Analyse the rendered soundtrack against the EDL.

    python production/audio/analyze.py [--wav production/cache/audio/soundtrack.wav]

Writes production/audio/review/{spectrogram,loudness,sub_energy,stems}.png and report.txt:
log-frequency spectrogram with shot boundaries / cues / pulses, momentary + short-term LUFS,
20-80 Hz energy, per-stem levels, and a text report (integrated LUFS, true peak, LRA, silence
check, end check, per-shot levels, hit / pulse alignment against the EDL).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402
from scipy import signal as sps  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import dsp  # noqa: E402
import loudness  # noqa: E402
from dsp import SR, n_of  # noqa: E402
from motif import edl  # noqa: E402
import elements  # noqa: E402

FLASHES, MEASURED = elements.beacon_flashes()   # EDL flashes, S15 from the tracer light curve if present

CACHE = HERE.parent / "cache" / "audio"
REVIEW = HERE / "review"
STEM_NAMES = ("drones", "signal", "beacon", "interference", "fx", "music")
HIT_KINDS = ("low_hit", "braam", "title_sting")

BG, FG, GRID = "#101114", "#d8d8d8", "#3a3d44"
C_SHOT, C_CUE, C_SIG, C_BCN = "#9aa0aa", "#f0b44c", "#5cc8e6", "#e87070"


def style(ax):
    ax.set_facecolor(BG)
    for s in ax.spines.values():
        s.set_color(GRID)
    ax.tick_params(colors=FG, labelsize=8)
    ax.xaxis.label.set_color(FG)
    ax.yaxis.label.set_color(FG)
    ax.title.set_color(FG)


def shot_lines(ax, labels=True, y_text=None):
    for s in edl.SHOTS:
        ax.axvline(s.start, color=C_SHOT, lw=0.7, ls="--", alpha=0.7)
        if labels:
            yt = y_text if y_text is not None else ax.get_ylim()[1]
            ax.text(s.start + 0.1, yt, s.id, color=C_SHOT, fontsize=7, va="top", ha="left")
    for a, b in edl.SILENCE:
        ax.axvspan(a, b, color="#ffffff", alpha=0.06)


def cue_marks(ax, y, labels=True):
    for i, c in enumerate(edl.CUES):
        ax.plot([c.t], [y], marker="v", color=C_CUE, ms=5, zorder=5)
        if labels:
            ax.text(c.t, y, " " + c.kind, color=C_CUE, fontsize=6.5, rotation=90, va="top", ha="center",
                    zorder=5, alpha=0.9)


def fig_spectrogram(x, path):
    m = dsp.mono(x)
    nper, hop = 8192, 1200
    f, t, Z = sps.stft(m, SR, window="hann", nperseg=nper, noverlap=nper - hop, boundary=None, padded=False)
    P = np.abs(Z) ** 2
    t = t
    fl = np.geomspace(20, 20000, 320)
    Pl = np.stack([np.interp(fl, f, P[:, k]) for k in range(P.shape[1])], axis=1)
    L = 10 * np.log10(Pl + 1e-20)
    top = np.percentile(L, 99.8)
    fig, ax = plt.subplots(figsize=(24, 8.5), facecolor=BG)
    style(ax)
    ax.pcolormesh(t, fl, L, shading="auto", cmap="magma", vmin=top - 95, vmax=top)
    ax.set_yscale("log")
    ax.set_ylim(20, 20000)
    ax.set_xlim(0, edl.DURATION)
    ax.set_xticks(np.arange(0, edl.DURATION + 0.1, 2.5))
    ax.set_yticks([20, 40, 80, 150, 300, 600, 1000, 2000, 4000, 8000, 16000])
    ax.set_yticklabels(["20", "40", "80", "150", "300", "600", "1k", "2k", "4k", "8k", "16k"])
    ax.set_xlabel("film time (s)")
    ax.set_ylabel("Hz")
    ax.set_title("THE LAST SIGNAL — soundtrack spectrogram (mid, log f, 95 dB range) · shots, cues (▼), "
                 "signal pulses (cyan) and beacon flashes (red) from edl.py")
    shot_lines(ax, y_text=19000)
    cue_marks(ax, 3000)
    for p in edl.signal_pulses():
        ax.plot([p.t, p.t], [11000, 14500 if p.long else 12500], color=C_SIG, lw=1.4)
    for p in FLASHES:
        ax.plot([p.t, p.t], [22, 26 if p.long else 24], color=C_BCN, lw=0.8)
    fig.tight_layout()
    fig.savefig(path, dpi=85, facecolor=BG)
    plt.close(fig)


def fig_loudness(x, path, integ, tp, lra_v):
    tm, lm = loudness.momentary(x)
    ts, ls = loudness.short_term(x)
    phone = dsp.hp(x, 300.0, order=4)
    tp_, lp_ = loudness.short_term(phone)
    fig, ax = plt.subplots(figsize=(24, 6.5), facecolor=BG)
    style(ax)
    ax.plot(tm, lm, color="#6f7b8f", lw=0.7, label="momentary (400 ms)")
    ax.plot(ts, ls, color="#f3d27a", lw=1.8, label="short-term (3 s)")
    ax.plot(tp_, lp_, color="#7ad3a0", lw=1.0, ls=":", label="short-term, phone sim (HP 300 Hz)")
    for yv, lab, c in ((-14, "−14 target (integrated)", "#ffffff"), (-9, "−9 short-term peak target", "#ff8a65"),
                       (-30, "−30 quiet floor", "#7aa7ff")):
        ax.axhline(yv, color=c, lw=0.8, ls="--", alpha=0.6)
        ax.text(0.3, yv + 0.4, lab, color=c, fontsize=7.5, alpha=0.8)
    ax.set_ylim(-60, -2)
    ax.set_xlim(0, edl.DURATION)
    ax.set_xticks(np.arange(0, edl.DURATION + 0.1, 2.5))
    ax.set_xlabel("film time (s)")
    ax.set_ylabel("LUFS")
    ax.set_title(f"Loudness (BS.1770): integrated {integ:.2f} LUFS · true peak {tp:.2f} dBTP · LRA {lra_v:.1f} LU")
    shot_lines(ax, y_text=-2.5)
    cue_marks(ax, -44)
    grp = CACHE / "master_gr.json"
    if grp.exists():
        gr = json.loads(grp.read_text())
        tg = (np.arange(len(gr["lim_db"])) + 0.5) / gr["rate"]
        ax2 = ax.twinx()
        style(ax2)
        ax2.plot(tg, gr["comp_db"], color="#b388ff", lw=0.8, alpha=0.8, label="bus comp GR (dB)")
        ax2.plot(tg, gr["lim_db"], color="#ff5252", lw=0.8, alpha=0.8, label="limiter GR (dB)")
        ax2.set_ylim(-40, 0)
        ax2.set_ylabel("gain reduction dB (right)")
        ax2.legend(loc="lower center", facecolor=BG, edgecolor=GRID, labelcolor=FG, fontsize=8)
    ax.legend(loc="lower right", facecolor=BG, edgecolor=GRID, labelcolor=FG, fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=85, facecolor=BG)
    plt.close(fig)


def band_energy(x, lo, hi, win=0.25, hop=0.05):
    y = dsp.bp(dsp.mono(x), lo, hi, order=4)
    p = y * y
    cs = np.concatenate([[0], np.cumsum(p)])
    w, h = n_of(win), n_of(hop)
    ends = np.arange(w, len(p) + 1, h)
    e = (cs[ends] - cs[ends - w]) / w
    return (ends - w / 2) / SR, 10 * np.log10(e + 1e-20)


def fig_sub(x, path):
    t, e = band_energy(x, 20, 80)
    t2, e2 = band_energy(x, 150, 1000)
    fig, ax = plt.subplots(figsize=(24, 5.5), facecolor=BG)
    style(ax)
    ax.fill_between(t, -90, e, color="#c0392b", alpha=0.35)
    ax.plot(t, e, color="#ff6b5b", lw=1.2, label="20–80 Hz energy (dBFS rms, 250 ms)")
    ax.plot(t2, e2, color="#7ad3a0", lw=0.8, alpha=0.8, label="150–1000 Hz (where phone speakers hear the sub's harmonics)")
    ax.set_ylim(-80, -5)
    ax.set_xlim(0, edl.DURATION)
    ax.set_xticks(np.arange(0, edl.DURATION + 0.1, 2.5))
    ax.set_xlabel("film time (s)")
    ax.set_ylabel("dBFS")
    ax.set_title("Sub-bass arc: 20–80 Hz energy vs time")
    shot_lines(ax, y_text=-6)
    cue_marks(ax, -66)
    ax.legend(loc="lower left", facecolor=BG, edgecolor=GRID, labelcolor=FG, fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=85, facecolor=BG)
    plt.close(fig)


def fig_stems(stems, path):
    cols = {"drones": "#8e7cc3", "signal": "#5cc8e6", "beacon": "#e87070", "interference": "#b0b0b0",
            "fx": "#f0b44c", "music": "#7ad3a0"}
    fig, ax = plt.subplots(figsize=(24, 5.5), facecolor=BG)
    style(ax)
    for name, s in stems.items():
        t, lv = loudness.momentary(s)
        ax.plot(t, lv, color=cols.get(name, FG), lw=1.0, label=name)
    ax.set_ylim(-70, -5)
    ax.set_xlim(0, edl.DURATION)
    ax.set_xticks(np.arange(0, edl.DURATION + 0.1, 2.5))
    ax.set_xlabel("film time (s)")
    ax.set_ylabel("LUFS (momentary, pre-master stems at master gain)")
    ax.set_title("Stems")
    shot_lines(ax, y_text=-6)
    ax.legend(loc="lower left", facecolor=BG, edgecolor=GRID, labelcolor=FG, fontsize=8, ncol=6)
    fig.tight_layout()
    fig.savefig(path, dpi=85, facecolor=BG)
    plt.close(fig)


def fig_motif(x, stems, path):
    """Zoomed views: the received motif, the beacon's morph into the signal, the last pulse."""
    views = [("signal stem: one motif (3 short + 1 long, x4.5)", stems.get("signal", x), 18.3, 24.8),
             ("beacon stem: the ship's tick slows and sinks into the signal (S14-S15; red = flashes, xN = stretch)", stems.get("beacon", x), 68.5, 82.5),
             ("mix: the title restates the motif; the last long pulse alone into 90.0", x, 84.4, 90.0)]
    fig, axes = plt.subplots(1, 3, figsize=(24, 6), facecolor=BG, gridspec_kw={"width_ratios": [6.5, 14, 5.6]})
    for ax, (title, sig, a, b) in zip(axes, views):
        style(ax)
        m = dsp.mono(sig[n_of(a):n_of(b)])
        f, t, Z = sps.stft(m, SR, nperseg=4096, noverlap=4096 - 480)
        P = 10 * np.log10(np.abs(Z) ** 2 + 1e-20)
        top = np.percentile(P, 99.9)
        ax.pcolormesh(t + a, f, P, shading="auto", cmap="magma", vmin=top - 80, vmax=top)
        ax.set_yscale("log")
        ax.set_ylim(25, 12000)
        ax.set_title(title, fontsize=9)
        ax.set_xlabel("film time (s)")
        for p in edl.signal_pulses():
            if a <= p.t <= b:
                ax.axvline(p.t, color=C_SIG, lw=0.8, alpha=0.8)
        for p in FLASHES:
            if a <= p.t <= b:
                ax.axvline(p.t, color=C_BCN, lw=0.6, alpha=0.6)
                if p.stretch > 1.05:
                    ax.text(p.t, 9000, f" x{p.stretch:.1f}", color=C_BCN, fontsize=7)
        for s_ in edl.SHOTS:
            if a < s_.start < b:
                ax.axvline(s_.start, color=C_SHOT, lw=0.8, ls="--")
                ax.text(s_.start, 30, s_.id, color=C_SHOT, fontsize=7)
    fig.tight_layout()
    fig.savefig(path, dpi=85, facecolor=BG)
    plt.close(fig)


def onset_near(x, t, pre=0.06, post=0.15, frac=0.3):
    """Onset of the event at EDL time t: first sample in [t-15 ms, t+post] whose 1 ms envelope
    rises above baseline + frac x (peak - baseline), baseline = the envelope's max over
    [t-pre, t-15 ms] (so decaying tails of earlier events never count as early onsets)."""
    a, b = n_of(max(t - pre, 0)), n_of(min(t + post, edl.DURATION))
    seg = np.abs(dsp.mono(x[a:b]))
    env = np.convolve(seg, np.ones(48) / 48, mode="same")
    k = max(1, n_of(t - 0.015) - a)
    base = float(env[:k].max())
    peak = float(env[k:].max())
    if peak <= base * 1.2 or peak <= 0:
        return None
    i = k + int(np.argmax(env[k:] > base + frac * (peak - base)))
    return (a + i) / SR


def report(x, stems, meta, integ, tp, lra_v, path):
    lines = []
    P = lines.append
    P("THE LAST SIGNAL — soundtrack analysis")
    P("=" * 72)
    info = sf.info(str(CACHE / "soundtrack.wav"))
    P(f"file: {info.samplerate} Hz, {info.channels} ch, {info.subtype}, {info.frames} frames = {info.frames / info.samplerate:.6f} s "
      f"({'OK' if info.frames == n_of(edl.DURATION) else 'WRONG LENGTH'})")
    try:
        import pyloudnorm as pyln
        pl = pyln.Meter(SR).integrated_loudness(x)
    except Exception:  # noqa: BLE001
        pl = float("nan")
    P(f"integrated loudness: {integ:.2f} LUFS (pyloudnorm cross-check {pl:.2f})   target -14 ±1")
    P(f"true peak (4x): {tp:.2f} dBTP   sample peak {dsp.to_db(np.abs(x).max()):.2f} dBFS   target <= -1 dBTP")
    P(f"loudness range: {lra_v:.1f} LU")
    P(f"beacon flashes: {len(FLASHES)} ({'S15 from ' + str(elements.LIGHTCURVE.relative_to(HERE.parents[1])) if MEASURED else 'all from edl.beacon_flashes()'})")
    ts, ls = loudness.short_term(x)
    tm, lm = loudness.momentary(x)
    k = int(np.argmax(ls))
    P(f"max short-term: {ls[k]:.2f} LUFS at {ts[k]:.2f} s   max momentary: {lm.max():.2f} LUFS at {tm[np.argmax(lm)]:.2f} s")
    # top short-term peaks (separated by 4 s)
    order = np.argsort(ls)[::-1]
    peaks = []
    for i in order:
        if all(abs(ts[i] - q) > 4.0 for q, _ in peaks):
            peaks.append((ts[i], ls[i]))
        if len(peaks) == 5:
            break
    P("short-term peaks: " + ", ".join(f"{v:.1f} @ {q:.1f}s" for q, v in sorted(peaks)))
    P("")
    P("silence / edges")
    for a, b in edl.SILENCE:
        i0, i1 = n_of(a), n_of(b)
        nz = int(np.count_nonzero(x[i0:i1]))
        pre = np.flatnonzero(np.abs(x[:i0]).max(axis=1) > 0)
        post = np.flatnonzero(np.abs(x[i1:]).max(axis=1) > 0)
        P(f"  {a:.3f}-{b:.3f} s: {i1 - i0} samples, {nz} non-zero -> {'TRUE DIGITAL SILENCE' if nz == 0 else 'NOT SILENT'}")
        if len(pre):
            P(f"    last non-zero before: {pre[-1] / SR:.6f} s (cut at {a:.3f})")
        if len(post):
            P(f"    first non-zero after: {(i1 + post[0]) / SR:.6f} s (sting at {b:.3f})")
    nzall = np.flatnonzero(np.abs(x).max(axis=1) > 0)
    P(f"  last non-zero sample: {nzall[-1] / SR:.4f} s; final sample value {np.abs(x[-1]).max():.1e}")
    tail = x[n_of(edl.DURATION - 0.3):]
    P(f"  last 300 ms rms: {dsp.to_db(np.sqrt(np.mean(tail ** 2))):.1f} dBFS (the last pulse dying into the end)")
    P("")
    P("alignment against edl.py (onset = 1 ms envelope passes baseline + 30 % (hits) / 10 % (pulses) of the rise)")
    for c in edl.CUES:
        if c.kind in HIT_KINDS:
            src = stems.get("fx", x)
            o = onset_near(src, c.t)
            P(f"  {c.kind:12s} EDL {c.t:7.3f}  onset {o:8.4f}  offset {1000 * (o - c.t):+6.1f} ms" if o is not None else f"  {c.kind} no onset")
    sig = stems.get("signal")
    if sig is not None:
        offs = []
        for p in edl.signal_pulses():
            o = onset_near(sig, p.t, pre=0.08, post=0.12, frac=0.1)
            if o is not None:
                offs.append(1000 * (o - p.t))
        P(f"  signal pulses: {len(offs)} onsets, offset min {min(offs):+.1f} / max {max(offs):+.1f} ms")
    bc = stems.get("beacon")
    if bc is not None:
        offs = []
        for p in FLASHES:
            if abs(dsp.mono(bc[n_of(p.t):n_of(p.t) + 480])).max() > 1e-4:
                o = onset_near(bc, p.t, pre=0.05, post=0.05, frac=0.1)
                if o is not None:
                    offs.append(1000 * (o - p.t))
        if offs:
            P(f"  beacon flashes: {len(offs)} audible onsets, offset min {min(offs):+.1f} / max {max(offs):+.1f} ms")
    P("")
    P("per shot:   rms dBFS | short-term LUFS mean / max (momentary if < 3 s) | sub 20-80 Hz dBFS | 150-1k dBFS")
    tsub, esub = band_energy(x, 20, 80)
    tmid, emid = band_energy(x, 150, 1000)
    for s in edl.SHOTS:
        a, b = n_of(s.start), n_of(s.end)
        seg = x[a:b]
        rms = dsp.to_db(np.sqrt(np.mean(seg ** 2)) + 1e-30)
        m = (ts >= s.start) & (ts < s.end)
        mm = (tm >= s.start) & (tm < s.end)
        lmean = ls[m].mean() if m.any() else lm[mm].mean()
        lmax = ls[m].max() if m.any() else lm[mm].max()
        if any(abs(s.start - a) < 1e-6 for a, _ in edl.SILENCE):
            P(f"  {s.id:6s} {s.start:5.1f}-{s.end:5.1f}  digital silence (short-term windows straddle it)")
            continue
        ms = (tsub >= s.start) & (tsub < s.end)
        sub = 10 * np.log10(np.mean(10 ** (esub[ms] / 10)) + 1e-20)
        mid = 10 * np.log10(np.mean(10 ** (emid[ms] / 10)) + 1e-20)
        P(f"  {s.id:6s} {s.start:5.1f}-{s.end:5.1f}  {rms:7.1f} | {lmean:6.1f} / {lmax:6.1f} | {sub:7.1f} | {mid:7.1f}   {s.title}")
    P("")
    if meta:
        P("render: " + json.dumps(meta))
    path.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wav", type=Path, default=CACHE / "soundtrack.wav")
    a = ap.parse_args()
    REVIEW.mkdir(parents=True, exist_ok=True)
    x, sr = sf.read(str(a.wav), always_2d=True)
    assert sr == SR
    stems = {}
    for s in STEM_NAMES:
        p = CACHE / "stems" / f"{s}.wav"
        if p.exists():
            stems[s], _ = sf.read(str(p), always_2d=True)
    meta_p = CACHE / "render_meta.json"
    meta = json.loads(meta_p.read_text()) if meta_p.exists() else {}
    integ = loudness.integrated(x)
    tp = dsp.true_peak_db(x)
    lra_v = loudness.lra(x)
    fig_spectrogram(x, REVIEW / "spectrogram.png")
    fig_loudness(x, REVIEW / "loudness.png", integ, tp, lra_v)
    fig_sub(x, REVIEW / "sub_energy.png")
    if stems:
        fig_stems(stems, REVIEW / "stems.png")
        fig_motif(x, stems, REVIEW / "motif.png")
    report(x, stems, meta, integ, tp, lra_v, REVIEW / "report.txt")


if __name__ == "__main__":
    main()

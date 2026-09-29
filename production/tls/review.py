"""Review tools (you can't watch video, so measure it).

  python -m tls.review camera  [--out production/review/camera.png]   camera angular speed & accel per shot
  python -m tls.review strips  VIDEO [--out dir]                      frame strips across every cut
  python -m tls.review sheet   VIDEO [--out file]                     contact sheet, 2 frames per shot

Camera metrics: angular speed of the view direction (deg/s, the thing an audience perceives as camera
motion) and its derivative (deg/s^2) sampled at 96 Hz; jerk flags where the acceleration jumps.
"""
from __future__ import annotations

import argparse
import importlib
import math
import subprocess
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from . import edl  # noqa: E402
from .paths import PROD  # noqa: E402

INK, INK2, GRID, SURF = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
S1, S2 = "#2a78d6", "#eb6834"


def camera_metrics(shot_id: str, rate: float = 96.0):
    mod = importlib.import_module(f"shots.{shot_id}.shot")
    s = edl.SHOT_BY_ID[shot_id]
    ts = np.arange(s.start, s.end, 1.0 / rate)
    f = np.array([np.asarray(mod.cam_at(t).fwd, float) for t in ts])
    f /= np.linalg.norm(f, axis=1, keepdims=True)
    ang = np.degrees(np.arccos(np.clip((f[1:] * f[:-1]).sum(1), -1, 1))) * rate
    acc = np.diff(ang) * rate
    fov = np.array([mod.cam_at(t).hfov for t in ts])
    return ts[1:], ang, ts[2:], acc, fov


def camera_report(out: Path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    shots = [s for s in edl.SHOTS if s.kind == "shot"]
    fig, axes = plt.subplots(len(shots), 2, figsize=(12, 1.25 * len(shots)), facecolor=SURF)
    lines = []
    for i, s in enumerate(shots):
        t, v, ta, a, fov = camera_metrics(s.id)
        # perceived motion in screen widths per second (normalise by field of view)
        vw = v / np.maximum(fov[1:], 1e-3)
        axv, axa = axes[i]
        for ax in (axv, axa):
            ax.set_facecolor(SURF)
            ax.grid(True, color=GRID, lw=0.6)
            for sp in ax.spines.values():
                sp.set_visible(False)
            ax.tick_params(colors=INK2, labelsize=7)
        axv.plot(t, vw, color=S1, lw=1.6)
        axv.set_ylabel(s.id, color=INK, fontsize=8, rotation=0, ha="right", va="center")
        axa.plot(ta, a, color=S2, lw=1.2)
        jerk = np.abs(np.diff(a)) * 96
        worst = float(np.percentile(jerk, 99.5)) if len(jerk) else 0.0
        lines.append(f"{s.id:5s} speed mean {np.mean(vw):.3f} max {np.max(vw):.3f} frame-widths/s | "
                     f"accel max {np.max(np.abs(a)):.2f} deg/s^2 | jerk p99.5 {worst:.1f}")
        if i == 0:
            axv.set_title("view motion (frame widths per second)", color=INK, fontsize=9, loc="left")
            axa.set_title("angular acceleration (deg/s²)", color=INK, fontsize=9, loc="left")
    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=90)
    txt = out.with_suffix(".txt")
    txt.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    print(f"-> {out}")


def ffmpeg(*a):
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *map(str, a)], check=True)


def strips(video: Path, outdir: Path, width=320):
    """For each cut: 3 frames before, 3 after, side by side."""
    from PIL import Image
    outdir.mkdir(parents=True, exist_ok=True)
    cuts = [s.start for s in edl.SHOTS[1:]]
    rows = []
    for c in cuts:
        tiles = []
        for k in (-3, -2, -1, 0, 1, 2):
            t = max(0.0, c + (k + 0.5) / edl.FPS)
            p = outdir / "tmp.png"
            ffmpeg("-ss", f"{t:.4f}", "-i", video, "-frames:v", 1, "-vf", f"scale={width}:-2", p)
            tiles.append(np.asarray(Image.open(p).convert("RGB")))
        rows.append(np.concatenate(tiles, 1))
    h = max(r.shape[0] for r in rows)
    rows = [np.pad(r, ((0, h - r.shape[0]), (0, 0), (0, 0))) for r in rows]
    for i in range(0, len(rows), 6):
        Image.fromarray(np.concatenate(rows[i:i + 6], 0)).save(outdir / f"cuts_{i // 6:02d}.jpg", quality=88)
    (outdir / "tmp.png").unlink(missing_ok=True)
    print(f"-> {outdir}")


def sheet(video: Path, out: Path, width=384):
    from PIL import Image, ImageDraw
    tiles = []
    for s in edl.SHOTS:
        for u in (0.25, 0.75):
            t = s.start + u * s.dur
            p = out.parent / "tmp_sheet.png"
            ffmpeg("-ss", f"{t:.4f}", "-i", video, "-frames:v", 1, "-vf", f"scale={width}:-2", p)
            im = Image.open(p).convert("RGB")
            ImageDraw.Draw(im).text((4, 3), f"{s.id} {t:.1f}s", fill=(230, 200, 60))
            tiles.append(np.asarray(im))
    h = tiles[0].shape[0]
    tiles = [np.pad(x, ((0, h - x.shape[0]), (0, 0), (0, 0))) for x in tiles]
    rows = [np.concatenate(tiles[i:i + 4], 1) for i in range(0, len(tiles) - len(tiles) % 4, 4)]
    if len(tiles) % 4:
        rest = tiles[len(tiles) - len(tiles) % 4:]
        rest += [np.zeros_like(tiles[0])] * (4 - len(rest))
        rows.append(np.concatenate(rest, 1))
    Image.fromarray(np.concatenate(rows, 0)).save(out, quality=88)
    (out.parent / "tmp_sheet.png").unlink(missing_ok=True)
    print(f"-> {out}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["camera", "strips", "sheet"])
    ap.add_argument("video", nargs="?")
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()
    sys.path.insert(0, str(PROD))
    if a.cmd == "camera":
        camera_report(a.out or PROD / "review" / "camera.png")
    elif a.cmd == "strips":
        strips(Path(a.video), a.out or PROD / "review" / "cuts")
    elif a.cmd == "sheet":
        sheet(Path(a.video), a.out or PROD / "review" / "sheet.jpg")


if __name__ == "__main__":
    main()

"""Command line entry point:  python -m lastsignal <command> [options]

Commands
  render     full pipeline in one process (frames -> audio -> mux -> contact sheet -> verify)
  segment    render one shard of the frames to an .mp4 segment (used by the cloud matrix)
  assemble   concat segments, mux audio, make contact sheet, verify
  audio      synthesise the soundtrack (.wav)
  still      render one frame to .png
  keyframes  render the key frames of every shot and a contact sheet
  sheet      build a contact sheet from an existing video
  frames     extract PNG frames from a video (at given times, or every N seconds)
  verify     check an output video (duration, streams, resolution, black/blank frames)
  selftest   fast sanity checks: timeline continuity, one frame per shot, soundtrack
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out"


def _renderer(quality: str):
    from .gl import QUALITIES, Renderer, configure_threads

    configure_threads()
    q = QUALITIES[quality]
    return q, Renderer(q)


SHUTTER = 0.5  # 180-degree shutter


def _frame(R, q, t: float, frame: int) -> bytes:
    """One output frame. Each anti-aliasing pass also samples a different instant
    inside the shutter interval, which gives real motion blur. Sub-frame times are
    clamped to the current shot so blur never bleeds across a cut."""
    from .gl import JITTER
    from .text import text_layer
    from .timeline import params_at, shot_at

    P = params_at(t, frame)
    n = len(JITTER[q.samples])
    if n > 1 and P.get("scene", True):
        shot = shot_at(t)
        span = SHUTTER / q.fps
        passes = []
        for i in range(n):
            ti = t + ((i + 0.5) / n - 0.5) * span
            ti = min(max(ti, shot.start), shot.end - 1e-4)
            passes.append(params_at(ti, frame))
        P["passes"] = passes
    img, key = text_layer(P, q.out_w, q.out_h)
    return R.render(P, img, key)


def n_frames(fps: int) -> int:
    from .timeline import DURATION

    return int(round(DURATION * fps))


def shard_ranges(fps: int, shards: int) -> list[tuple[int, int]]:
    """Contiguous frame ranges with roughly equal render cost."""
    from .timeline import params_at

    n = n_frames(fps)
    cost = [1.0 if params_at(i / fps, i).get("scene", True) else 0.05 for i in range(n)]
    total = sum(cost)
    ranges, start, acc = [], 0, 0.0
    for i, c in enumerate(cost):
        acc += c
        if len(ranges) < shards - 1 and acc >= total * (len(ranges) + 1) / shards:
            ranges.append((start, i + 1))
            start = i + 1
    ranges.append((start, n))
    while len(ranges) < shards:
        ranges.append((n, n))
    return ranges


def render_segment(quality: str, start: int, end: int, out: Path, log_every: int = 12) -> Path:
    from .encode import VideoWriter

    q, R = _renderer(quality)
    print(f"[segment] {quality} frames {start}..{end - 1} -> {out}  ({R.gl_info})", flush=True)
    vw = VideoWriter(out, q.out_w, q.out_h, q.fps, q.crf, q.x264_preset)
    t0 = time.time()
    for k, f in enumerate(range(start, end)):
        vw.write(_frame(R, q, f / q.fps, f))
        done = k + 1
        if done % log_every == 0 or f == end - 1:
            el = time.time() - t0
            eta = el / done * (end - start - done)
            print(f"  frame {f:4d}  {done}/{end - start}  {el / done:5.2f}s/f  eta {eta / 60:5.1f} min", flush=True)
    vw.close()
    R.release()
    return out


def cmd_segment(a):
    from .gl import QUALITIES

    q = QUALITIES[a.quality]
    start, end = shard_ranges(q.fps, a.shards)[a.shard]
    out = Path(a.out) if a.out else OUT / a.quality / "segments" / f"seg_{a.shard:02d}.mp4"
    if end <= start:
        print("empty shard, nothing to do")
        return 0
    render_segment(a.quality, start, end, out)
    return 0


def cmd_audio(a):
    from .audio import render_soundtrack

    out = Path(a.out) if a.out else OUT / "audio" / "the_last_signal.wav"
    render_soundtrack(out)
    print("audio ->", out)
    return 0


def _assemble(quality: str, segments: list[Path], audio: Path | None) -> Path:
    from .encode import concat, mux

    qdir = OUT / quality
    qdir.mkdir(parents=True, exist_ok=True)
    silent = qdir / "video_only.mp4"
    segments = sorted(p for p in segments if p.exists() and p.stat().st_size > 0)
    if not segments:
        raise SystemExit("no segments found")
    concat(segments, silent)
    if audio is None:
        from .audio import render_soundtrack

        audio = OUT / "audio" / "the_last_signal.wav"
        if not audio.exists():
            render_soundtrack(audio)
    final = qdir / f"THE_LAST_SIGNAL_{quality}.mp4"
    mux(silent, audio, final)
    silent.unlink()
    print("video ->", final)
    make_sheet(final, qdir / f"contact_sheet_{quality}.jpg")
    report = verify(final, quality)
    (qdir / "verify.json").write_text(json.dumps(report, indent=2) + "\n")
    return final


def cmd_assemble(a):
    segdir = Path(a.segments) if a.segments else OUT / a.quality / "segments"
    segs = sorted(segdir.glob("**/seg_*.mp4"))
    _assemble(a.quality, segs, Path(a.audio) if a.audio else None)
    return 0


def cmd_render(a):
    from .gl import QUALITIES

    q = QUALITIES[a.quality]
    n = n_frames(q.fps)
    seg = OUT / a.quality / "segments" / "seg_00.mp4"
    t0 = time.time()
    render_segment(a.quality, 0, n, seg)
    print(f"rendered {n} frames in {(time.time() - t0) / 60:.1f} min")
    cmd_audio(argparse.Namespace(out=None))
    _assemble(a.quality, [seg], None)
    return 0


def cmd_still(a):
    from PIL import Image

    q, R = _renderer(a.quality)
    t0 = time.time()
    data = _frame(R, q, a.t, int(round(a.t * q.fps)))
    print(f"t={a.t:.3f}s rendered in {time.time() - t0:.2f}s")
    out = Path(a.out) if a.out else OUT / a.quality / "stills" / f"t{a.t:06.3f}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    Image.frombytes("RGB", (q.out_w, q.out_h), data).save(out)
    print("still ->", out)
    return 0


def cmd_keyframes(a):
    from PIL import Image

    from .contact import contact_sheet
    from .timeline import keyframe_times

    q, R = _renderer(a.quality)
    kdir = OUT / a.quality / "keyframes"
    kdir.mkdir(parents=True, exist_ok=True)
    items = []
    times = keyframe_times()
    if a.only:
        times = [(t, l) for t, l in times if any(t >= float(x.split(':')[0]) and t <= float(x.split(':')[1]) for x in a.only)]
    for t, label in times:
        t0 = time.time()
        img = Image.frombytes("RGB", (q.out_w, q.out_h), _frame(R, q, t, int(round(t * q.fps))))
        img.save(kdir / f"key_{t:06.3f}.png")
        items.append((img, f"{t:6.2f}s  {label}"))
        print(f"  key {t:6.2f}s  {time.time() - t0:5.2f}s", flush=True)
    sheet = contact_sheet(items, OUT / a.quality / f"keyframes_sheet_{a.quality}.jpg", cols=a.cols)
    print("contact sheet ->", sheet)
    return 0


def make_sheet(video: Path, out: Path) -> Path:
    import tempfile

    from PIL import Image

    from .contact import contact_sheet
    from .encode import extract_frame
    from .timeline import keyframe_times

    times = keyframe_times()
    items = []
    with tempfile.TemporaryDirectory() as td:
        for i, (t, label) in enumerate(times):
            p = Path(td) / f"{i:03d}.png"
            extract_frame(video, t, p)
            items.append((Image.open(p).convert("RGB"), f"{t:6.2f}s  {label}"))
        contact_sheet(items, out)
    print("contact sheet ->", out)
    return out


def cmd_sheet(a):
    v = Path(a.video)
    make_sheet(v, Path(a.out) if a.out else v.with_name(v.stem + "_sheet.jpg"))
    return 0


def cmd_frames(a):
    from .encode import extract_frame
    from .timeline import DURATION

    v = Path(a.video)
    out = Path(a.out) if a.out else v.with_name(v.stem + "_frames")
    out.mkdir(parents=True, exist_ok=True)
    if a.times:
        times = [float(x) for x in a.times]
    else:
        n = int(DURATION / a.every)
        times = [round(i * a.every + a.every / 2, 3) for i in range(n)]
    for t in times:
        p = out / f"frame_{t:06.3f}.png"
        extract_frame(v, t, p, a.width)
        print(p)
    return 0


def verify(path: Path, quality: str | None = None) -> dict:
    """Sanity checks on a rendered trailer. Raises SystemExit on failure."""
    import subprocess

    import numpy as np

    from .encode import ffmpeg_bin, probe
    from .timeline import DURATION, SHOTS

    info = probe(path)
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    a = [s for s in info["streams"] if s["codec_type"] == "audio"]
    dur = float(info["format"]["duration"])
    fps = eval(v["r_frame_rate"])  # e.g. "24/1"
    problems = []
    if abs(dur - DURATION) > 0.15:
        problems.append(f"duration {dur:.3f}s != {DURATION}s")
    if not a:
        problems.append("no audio stream")
    if v.get("pix_fmt") != "yuv420p":
        problems.append(f"pix_fmt {v.get('pix_fmt')}")
    if quality:
        from .gl import QUALITIES

        q = QUALITIES[quality]
        if (int(v["width"]), int(v["height"])) != (q.out_w, q.out_h):
            problems.append(f"size {v['width']}x{v['height']}")
    # every shot that should show picture must not be black; blacks must be black
    w, h = 160, 90
    raw = subprocess.run([ffmpeg_bin(), "-v", "error", "-i", str(path), "-vf", f"scale={w}:{h}",
                          "-f", "rawvideo", "-pix_fmt", "gray", "-"], check=True, capture_output=True).stdout
    frames = np.frombuffer(raw, np.uint8).reshape(-1, h, w)
    means = frames.mean(axis=(1, 2))
    shot_stats = {}
    for s in SHOTS:
        i0, i1 = int(math.ceil(s.start * fps)), int(math.floor(s.end * fps))
        m = means[i0:i1]
        if len(m) == 0:
            continue
        shot_stats[s.name] = {"frames": int(len(m)), "mean_luma": round(float(m.mean()), 2),
                              "max_luma": round(float(m.max()), 2)}
        if s.name.startswith("black") and m.max() > 20:
            problems.append(f"{s.name} should be black (max luma {m.max():.1f})")
        if s.name.startswith("s") and not s.name.startswith("s_") and float(np.median(m)) < 2.0:
            problems.append(f"{s.name} is (almost) black (median luma {np.median(m):.2f})")
    report = {
        "file": str(path), "size_mb": round(path.stat().st_size / 1e6, 2),
        "duration": dur, "fps": fps, "frames": int(len(frames)),
        "video": f"{v['codec_name']} {v['width']}x{v['height']} {v.get('pix_fmt')} {v.get('profile')}",
        "audio": f"{a[0]['codec_name']} {a[0].get('sample_rate')}Hz {a[0].get('channels')}ch" if a else None,
        "shots": shot_stats, "problems": problems, "ok": not problems,
    }
    print(json.dumps(report, indent=2))
    if problems:
        raise SystemExit("verification failed: " + "; ".join(problems))
    return report


def cmd_verify(a):
    verify(Path(a.video), a.quality)
    return 0


def cmd_selftest(a):
    import numpy as np

    from .timeline import DURATION, PINGS, SHOTS, params_at

    errors = []
    # 1. the edit is gap-free and exactly DURATION long
    if SHOTS[0].start != 0.0 or abs(SHOTS[-1].end - DURATION) > 1e-9:
        errors.append("shots do not span the full duration")
    for s0, s1 in zip(SHOTS, SHOTS[1:]):
        if abs(s0.end - s1.start) > 1e-9:
            errors.append(f"gap/overlap between {s0.name} and {s1.name}")
    if any(not (0.0 <= t < DURATION) for t, _, _ in PINGS):
        errors.append("sound event outside the trailer")
    # 2. one mid-shot frame per shot renders and has the expected brightness
    q, R = _renderer("draft")
    for s in SHOTS:
        t = (s.start + s.end) / 2
        img = np.frombuffer(_frame(R, q, t, int(t * q.fps)), np.uint8)
        m = float(img.mean())
        Pm = params_at(t)
        black = not Pm.get("scene", True) and Pm.get("text") is None
        card = not Pm.get("scene", True) and Pm.get("text") is not None
        ok = (m < 1.0) if black else (m > 0.2) if card else (m > 1.0)
        print(f"  {s.name:12s} t={t:6.2f}  mean={m:6.2f}  {'ok' if ok else 'FAIL'}")
        if not ok:
            errors.append(f"{s.name}: unexpected brightness {m:.2f}")
    R.release()
    # 3. soundtrack length
    import wave

    from .audio import render_soundtrack

    wav = OUT / "audio" / "the_last_signal.wav"
    render_soundtrack(wav)
    with wave.open(str(wav)) as w:
        dur = w.getnframes() / w.getframerate()
    print(f"  soundtrack {dur:.3f}s")
    if abs(dur - DURATION) > 1e-3:
        errors.append(f"soundtrack is {dur}s")
    if errors:
        raise SystemExit("selftest FAILED: " + "; ".join(errors))
    print("selftest passed")
    return 0


def cmd_shards(a):
    from .gl import QUALITIES

    q = QUALITIES[a.quality]
    for i, (s, e) in enumerate(shard_ranges(q.fps, a.shards)):
        print(i, s, e, e - s)
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="lastsignal", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    qual = dict(choices=["draft", "preview", "final"], default="draft")

    p = sub.add_parser("render"); p.add_argument("--quality", **qual); p.set_defaults(fn=cmd_render)
    p = sub.add_parser("segment"); p.add_argument("--quality", **qual)
    p.add_argument("--shard", type=int, default=0); p.add_argument("--shards", type=int, default=1)
    p.add_argument("--out"); p.set_defaults(fn=cmd_segment)
    p = sub.add_parser("assemble"); p.add_argument("--quality", **qual)
    p.add_argument("--segments"); p.add_argument("--audio"); p.set_defaults(fn=cmd_assemble)
    p = sub.add_parser("audio"); p.add_argument("--out"); p.set_defaults(fn=cmd_audio)
    p = sub.add_parser("still"); p.add_argument("--quality", **qual); p.add_argument("--t", type=float, required=True)
    p.add_argument("--out"); p.set_defaults(fn=cmd_still)
    p = sub.add_parser("keyframes"); p.add_argument("--quality", **qual); p.add_argument("--cols", type=int, default=4)
    p.add_argument("--only", nargs="*", help="time windows a:b"); p.set_defaults(fn=cmd_keyframes)
    p = sub.add_parser("sheet"); p.add_argument("video"); p.add_argument("--out"); p.set_defaults(fn=cmd_sheet)
    p = sub.add_parser("frames"); p.add_argument("video"); p.add_argument("--times", nargs="*")
    p.add_argument("--every", type=float, default=1.0); p.add_argument("--width", type=int)
    p.add_argument("--out"); p.set_defaults(fn=cmd_frames)
    p = sub.add_parser("verify"); p.add_argument("video"); p.add_argument("--quality", choices=["draft", "preview", "final"])
    p.set_defaults(fn=cmd_verify)
    p = sub.add_parser("selftest"); p.set_defaults(fn=cmd_selftest)
    p = sub.add_parser("shards"); p.add_argument("--quality", **qual); p.add_argument("--shards", type=int, default=8)
    p.set_defaults(fn=cmd_shards)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())

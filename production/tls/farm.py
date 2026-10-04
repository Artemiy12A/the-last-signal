"""Render farm helpers (GitHub Actions): plan shards, render a shard, assemble the film.

  python -m tls.farm plan --request production/render-request.json      -> writes matrix JSON to stdout
  python -m tls.farm shard --quality final --frames 1164-1260 --out seg  -> frames + ProRes segment
  python -m tls.farm assemble --quality final --segments segs --out dist

A patch run (render-request "frames": "missing", "reuse_runs": [run ids]) renders only the frames earlier
runs did not deliver and assembles them with those runs' segments (downloaded under segs/reuse/).
"""
from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from . import edl  # noqa: E402
from .paths import OUT, PROD, ROOT  # noqa: E402

# rough relative cost per frame (final quality, 4 vCPU seconds) used for load balancing
COST = {
    # fitted to the final run's shard times (tls90-final, run 37163704098; seconds/frame / 1.5)
    "BLK0": 4, "BLK1": 1, "TITLE": 3, "BTN": 2,
    "S01": 5, "S02": 420, "S03": 135, "S04": 80, "S05": 45, "S06": 145, "S07": 245, "S08": 115,
    "S09": 225, "S10": 190, "S11": 335, "S12": 240, "S13": 250, "S14": 430, "S15": 160,
}
QSCALE = {"draft": 1 / 16, "preview": 1 / 4, "final": 1.0}


def frame_cost(f: int, q: str) -> float:
    s = edl.shot_at(edl.frame_time(f) + 1e-6)
    return COST.get(s.id, 100) * QSCALE[q]


def parse_frames(spec: str) -> list[int]:
    if spec in ("all", "", None):
        return list(range(edl.NFRAMES))
    out = []
    for part in spec.split(","):
        part = part.strip()
        if part in edl.SHOT_BY_ID:
            s = edl.SHOT_BY_ID[part]
            out += list(range(s.f0, s.f1))
        elif "-" in part:
            a, b = part.split("-")
            out += list(range(int(a), int(b) + 1))
        elif part:
            out.append(int(part))
    return sorted(set(out))


def plan(frames: list[int], q: str, jobs: int, every: int = 1) -> list[dict]:
    """Split frames into `jobs` contiguous shards of ~equal cost."""
    frames = frames[::every]
    costs = [frame_cost(f, q) for f in frames]
    total = sum(costs)
    jobs = max(1, min(jobs, len(frames)))
    target = total / jobs
    shards, cur, acc = [], [], 0.0
    for f, c in zip(frames, costs):
        cur.append(f)
        acc += c
        if acc >= target and len(shards) < jobs - 1:
            shards.append(cur)
            cur, acc = [], 0.0
    if cur:
        shards.append(cur)
    return [{"id": i, "frames": ",".join(_compress(s)), "n": len(s),
             "est_min": round(sum(frame_cost(f, q) for f in s) / 60, 1)} for i, s in enumerate(shards)]


def _gh(path: str, jq: str | None = None) -> str:
    # job logs carry Blender's colour codes, which gh refuses to print without --allow-escape-sequences
    cmd = ["gh", "api", path] + (["--paginate", "--jq", jq] if jq else ["--allow-escape-sequences"])
    return subprocess.run(cmd, check=True, capture_output=True, text=True).stdout


def delivered_by_run(run: int, repo: str, log=None) -> set[int]:
    """Frames one farm run delivered: every successful render job's frames, cut at its deadline line if the
    shard stopped early. A job that failed (runner lost, timeout, crash) delivered nothing: its segments are
    only encoded after the last frame."""
    log = log or (lambda jid: _gh(f"repos/{repo}/actions/jobs/{jid}/logs"))
    rows = _gh(f"repos/{repo}/actions/runs/{run}/jobs?per_page=100",
               '.jobs[] | [.id, .name, .conclusion] | @json').split("\n")
    out = set()
    for jid, name, concl in (json.loads(r) for r in rows if r.strip()):
        m = re.match(r"render \((\d+), (.+), (\d+), [\d.]+\)$", name)
        if not m or concl != "success":
            continue
        fs = parse_frames(m.group(2))
        try:
            text = log(jid)
        except subprocess.CalledProcessError as e:   # never guess: an unread deadline line is a silent black gap
            raise SystemExit(f"cannot read the log of job {jid} ({name}): {e.stderr}")
        d = re.search(r"deadline reached before frame (\d+)", text)
        out.update(f for f in fs if not d or f < int(d.group(1)))
    return out


def missing_after(runs: list[int], repo: str, log=None) -> list[int]:
    have = set()
    for r in runs:
        have |= delivered_by_run(r, repo, log)
    return [f for f in range(edl.NFRAMES) if f not in have]


def _compress(fs: list[int]) -> list[str]:
    out, i = [], 0
    while i < len(fs):
        j = i
        while j + 1 < len(fs) and fs[j + 1] == fs[j] + 1:
            j += 1
        out.append(f"{fs[i]}-{fs[j]}" if j > i else str(fs[i]))
        i = j + 1
    return out


def ffmpeg(*args):
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *map(str, args)]
    subprocess.run(cmd, check=True)


def _runs(fs: list[int], step: int) -> list[tuple[int, int]]:
    """Group sorted frames into runs with constant spacing `step`."""
    out, i = [], 0
    while i < len(fs):
        j = i
        while j + 1 < len(fs) and fs[j + 1] == fs[j] + step:
            j += 1
        out.append((fs[i], fs[j]))
        i = j + 1
    return out


def shard(q: str, frames_spec: str, out: Path, deadline_min: float = 330.0, every: int = 1):
    """Render frames (resumable: existing PNGs are kept) then encode ProRes 4444 segments per
    contiguous run. Stops early (cleanly) if the deadline approaches."""
    from .render import render_frames
    t_start = time.time()
    frames = parse_frames(frames_spec)
    fdir = OUT / q / "_frames"
    fdir.mkdir(parents=True, exist_ok=True)
    done = []
    # group consecutive frames by shot so each shot's Blender work is batched
    groups = []
    for f in frames:
        sid = edl.shot_at(edl.frame_time(f) + 1e-6).id
        if groups and groups[-1][0] == sid:
            groups[-1][1].append(f)
        else:
            groups.append((sid, [f]))
    stop = False
    for sid, fs in groups:
        for i in range(0, len(fs), 12):
            chunk = [f for f in fs[i:i + 12] if not (fdir / f"f{f:05d}.ppm").exists()]
            if (time.time() - t_start) / 60 > deadline_min:
                print(f"deadline reached before frame {fs[i]}", flush=True)
                stop = True
                break
            if chunk:
                for p in render_frames(sid, chunk, q, png16=True, keep_exr=False, outdir=OUT / q / sid):
                    shutil.move(str(p), fdir / p.name)
            done += fs[i:i + 12]
        if stop:
            break
    out.mkdir(parents=True, exist_ok=True)
    for a, b in _runs(done, every):
        last = min(b + every - 1, edl.NFRAMES - 1)
        seg = out / f"seg_{a:05d}_{last:05d}.mov"
        lst = out / f"list_{a:05d}.txt"
        body = ""
        for f in range(a, b + 1, every):
            body += f"file '{fdir / f'f{f:05d}.ppm'}'\nduration {min(every, last - f + 1) / edl.FPS:.6f}\n"
        body += f"file '{fdir / f'f{b:05d}.ppm'}'\n"   # concat demuxer quirk: repeat last entry
        lst.write_text(body)
        ffmpeg("-f", "concat", "-safe", "0", "-i", lst, "-vf", f"fps={edl.FPS}", "-frames:v", last - a + 1,
               "-c:v", "prores_ks", "-profile:v", "4", "-pix_fmt", "yuv444p10le", "-vendor", "apl0", seg)
        lst.unlink()
    print(f"shard: {len(done)}/{len(frames)} frames -> {out}", flush=True)


def assemble(q: str, segdir: Path, out: Path, audio: Path | None, title: str):
    out.mkdir(parents=True, exist_ok=True)
    segdir.mkdir(parents=True, exist_ok=True)
    # this run's segments first, then reused ones (segs/reuse/<run>/) where they don't overlap
    segs = sorted(segdir.rglob("seg_*.mov"),
                  key=lambda p: ("reuse" in p.relative_to(segdir).parts, int(p.stem.split("_")[1])))
    have, keep = set(), []
    for s in segs:
        a, b = map(int, s.stem.split("_")[1:3])
        if have & set(range(a, b + 1)):
            print(f"assemble: skipping {s} (overlaps a newer segment)", flush=True)
            continue
        have.update(range(a, b + 1))
        keep.append(s)
    missing = [f for f in range(edl.NFRAMES) if f not in have]
    print(f"assemble: {len(segs)} segments, {len(have)} frames, {len(missing)} missing", flush=True)
    # fill gaps with black so timing stays locked (reported in the release notes)
    W, H = 1920 if q == "final" else (960 if q == "preview" else 480), 0
    H = int(round(W / 2.39 / 2)) * 2
    fill = []
    for run in _compress(missing):
        a, b = (run.split("-") + [run])[:2]
        a, b = int(a), int(b)
        seg = segdir / f"seg_{a:05d}_{b:05d}.mov"
        ffmpeg("-f", "lavfi", "-i", f"color=c=black:s={W}x{H}:r={edl.FPS}", "-frames:v", b - a + 1,
               "-c:v", "prores_ks", "-profile:v", "4", "-pix_fmt", "yuv444p10le", seg)
        fill.append(seg)
    segs = sorted(keep + fill, key=lambda p: int(p.stem.split("_")[1]))
    lst = out / "segments.txt"
    lst.write_text("".join(f"file '{s.resolve()}'\n" for s in segs))
    joined = out / "joined.mov"
    ffmpeg("-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", joined)
    base = "THE_LAST_SIGNAL" + ("" if q == "final" else f"_{q}")
    master = out / f"{base}_master_ProRes422HQ.mov"
    mp4 = out / f"{base}.mp4"
    a_in = ["-i", audio] if audio and audio.exists() else []
    a_map = ["-map", "0:v", "-map", "1:a"] if a_in else []
    def prores(profile, path):
        ffmpeg("-i", joined, *a_in, *a_map, "-c:v", "prores_ks", "-profile:v", profile, "-pix_fmt", "yuv422p10le",
               "-vendor", "apl0", *(["-c:a", "pcm_s24le"] if a_in else []), "-t", edl.DURATION,
               "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709", path)
    prores("3", master)
    if master.stat().st_size > 1.9e9:   # GitHub release assets stop at 2 GB: fall back to ProRes 422
        master.unlink()
        master = out / f"{base}_master_ProRes422.mov"
        prores("2", master)
    # phone-friendly ceiling: CRF 14 with grain can balloon past what a phone streams comfortably
    cap = ["-maxrate", "40M", "-bufsize", "80M"] if q == "final" else []
    ffmpeg("-i", joined, *a_in, *a_map, "-c:v", "libx264", "-preset", "slow", "-crf", "14" if q == "final" else "18",
           *cap, "-tune", "grain", "-profile:v", "high", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
           "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
           *(["-c:a", "aac", "-b:a", "320k"] if a_in else []), "-t", edl.DURATION, mp4)
    joined.unlink()
    # stills + contact sheet
    stills = out / "stills"
    stills.mkdir(exist_ok=True)
    for s in edl.SHOTS:
        if s.kind == "shot":
            tm = s.start + 0.6 * s.dur
            ffmpeg("-ss", f"{tm:.3f}", "-i", mp4, "-frames:v", 1, "-q:v", 2, stills / f"{s.id}.jpg")
    ffmpeg("-i", mp4, "-vf", "fps=1,scale=384:-1,tile=6x15:padding=4:margin=4", "-frames:v", 1, "-q:v", 3,
           out / "contact_sheet.jpg")
    (out / "missing_frames.json").write_text(json.dumps(missing))
    print(f"assemble: -> {mp4}, {master}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["plan", "shard", "assemble"])
    ap.add_argument("--request", type=Path)
    ap.add_argument("--quality", default="preview")
    ap.add_argument("--frames", default="all")
    ap.add_argument("--jobs", type=int, default=20)
    ap.add_argument("--every", type=int, default=1)
    ap.add_argument("--out", type=Path, default=Path("seg"))
    ap.add_argument("--segments", type=Path, default=Path("segs"))
    ap.add_argument("--audio", type=Path, default=None)
    ap.add_argument("--deadline", type=float, default=330.0)
    a = ap.parse_args()
    if a.cmd == "plan":
        req = json.loads(a.request.read_text()) if a.request else {}
        q = req.get("quality", a.quality)
        spec = req.get("frames", a.frames)
        frames = (missing_after([int(r) for r in req.get("reuse_runs", [])], "Artemiy12A/the-last-signal")
                  if spec == "missing" else parse_frames(spec))
        shards = plan(frames, q, int(req.get("jobs", a.jobs)), int(req.get("every", 1)))
        print(json.dumps({"quality": q, "shards": shards}))
    elif a.cmd == "shard":
        shard(a.quality, a.frames, a.out, a.deadline, a.every)
    elif a.cmd == "assemble":
        assemble(a.quality, a.segments, a.out, a.audio, "THE LAST SIGNAL")


if __name__ == "__main__":
    main()

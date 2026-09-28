"""ffmpeg helpers: streaming encode, segment concat, audio mux, probing."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path


def ffmpeg_bin() -> str:
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:  # fallback: static build shipped by imageio-ffmpeg
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("ffmpeg not found (apt install ffmpeg)") from exc


def ffprobe_bin() -> str | None:
    return shutil.which("ffprobe")


def x264_args(crf: int, preset: str) -> list[str]:
    return [
        "-c:v", "libx264", "-preset", preset, "-crf", str(crf), "-tune", "film",
        "-profile:v", "high", "-level:v", "4.2",
        "-x264-params", "aq-mode=3:aq-strength=0.9:deblock=-1,-1",
        "-pix_fmt", "yuv420p",
        "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv",
    ]


class VideoWriter:
    """Pipe raw RGB frames into ffmpeg/x264."""

    def __init__(self, path: Path, w: int, h: int, fps: int, crf: int, preset: str):
        path.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            ffmpeg_bin(), "-hide_banner", "-loglevel", "error", "-y",
            "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}", "-r", str(fps), "-i", "-",
            "-vf", "scale=out_color_matrix=bt709:out_range=tv:flags=bicubic+accurate_rnd+full_chroma_int",
            *x264_args(crf, preset),
            "-g", str(fps * 2), "-movflags", "+faststart",
            str(path),
        ]
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)

    def write(self, rgb: bytes):
        self.proc.stdin.write(rgb)

    def close(self):
        self.proc.stdin.close()
        if self.proc.wait() != 0:
            raise RuntimeError("ffmpeg encode failed")


def concat(segments: list[Path], out: Path):
    lst = out.with_suffix(".txt")
    lst.write_text("".join(f"file '{p.resolve()}'\n" for p in segments))
    subprocess.run([ffmpeg_bin(), "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0",
                    "-i", str(lst), "-c", "copy", "-movflags", "+faststart", str(out)], check=True)
    lst.unlink()


def mux(video: Path, audio: Path, out: Path):
    subprocess.run([ffmpeg_bin(), "-hide_banner", "-loglevel", "error", "-y",
                    "-i", str(video), "-i", str(audio),
                    "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy",
                    "-c:a", "aac", "-b:a", "320k", "-ar", "48000",
                    "-shortest", "-movflags", "+faststart",
                    "-metadata", "title=THE LAST SIGNAL", str(out)], check=True)


def probe(path: Path) -> dict:
    exe = ffprobe_bin()
    if not exe:
        raise RuntimeError("ffprobe not found")
    out = subprocess.run([exe, "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)],
                         check=True, capture_output=True, text=True).stdout
    return json.loads(out)


def extract_frame(video: Path, t: float, out: Path, width: int | None = None):
    vf = [f"scale={width}:-2"] if width else []
    subprocess.run([ffmpeg_bin(), "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{t:.3f}", "-i", str(video),
                    "-frames:v", "1", *(["-vf", ",".join(vf)] if vf else []), str(out)], check=True)

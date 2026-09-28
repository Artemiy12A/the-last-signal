"""Fetch the few real space recordings used as texture layers in the soundtrack.

    python production/audio/fetch_audio.py          # download (skips files already verified)
    python production/audio/fetch_audio.py --check  # verify checksums only

Files land in production/cache/audio/src/ (gitignored). Sources, licences and credit lines are
listed in production/audio/ASSETS_AUDIO.md. Everything else in the soundtrack is synthesised.
"""
from __future__ import annotations

import hashlib
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC_DIR = HERE.parent / "cache" / "audio" / "src"

# name -> (url, sha256, licence, credit)
SOURCES = {
    "juno_ganymede.wav": (
        "https://www.nasa.gov/wp-content/uploads/2024/05/e2-wave-ganymede-flyby-compressed.wav",
        "8cb5393b9faa6cde859a6164a635bcbecb4cf8b6cfe70acc20e6ad3da7711919",
        "Public domain (NASA media guidelines)",
        "NASA/JPL-Caltech/SwRI/Univ of Iowa",
    ),
    "cassini_skr.wav": (
        "https://space-audio.org/cassini/SKR1/SKR-03-324.wav",
        "54b2e2a15edf1e65e5771c7d74422e9c158d0aa87b11fc5730c7a085d49ebdfb",
        "CC BY 4.0",
        "Original space audio recordings provided courtesy of NASA and The University of Iowa. "
        "https://space-audio.org/",
    ),
    "insight_wind.wav": (
        "https://www.nasa.gov/wp-content/uploads/2015/01/08-Brian-Cook_raw_velocity_0.6_normalisedx1_2octavesUp_03.wav",
        "9f0fa7d6ef14298dc942091d2c083a7809dc96bfaacdac901e7c3ffef4274710",
        "Public domain (NASA media guidelines)",
        "NASA/JPL-Caltech/CNES/IPGP",
    ),
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch(url: str, dst: Path, tries: int = 5) -> None:
    tmp = dst.with_suffix(dst.suffix + ".part")
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "the-last-signal-audio/1.0 (film sound build)"})
            with urllib.request.urlopen(req, timeout=60) as r, open(tmp, "wb") as f:
                expected = int(r.headers.get("Content-Length") or 0)
                n = 0
                while True:
                    b = r.read(1 << 16)
                    if not b:
                        break
                    f.write(b)
                    n += len(b)
            if expected and n != expected:
                raise IOError(f"short read {n}/{expected}")
            tmp.replace(dst)
            return
        except Exception as e:  # noqa: BLE001 - retry any transport error
            wait = 2 ** k
            print(f"  {dst.name}: {e}; retry in {wait}s", file=sys.stderr)
            time.sleep(wait)
    raise SystemExit(f"failed to fetch {url}")


def main(check_only: bool = False) -> int:
    SRC_DIR.mkdir(parents=True, exist_ok=True)
    bad = 0
    for name, (url, digest, lic, credit) in SOURCES.items():
        dst = SRC_DIR / name
        if not dst.exists() and not check_only:
            print(f"fetch {name} <- {url}")
            fetch(url, dst)
        if not dst.exists():
            print(f"MISSING {name}")
            bad += 1
            continue
        got = sha256(dst)
        ok = (not digest) or got == digest
        print(f"{'ok ' if ok else 'BAD'} {name}  sha256={got}  [{lic}]")
        if not ok:
            bad += 1
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main("--check" in sys.argv))

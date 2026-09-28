#!/usr/bin/env python3
"""Fetch the CC0 ambientCG texture sets used by the hero ship.

Run from anywhere (plain Python 3, no Blender needed):

    python3 production/blender/ship/fetch_textures.py

Downloads each set's 2K-JPG zip once, keeps only the maps the ship shaders use, and writes them to
production/cache/textures/<ID>/<ID>_<Map>.jpg (gitignored). Idempotent: sets already extracted are
skipped. Every set is listed with URL and licence in ASSETS_SHIP.md.
"""
from __future__ import annotations

import io
import hashlib
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
DEST = REPO / "production" / "cache" / "textures"

# id -> maps to keep (ambientCG map suffixes)
SETS = {
    "Foil002": ["Color", "NormalGL", "Roughness", "Displacement"],                 # gold crinkled MLI
    "Foil001": ["Color", "NormalGL", "Roughness", "Displacement"],                 # silver crinkled MLI
    "Metal009": ["Color", "NormalGL", "Roughness"],                                # brushed metal
    "SurfaceImperfections003": ["Color", "NormalGL", "Opacity"],                  # smudges / grime (decal set)
    "Scratches002": ["Color", "NormalGL", "Opacity"],                             # scratch mask (decal set)
}
URL = "https://ambientcg.com/get?file={id}_2K-JPG.zip"
UA = "TheLastSignal-fetch/1.0 (+https://github.com/Artemiy12A/the-last-signal)"


def _get(url: str, tries: int = 6) -> bytes:
    delay = 2.0
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=180) as r:
                data = r.read()
                n = r.headers.get("Content-Length")
                if n is not None and int(n) != len(data):
                    raise IOError(f"short read {len(data)} / {n}")
                return data
        except Exception as e:  # noqa: BLE001 - retry anything transient
            if k == tries - 1:
                raise
            print(f"  retry {k + 1} after error: {e}", flush=True)
            time.sleep(delay)
            delay *= 2
    raise RuntimeError("unreachable")


def fetch(set_id: str, maps: list[str]) -> None:
    out = DEST / set_id
    want = [out / f"{set_id}_{m}.jpg" for m in maps]
    if all(p.exists() and p.stat().st_size > 0 for p in want):
        print(f"{set_id}: cached")
        return
    url = URL.format(id=set_id)
    print(f"{set_id}: downloading {url}", flush=True)
    data = _get(url)
    sha = hashlib.sha256(data).hexdigest()
    out.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        names = z.namelist()
        for m in maps:
            name = f"{set_id}_2K-JPG_{m}.jpg"
            if name not in names:
                raise FileNotFoundError(f"{name} not in {set_id} zip: {names}")
            (out / f"{set_id}_{m}.jpg").write_bytes(z.read(name))
    (out / "SOURCE.txt").write_text(f"{url}\nsha256(zip)={sha}\nlicence=CC0 1.0 (ambientCG)\n")
    print(f"{set_id}: ok ({len(data) / 1e6:.1f} MB zip, sha256 {sha[:16]}...)")


def main() -> int:
    DEST.mkdir(parents=True, exist_ok=True)
    only = set(sys.argv[1:])
    for sid, maps in SETS.items():
        if only and sid not in only:
            continue
        fetch(sid, maps)
    return 0


if __name__ == "__main__":
    sys.exit(main())

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROD = ROOT / "production"
CACHE = PROD / "cache"
TRACER = PROD / "tracer" / "build" / "tracer"
BLENDER = Path("/opt/blender/blender-4.5.14-linux-x64/blender")
SKY_MAP = CACHE / "sky" / "mw_gal.exr"
STARS = CACHE / "sky" / "stars_tycho2.bin"
OUT = PROD / "out"

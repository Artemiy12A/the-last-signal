#!/usr/bin/env bash
# Install system + Python dependencies on Ubuntu 22.04/24.04 (also used by CI).
set -euo pipefail
SUDO=""; [ "$(id -u)" -ne 0 ] && SUDO="sudo"
$SUDO apt-get update -qq
DEBIAN_FRONTEND=noninteractive $SUDO apt-get install -y -qq --no-install-recommends \
  ffmpeg libegl1 libegl-mesa0 libgl1-mesa-dri libgl1 >/dev/null
python3 -m pip install --quiet -r "$(dirname "$0")/../requirements.txt"
python3 - <<'PY'
import moderngl
ctx = moderngl.create_standalone_context(backend="egl", require=330)
print("OpenGL:", ctx.info["GL_RENDERER"], ctx.info["GL_VERSION"])
PY
ffmpeg -hide_banner -version | head -1

"""Headless OpenGL renderer (moderngl + EGL, runs on Mesa llvmpipe in the cloud)."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

from .colour import blackbody_lut

ROOT = Path(__file__).resolve().parents[1]
SHADERS = Path(__file__).resolve().parent / "shaders"
ASSETS = ROOT / "assets"


def _read(name: str) -> str:
    return (SHADERS / name).read_text()


def create_context():
    import moderngl

    errors = []
    for backend in ("egl", None):
        try:
            kw = {"require": 330}
            if backend:
                kw["backend"] = backend
            return moderngl.create_standalone_context(**kw)
        except Exception as exc:  # pragma: no cover - depends on host GL
            errors.append(f"{backend}: {exc}")
    raise RuntimeError("could not create an OpenGL 3.3 context:\n" + "\n".join(errors))


@dataclass
class Quality:
    name: str
    out_w: int
    out_h: int
    fps: int
    samples: int         # jittered scene passes per frame
    step_k: float        # geodesic step factor (smaller = more accurate)
    max_steps: int
    crf: int
    x264_preset: str

    @property
    def active_h(self) -> int:
        # 2.39:1 scope picture inside the 16:9 frame, even number of lines
        return int(round(self.out_w / 2.39 / 2.0) * 2)


QUALITIES = {
    "draft": Quality("draft", 960, 540, 24, 1, 0.07, 320, 20, "veryfast"),
    "preview": Quality("preview", 1280, 720, 24, 2, 0.05, 420, 18, "medium"),
    "final": Quality("final", 1920, 1080, 24, 4, 0.035, 600, 14, "slow"),
}

# Jitter patterns (pixel offsets), rotated grid for 4 samples.
JITTER = {
    1: [(0.0, 0.0)],
    2: [(-0.25, -0.25), (0.25, 0.25)],
    3: [(-0.33, 0.1), (0.1, -0.33), (0.25, 0.3)],
    4: [(-0.125, -0.375), (0.375, -0.125), (0.125, 0.375), (-0.375, 0.125)],
    6: [(-0.25, -0.4), (0.25, -0.4), (-0.45, 0.0), (0.45, 0.0), (-0.2, 0.4), (0.2, 0.4)],
}


def _mat3(m: np.ndarray) -> tuple:
    """numpy row-major 3x3 -> GLSL column-major tuple."""
    return tuple(float(v) for v in np.asarray(m, dtype=np.float64).T.reshape(-1))


class Renderer:
    def __init__(self, q: Quality):
        import moderngl

        self.q = q
        self.mgl = moderngl
        self.ctx = create_context()
        ctx = self.ctx
        self.gl_info = ctx.info.get("GL_RENDERER", "?")

        vert = _read("fullscreen.vert")
        self.p_scene = ctx.program(vertex_shader=vert, fragment_shader=_read("scene.frag"))
        self.p_down = ctx.program(vertex_shader=vert, fragment_shader=_read("bloom_down.frag"))
        self.p_up = ctx.program(vertex_shader=vert, fragment_shader=_read("bloom_up.frag"))
        self.p_streak = ctx.program(vertex_shader=vert, fragment_shader=_read("streak.frag"))
        self.p_comp = ctx.program(vertex_shader=vert, fragment_shader=_read("composite.frag"))

        tri = np.array([-1, -1, 3, -1, -1, 3], dtype="f4")
        self.vbo = ctx.buffer(tri.tobytes())
        self.vaos = {
            p: ctx.vertex_array(p, [(self.vbo, "2f", "in_pos")])
            for p in (self.p_scene, self.p_down, self.p_up, self.p_streak, self.p_comp)
        }

        # --- static textures
        sky_img = Image.open(ASSETS / "sky" / "milkyway_diffuse.jpg").convert("RGB")
        meta = json.loads((ASSETS / "sky" / "milkyway_diffuse.json").read_text())
        self.sky_scale = float(meta["scale"])
        self.sky = ctx.texture(sky_img.size, 3, np.asarray(sky_img).tobytes())
        self.sky.build_mipmaps()
        self.sky.filter = (moderngl.LINEAR_MIPMAP_LINEAR, moderngl.LINEAR)
        self.sky.repeat_x = True
        self.sky.repeat_y = False
        self.sky.anisotropy = 8.0

        lut = blackbody_lut(512).astype("f4")
        self.bb = ctx.texture((lut.shape[0], 1), 3, lut.tobytes(), dtype="f4")
        self.bb.filter = (moderngl.LINEAR, moderngl.LINEAR)
        self.bb.repeat_x = False

        # --- render targets
        self.aw, self.ah = q.out_w, q.active_h
        self.accum = ctx.texture((self.aw, self.ah), 4, dtype="f4")
        self.accum.filter = (moderngl.LINEAR, moderngl.LINEAR)
        self.accum.repeat_x = self.accum.repeat_y = False
        self.fbo_accum = ctx.framebuffer([self.accum])

        self.levels = []
        w, h = self.aw, self.ah
        for _ in range(7):
            w, h = max(w // 2, 2), max(h // 2, 2)
            down = ctx.texture((w, h), 4, dtype="f2")
            up = ctx.texture((w, h), 4, dtype="f2")
            for t in (down, up):
                t.filter = (moderngl.LINEAR, moderngl.LINEAR)
                t.repeat_x = t.repeat_y = False
            self.levels.append((down, ctx.framebuffer([down]), up, ctx.framebuffer([up]), (w, h)))

        sw, sh = self.levels[1][4]
        self.streak = []
        for _ in range(2):
            t = ctx.texture((sw, sh), 4, dtype="f2")
            t.filter = (moderngl.LINEAR, moderngl.LINEAR)
            t.repeat_x = t.repeat_y = False
            self.streak.append((t, ctx.framebuffer([t])))

        self.text = ctx.texture((q.out_w, q.out_h), 1, dtype="f1")
        self.text.filter = (moderngl.LINEAR_MIPMAP_LINEAR, moderngl.LINEAR)
        self.text.repeat_x = self.text.repeat_y = False
        self._text_key = None
        self._set_text(np.zeros((q.out_h, q.out_w), np.uint8), key="empty")

        self.out = ctx.texture((q.out_w, q.out_h), 3, dtype="f1")
        self.fbo_out = ctx.framebuffer([self.out])

    # ------------------------------------------------------------------ utils
    @staticmethod
    def _set(prog, values: dict):
        for k, v in values.items():
            u = prog.get(k, None)
            if u is None:
                continue
            if isinstance(v, np.ndarray):
                v = tuple(float(x) for x in v.reshape(-1))
            u.value = v

    def _set_text(self, img: np.ndarray, key):
        if key == self._text_key:
            return
        # flip vertically: GL textures start at the bottom row
        self.text.write(np.ascontiguousarray(img[::-1]).tobytes())
        self.text.build_mipmaps()
        self._text_key = key

    # ------------------------------------------------------------------ frame
    def render(self, P: dict, text_img: np.ndarray | None = None, text_key=None) -> bytes:
        mgl = self.mgl
        ctx = self.ctx
        q = self.q

        # ---------------- scene: jittered passes accumulated additively
        cam_rot = P["cam_rot"]
        tan_half = float(np.tan(np.radians(P["fov"]) * 0.5))
        pix_ang = 2.0 * tan_half / self.ah
        jit = JITTER[q.samples]
        self.sky.use(0)
        self.bb.use(1)
        common = {
            "uRes": (float(self.aw), float(self.ah)),
            "uCamPos": tuple(P["cam_pos"]),
            "uCamRot": _mat3(cam_rot),
            "uTanHalfFovY": tan_half,
            "uPixelAngle": pix_ang,
            "uTime": P["t"],
            "uBH": P["bh"],
            "uStepK": q.step_k,
            "uMaxSteps": q.max_steps,
            "uEscapeR": max(float(np.linalg.norm(P["cam_pos"])) * 1.3, 60.0),
            "uDiskGain": P["disk_gain"],
            "uDiskIgnite": P["disk_ignite"],
            "uDiskTime": P["disk_time"],
            "uDiskTemp": P["disk_temp"],
            "uDoppler": P["doppler"],
            "uDiskIn": P["disk_in"],
            "uDiskOut": P["disk_out"],
            "uGlow": P["glow"],
            "uRingBoost": P["ring_boost"],
            "uSky": 0,
            "uBB": 1,
            "uSkyScale": self.sky_scale,
            "uSkyRot": _mat3(P["sky_rot"]),
            "uSkyGain": P["sky_gain"],
            "uStarGain": P["star_gain"],
            "uShip": P["ship"],
            "uShipPos": tuple(P["ship_pos"]),
            "uShipRot": _mat3(P["ship_rot"]),
            "uShipScale": P["ship_scale"],
            "uKeyDir": tuple(P["key_dir"]),
            "uKeyCol": tuple(P["key_col"]),
            "uFillCol": tuple(P["fill_col"]),
            "uRimCol": tuple(P["rim_col"]),
            "uBeacon": P["beacon"],
            "uEngine": P["engine"],
            "uWeight": 1.0 / len(jit),
        }
        self.fbo_accum.use()
        self.fbo_accum.clear(0.0, 0.0, 0.0, 0.0)
        if P.get("scene", True):
            self._set(self.p_scene, common)
            ctx.enable(mgl.BLEND)
            ctx.blend_func = (mgl.ONE, mgl.ONE)
            for i, (jx, jy) in enumerate(jit):
                self._set(self.p_scene, {"uJitter": (jx, jy), "uPass": float(i)})
                self.vaos[self.p_scene].render(mgl.TRIANGLES)
            ctx.disable(mgl.BLEND)

        # ---------------- bloom pyramid
        src, src_size = self.accum, (self.aw, self.ah)
        for i, (down, fbo, _, _, size) in enumerate(self.levels):
            fbo.use()
            ctx.viewport = (0, 0, *size)
            src.use(0)
            self._set(self.p_down, {
                "uSrc": 0,
                "uSrcTexel": (1.0 / src_size[0], 1.0 / src_size[1]),
                "uFirst": 1 if i == 0 else 0,
                "uThreshold": P["bloom_threshold"],
                "uKnee": 0.6,
            })
            self.vaos[self.p_down].render(mgl.TRIANGLES)
            src, src_size = down, size
        low = self.levels[-1][0]
        low_size = self.levels[-1][4]
        for i in range(len(self.levels) - 2, -1, -1):
            down, _, up, fbo_up, size = self.levels[i]
            fbo_up.use()
            ctx.viewport = (0, 0, *size)
            low.use(0)
            down.use(1)
            self._set(self.p_up, {
                "uLow": 0, "uCur": 1,
                "uLowTexel": (1.0 / low_size[0], 1.0 / low_size[1]),
                "uRadius": 1.0,
                "uMix": P["bloom_spread"],
            })
            self.vaos[self.p_up].render(mgl.TRIANGLES)
            low, low_size = up, size
        bloom_tex = self.levels[0][2]

        # ---------------- anamorphic streak
        s_src = self.levels[1][0]
        size = self.levels[1][4]
        spreads = (1.0, 3.5, 10.0)
        for k, sp in enumerate(spreads):
            dst_tex, dst_fbo = self.streak[k % 2]
            dst_fbo.use()
            ctx.viewport = (0, 0, *size)
            s_src.use(0)
            self._set(self.p_streak, {
                "uSrc": 0,
                "uTexel": (1.0 / size[0], 1.0 / size[1]),
                "uSpread": sp,
                "uThreshold": P["streak_threshold"] if k == 0 else 0.0,
            })
            self.vaos[self.p_streak].render(mgl.TRIANGLES)
            s_src = dst_tex
        streak_tex = s_src

        # ---------------- composite
        if text_img is not None:
            self._set_text(text_img, text_key if text_key is not None else id(text_img))
        else:
            self._set_text(np.zeros((q.out_h, q.out_w), np.uint8), "empty")
        self.fbo_out.use()
        ctx.viewport = (0, 0, q.out_w, q.out_h)
        self.accum.use(0)
        bloom_tex.use(1)
        streak_tex.use(2)
        self.text.use(3)
        self._set(self.p_comp, {
            "uScene": 0, "uBloom": 1, "uStreak": 2, "uText": 3,
            "uOutRes": (float(q.out_w), float(q.out_h)),
            "uActiveH": float(self.ah),
            "uExposure": P["exposure"],
            "uBloomGain": P["bloom_gain"],
            "uStreakGain": P["streak_gain"],
            "uStreakTint": tuple(P["streak_tint"]),
            "uCA": P["ca"],
            "uVignette": P["vignette"],
            "uGrain": P["grain"],
            "uFade": P["fade"],
            "uFlash": P["flash"],
            "uGlitch": P["glitch"],
            "uFrame": float(P["frame"]),
            "uSaturation": P["saturation"],
            "uContrast": P["contrast"],
            "uLift": tuple(P["lift"]),
            "uGain": tuple(P["gain"]),
            "uTextOpacity": P["text_opacity"],
            "uTextColor": tuple(P["text_color"]),
            "uTextGlow": P["text_glow"],
            "uTextSweep": P["text_sweep"],
            "uTextFlicker": P["text_flicker"],
        })
        self.vaos[self.p_comp].render(mgl.TRIANGLES)
        data = self.fbo_out.read(components=3, alignment=1)
        # flip to top-down rows for image/video output
        arr = np.frombuffer(data, np.uint8).reshape(q.out_h, q.out_w, 3)[::-1]
        return np.ascontiguousarray(arr).tobytes()

    def release(self):
        self.ctx.release()


def configure_threads():
    """llvmpipe uses one thread per core by default; make it explicit."""
    n = os.cpu_count() or 2
    os.environ.setdefault("LP_NUM_THREADS", str(n))
    os.environ.setdefault("EGL_PLATFORM", "surfaceless")

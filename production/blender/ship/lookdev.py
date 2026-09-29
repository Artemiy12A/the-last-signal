"""Review stills for the LSV-7 hero ship.

    blender -b --factory-startup -P production/blender/ship/lookdev.py -- [--shots 1,2,3,4,5]
            [--width 1280] [--height 536] [--samples 64] [--out production/blender/ship/review]

Writes <out>/0N_<name>.jpg (AgX, quality 88) and prints render times. Lighting is a synthetic
disk-like env probe (ship_api.make_test_probe) plus a hard warm key sun, standing in for the tracer's
probes until they exist.
"""
from __future__ import annotations

import argparse
import math
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import bpy  # noqa: E402
import numpy as np  # noqa: E402

import ship_api as S  # noqa: E402
import ship_build as SB  # noqa: E402
import ship_materials as SM  # noqa: E402

CACHE = HERE.parents[1] / "cache" / "ship_lookdev"


def D(x, y, z):
    """Design coordinates -> world (SHIP_ROOT at the origin)."""
    return (x, y - SB.COM_Y, z)


def azel(v):
    v = np.asarray(v, float)
    v = v / np.linalg.norm(v)
    return math.degrees(math.atan2(v[1], v[0])), math.degrees(math.asin(v[2]))


def probe(name, key_dir, intensity, fill):
    CACHE.mkdir(parents=True, exist_ok=True)
    p = CACHE / f"{name}.exr"
    az, el = azel(key_dir)
    S.make_test_probe(p, disk_az_deg=az, disk_el_deg=el, disk_intensity=intensity, fill=fill)
    return p


def clear_lights():
    for ob in list(bpy.data.objects):
        if ob.name.startswith(("TLS_", "Fill", "LD_")):
            bpy.data.objects.remove(ob, do_unlink=True)


SHOTS = {}


def shot(n, name):
    def deco(f):
        SHOTS[n] = (name, f)
        return f
    return deco


@shot(1, "hero_34_medium")
def s1(root):
    key = (1.0, 0.1, 0.42)
    S.set_controls(root, beacon=0, nav=1, running=1, engine=0, interior=0)
    S.setup_world_from_equirect(probe("p1", key, 6.0, (0.002, 0.003, 0.007)), strength=1.0)
    S.add_key_light(key, (1.0, 0.80, 0.58), 4.5, 0.4)
    S.add_key_light((-0.4, -0.3, -0.85), (0.45, 0.6, 1.0), 0.12, 25.0, name="TLS_Fill")
    S.set_camera(D(31, 55, 15), D(0.0, 16.5, -1.5), hfov_deg=41, fstop=None)
    return 0.0


@shot(2, "macro_mli_beacon")
def s2(root):
    key = (0.55, 0.5, 0.67)
    S.set_controls(root, beacon=1, nav=1, running=1, engine=0, interior=0)
    S.setup_world_from_equirect(probe("p2", key, 6.0, (0.002, 0.003, 0.007)), strength=1.0)
    S.add_key_light(key, (1.0, 0.78, 0.55), 2.6, 0.4)
    S.add_key_light((0.2, -0.9, 0.25), (1.0, 0.7, 0.45), 0.6, 2.0, name="TLS_Rim")
    S.set_camera(D(-0.05, 14.0, 2.60), D(-0.2, 11.4, 2.555), hfov_deg=44, fstop=2.8, focus_dist=1.66,
                 aperture_ratio=2.0, clip_start=0.01)
    return -0.6


@shot(3, "silhouette_far")
def s3(root):
    S.set_controls(root, beacon=0, nav=1, running=1, engine=0, interior=0, dish_az_deg=-28, dish_el_deg=10)
    S.setup_world_color((0, 0, 0), 0)
    me = bpy.data.meshes.new("LD_Backdrop")
    s = 4000.0
    me.from_pydata([(-600, -s, -s * 0.5), (-600, s, -s * 0.5), (-600, s, s * 0.5), (-600, -s, s * 0.5)], [],
                   [(0, 1, 2, 3)])
    ob = bpy.data.objects.new("LD_Backdrop", me)
    bpy.context.scene.collection.objects.link(ob)
    me.materials.append(SM.backdrop("LD_Backdrop_Mat", (1.0, 0.40, 0.09), 0.55))
    S.set_camera((800, -150, 110), (0, 0, 0), hfov_deg=40, clip_end=5000)
    return 0.0


@shot(4, "aft_34_engines")
def s4(root):
    key = (0.9, 0.55, 0.5)
    S.set_controls(root, beacon=0, nav=1, running=1, engine=1, interior=0)
    S.setup_world_from_equirect(probe("p4", key, 6.0, (0.002, 0.003, 0.007)), strength=1.0)
    S.add_key_light(key, (1.0, 0.8, 0.58), 3.5, 0.4)
    S.add_key_light((-0.5, -0.2, -0.8), (0.45, 0.6, 1.0), 0.1, 25.0, name="TLS_Fill")
    S.set_camera(D(-24, -54, -10), D(0.5, -23.0, 0.5), hfov_deg=42)
    return 0.0


@shot(5, "dish_slewed")
def s5(root):
    key = (0.35, 0.75, 0.55)
    S.set_controls(root, beacon=0, nav=1, running=1, engine=0, interior=1, dish_az_deg=38, dish_el_deg=24)
    S.setup_world_from_equirect(probe("p5", key, 6.0, (0.002, 0.003, 0.007)), strength=1.0)
    S.add_key_light(key, (1.0, 0.8, 0.58), 4.0, 0.4)
    S.add_key_light((0.6, -0.3, -0.7), (0.45, 0.6, 1.0), 0.1, 25.0, name="TLS_Fill")
    S.set_camera(D(15.5, 33.5, 9.5), D(-0.8, 24.5, 0.8), hfov_deg=44)
    return 0.0


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--shots", default="1,2,3,4,5")
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--height", type=int, default=536)
    ap.add_argument("--samples", type=int, default=64)
    ap.add_argument("--out", default=str(HERE / "review"))
    ap.add_argument("--suffix", default="")
    a = ap.parse_args(argv)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    S.reset_scene()
    t0 = time.time()
    root = S.build_ship()
    print(f"[lookdev] build {time.time() - t0:.1f}s, polycount {S.polycount()}")
    times = {}
    for n in [int(x) for x in a.shots.split(",")]:
        name, fn = SHOTS[n]
        clear_lights()
        for ob in list(bpy.data.objects):
            if ob.name.startswith("LD_"):
                bpy.data.objects.remove(ob, do_unlink=True)
        exposure = fn(root)
        S.setup_render(a.width, a.height, a.samples, denoise=True, motion_blur=False, transparent=False)
        path = out / f"0{n}_{name}{a.suffix}.jpg"
        S.setup_review_output(path, 88, exposure)
        t = time.time()
        S.render()
        times[name] = time.time() - t
        print(f"[lookdev] shot {n} {name}: {times[name]:.1f}s -> {path}")
    print("[lookdev] times", {k: round(v, 1) for k, v in times.items()})


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    main(argv)

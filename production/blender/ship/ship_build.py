"""LSV-7 hero ship assembly (procedural, deterministic).

Design frame (metres): +Y bow, +Z dorsal, +X starboard. Parts are authored in design coordinates and
shifted by a single offset (SHIP_Hull empty) so that the SHIP_ROOT origin sits at the estimated
centre of mass (see MASS_TABLE). Call build(); ship_api.build_ship() wraps it.
"""
from __future__ import annotations

import math
from pathlib import Path

import bpy
import numpy as np

import ship_materials as SM
from ship_geo import (MeshBuilder, frame_z, mat4, polar, rot_x, rot_z, surface_frame, text_geometry, trans,
                      unit, along_y)

REPO = Path(__file__).resolve().parents[3]
FONT_SANS = str(REPO / "assets" / "fonts" / "Jost-Variable.ttf")
FONT_MONO = str(REPO / "assets" / "fonts" / "IBMPlexMono-Light.ttf")

C22 = math.cos(math.radians(22.5))
T22 = math.tan(math.radians(22.5))
OCT = math.radians(22.5)          # lathe phase that puts octagon faces at 0, 45, 90 ... degrees

# ------------------------------------------------------------------------------------ layout
BUS_Y0, BUS_Y1, BUS_R = 12.0, 21.5, 2.6
BUS_A = BUS_R * C22
SVC_Y0, SVC_Y1, SVC_R = 9.8, 12.0, 2.8
SVC_A = SVC_R * C22
NOSE_Y1, NOSE_R1 = 22.3, 1.5
AZ_PIVOT = np.array([0.0, 26.0, 0.0])      # Dish_Az (about local Z) and Dish_El (about local X) pivot
DISH_R, DISH_F, DISH_V, DISH_T = 4.0, 2.8, 1.2, 0.07
TRUSS_Y0, TRUSS_Y1, TRUSS_RC, TRUSS_BAYS = -19.2, 8.0, 1.39, 17
TRI = (90.0, 210.0, 330.0)
SPH_Y, SPH_R, SPH_RAD = 3.4, 1.45, 2.9
COPV_Y0, COPV_Y1, COPV_R, COPV_RAD = -5.4, 0.6, 0.8, 2.55
RAD_Y0, RAD_Y1, RAD_TIP0, RAD_TIP1, RAD_X0, RAD_X1 = -7.4, -18.6, -8.6, -17.4, 1.95, 7.3
RAD_PHI = (28.0, 152.0, -28.0, -152.0)
SHIELD_Y0, SHIELD_Y1, SHIELD_R0, SHIELD_R1 = -19.5, -22.3, 3.0, 1.45
PPU_Y0, PPU_Y1, PPU_R = -24.9, -26.2, 2.3
THR_PHI, THR_RAD = (90.0, 210.0, 330.0), 1.3
THR_GRID_Z = 1.13                           # grid plane distance downstream of the thrust plate

# rough mass budget (kg, design-Y) used to put the root origin at the centre of mass
MASS_TABLE = [
    ("bus + service ring", 3000, 15.5), ("dish + gimbal", 400, 27.0), ("xenon spheres (full)", 10000, SPH_Y),
    ("xenon COPVs (full)", 6000, -2.4), ("spine truss", 1500, -5.6), ("radiators", 2000, -13.0),
    ("shadow shield", 4000, -21.0), ("reactor", 2500, -23.6), ("PPU + thrusters", 2000, -25.6),
]
COM_Y = sum(m * y for _, m, y in MASS_TABLE) / sum(m for _, m, _ in MASS_TABLE)


def ss(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


# ------------------------------------------------------------------------------------ text helpers


def place_text(mb, body, size, origin, u, v, mat, font=FONT_SANS, align="CENTER", spacing=1.0):
    """Flat text at `origin`, reading along u, glyph-up along v (normal = u x v)."""
    u, v = unit(u), unit(v)
    verts, faces = text_geometry(body, font, size, align, spacing)
    if not faces:
        return
    xf = mat4(origin, u, v, np.cross(u, v))
    mb.add(verts, faces, mat, xf, flat=True)


def place_text_cyl(mb, body, size, xf_axis, radius, theta0, mat, font=FONT_SANS, z0=0.0):
    """Text wrapped on a cylinder (axis = local +Z of xf_axis), reading along +Z."""
    verts, faces = text_geometry(body, font, size, "CENTER", 1.0)
    if not faces:
        return
    x, y = verts[:, 0], verts[:, 1]
    r = radius + 0.0012
    th = theta0 - y / r
    loc = np.stack([r * np.cos(th), r * np.sin(th), z0 + x], -1)
    mb.add(loc, faces, mat, xf_axis, flat=True)


def trefoil(mb, xf, R, mat_bg, mat_fg):
    """Radiation trefoil on a yellow plate (local XY, +Z out)."""
    mb.box((R * 6.4, R * 6.4, 0.003), mat_bg, xf, center=(0, 0, 0.0015), bevel=0.001)
    top = xf @ trans(0, 0, 0.0034)
    mb.lathe([(R, 0), (0, 0)], 20, mat_fg, top)
    for k in range(3):
        a = math.radians(90 + 120 * k)
        mb.lathe([(R * 2.6, 0), (R * 1.5, 0)], 8, mat_fg, top, arc=(a - math.radians(30), a + math.radians(30)))


# ------------------------------------------------------------------------------------ blankets


def wrinkle_sphere(V, c, rng, amp=0.012):
    """Radial blanket wrinkles on an MLI-wrapped sphere (soft folds + a few sharper creases)."""
    P = V - c
    r = np.linalg.norm(P, axis=1, keepdims=True)
    n = P / np.maximum(r, 1e-9)
    disp = np.zeros(len(V))
    for _ in range(9):
        k = unit(rng.normal(size=3)) * rng.uniform(3.0, 9.0)
        disp += rng.uniform(0.3, 1.0) * np.sin(P @ k + rng.uniform(0, 6.3))
    for _ in range(4):
        k = unit(rng.normal(size=3)) * rng.uniform(1.5, 4.0)
        disp += 1.6 * (1 - np.abs(np.sin(P @ k + rng.uniform(0, 6.3)))) ** 6
    return c + n * (r + amp * disp[:, None] / 3.0)


def blanket_height(w, h, rng, puff=0.03, fold=0.0042):
    k = 10
    ang = rng.uniform(0, math.pi, k)
    fr = rng.uniform(5.0, 17.0, k)
    ph = rng.uniform(0, 2 * math.pi, k)
    am = fold * rng.uniform(0.3, 1.0, k)
    ang2 = rng.uniform(0, math.pi, 3)
    fr2 = rng.uniform(1.0, 2.5, 3)
    ph2 = rng.uniform(0, 2 * math.pi, 3)
    am2 = fold * rng.uniform(0.5, 1.4, 3)
    cx, cy = rng.uniform(0.3, 0.7) * w, rng.uniform(0.3, 0.7) * h

    def f(U, V):
        du, dv = np.minimum(U, w - U), np.minimum(V, h - V)
        d = np.minimum(du, dv)
        e = ss((d - 0.035) / 0.16)
        pil = puff * (0.45 + 0.55 * np.exp(-(((U - cx) / w) ** 2 + ((V - cy) / h) ** 2) * 3.0))
        fo = sum(am[i] * np.sin(fr[i] * (math.cos(ang[i]) * U + math.sin(ang[i]) * V) + ph[i]) for i in range(k))
        cr = sum(am2[j] * (1 - np.abs(np.sin(fr2[j] * (math.cos(ang2[j]) * U + math.sin(ang2[j]) * V) + ph2[j]))) ** 5
                 for j in range(3))
        zin = 0.0035 + e * np.maximum(pil + fo + cr, 0.25 * pil)
        zed = np.interp(d, [0.0, 0.012, 0.035], [-0.010, 0.0025, 0.0035])
        return np.where(d < 0.035, zed, zin)
    return f


def edge_spacing(L, step=0.07):
    inner = np.linspace(0.05, L - 0.05, max(2, int((L - 0.1) / step) + 1))
    return np.concatenate([[0.0, 0.006, 0.012, 0.024, 0.035], inner, L - np.array([0.035, 0.024, 0.012, 0.006, 0.0])])


def blanket(mb, xf, w, h, kind, rng, puff=0.032):
    mat = {"gold": "mli_gold", "silver": "mli_silver", "black": "mli_black"}[kind]
    rot = float(rng.integers(0, 4)) * math.pi / 2 + rng.uniform(-0.25, 0.25)
    mb.grid(w, h, 0, 0, mat, xf, height=blanket_height(w, h, rng, puff), uv_off=tuple(rng.uniform(0, 20, 2)),
            uv_rot=rot, us=edge_spacing(w), vs=edge_spacing(h))


def tape_strip(mb, xf, w, h, kind, z=0.0056):
    mb.box((w, h, 0.0008), "tape_gold" if kind == "gold" else "tape_silver", xf, center=(0, 0, z), bevel=0.0003)


# ------------------------------------------------------------------------------------ small parts


def rcs_quad(B, xf, label=None):
    d = B["details"]
    d.box((0.12, 0.12, 0.26), "paint_offwhite", xf, center=(0, 0, 0.13), bevel=0.008)
    d.box((0.30, 0.30, 0.22), "paint_offwhite", xf, center=(0, 0, 0.36), bevel=0.012, segments=2)
    d.box((0.31, 0.31, 0.02), "alu_anod", xf, center=(0, 0, 0.25), bevel=0.004)
    for bx in (-0.12, 0.12):
        for by in (-0.12, 0.12):
            d.bolt(xf @ trans(bx, by, 0.47), "alu", r=0.007, h=0.005)
    bell = [(0.010, 0.0), (0.016, 0.012), (0.024, 0.04), (0.036, 0.085), (0.042, 0.11)]
    for axis in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0)):
        a = np.array(axis, float)
        base = np.array([0, 0, 0.36]) + a * 0.15
        m = xf @ frame_z(base, a)
        d.cylinder(0.03, 0.03, "alu_anod", m, segs=12, chamfer=0.004)
        d.lathe(bell, 16, "nozzle", m @ trans(0, 0, 0.028))
    if label:
        o = xf @ np.array([0.0, -0.1505, 0.36, 1.0])
        place_text(B["stencils"], label, 0.032, o[:3], xf[:3, 0], xf[:3, 2], "stencil_black", FONT_MONO)


def lamp_unit(B, xf, lamp_mat, r=0.035, mast=0.0, housing="paint_offwhite"):
    """Small light: base + optional mast + housing + lens dome. Returns lens centre (design coords)."""
    d, L = B["details"], B["lamps"]
    d.box((r * 3.2, r * 3.2, 0.012), housing, xf, center=(0, 0, 0.006), bevel=0.002)
    z = 0.012
    if mast > 0:
        d.cylinder(r * 0.45, mast, "alu_anod", xf, segs=10, z0=z)
        z += mast
    d.cylinder(r * 1.25, r * 0.9, housing, xf, segs=16, chamfer=r * 0.15, z0=z)
    z += r * 0.9
    d.cylinder(r * 1.05, 0.004, "alu_anod", xf, segs=16, z0=z)
    L.sphere(r, lamp_mat, xf @ trans(0, 0, z), segs=20, rings=10, squash=0.9)
    c = xf @ np.array([0, 0, z + r * 0.35, 1.0])
    return c[:3]


# ------------------------------------------------------------------------------------ sections


def build_bus(B, rng, lights):
    h, d, st = B["hull"], B["details"], B["stencils"]
    ay = along_y()
    # dark structure core (visible only in seams)
    rc = (BUS_A - 0.012) / C22
    h.lathe([(0, BUS_Y0 + 0.01), (rc, BUS_Y0 + 0.01), (rc, BUS_Y1 - 0.01), (0, BUS_Y1 - 0.01)], 8, "paint_dark", ay,
            phase=OCT)
    # corner longerons (anodised angle)
    for k in range(8):
        phi = 22.5 + 45 * k
        n = polar(phi, 1.0, 0.0)
        xf = frame_z(polar(phi, BUS_R - 0.012, BUS_Y0), (0, 1, 0), n)
        h.box((0.05, 0.08, BUS_Y1 - BUS_Y0 + 0.02), "alu_anod", xf, center=(0, 0, (BUS_Y1 - BUS_Y0) / 2), bevel=0.008)
    faces = {
        0: [(12.0, 13.1, "gold"), (13.1, 20.5, "equip"), (20.5, 21.5, "gold")],
        1: [(12.0, 21.5, "gold")], 2: [(12.0, 21.5, "gold")], 3: [(12.0, 21.5, "gold")],
        4: [(12.0, 15.1, "gold"), (15.1, 18.3, "dock"), (18.3, 21.5, "gold")],
        5: [(12.0, 21.5, "silver")], 6: [(12.0, 21.5, "silver")], 7: [(12.0, 21.5, "gold")],
    }
    bw = 2 * BUS_A * T22 - 0.1
    for k, spans in faces.items():
        phi = 45.0 * k
        for (y0, y1, kind) in spans:
            L = y1 - y0
            if kind in ("gold", "silver", "black"):
                n = max(1, int(round(L / 2.4)))
                hb = L / n
                for i in range(n):
                    yc = y0 + (i + 0.5) * hb
                    blanket(h, surface_frame(phi, BUS_A, yc), bw, hb, kind, rng)
                for i in range(n + 1):
                    tape_strip(h, surface_frame(phi, BUS_A, y0 + i * hb), bw + 0.02, 0.05, kind)
            else:
                build_panel_face(B, rng, phi, y0, y1, kind, bw, lights)
    # nose: silver MLI frustum, white front plate, mast flange
    h.lathe([(BUS_R, BUS_Y1), (NOSE_R1 + 0.06, NOSE_Y1 - 0.03), (NOSE_R1, NOSE_Y1)], 8, "mli_silver", ay, phase=OCT)
    h.lathe([(NOSE_R1 + 0.02, NOSE_Y1 - 0.005), (NOSE_R1 + 0.02, NOSE_Y1 + 0.03), (0.0, NOSE_Y1 + 0.03)], 8,
            "paint_white", ay, phase=OCT)
    for k in range(8):
        phi = 22.5 + 45 * k
        xf = frame_z(polar(phi, NOSE_R1 * 0.93, NOSE_Y1 + 0.03), (0, 1, 0), polar(phi, 1, 0))
        d.bolt(xf, "alu", r=0.012, h=0.009)
    for k in (0, 2, 4, 6):
        phi = 22.5 + 45 * k
        p = polar(phi, NOSE_R1 * 0.8, NOSE_Y1 + 0.03)
        lamp_unit(B, frame_z(p, (0, 1, 0), polar(phi, 1, 0)), "running", r=0.026)
    # handrails along the dorsal face
    for s in (-0.55, 0.55):
        p0 = surface_frame(90, BUS_A + 0.02, 13.3) @ np.array([s, 0, 0, 1.0])
        p1 = surface_frame(90, BUS_A + 0.02, 16.2) @ np.array([s, 0, 0, 1.0])
        d.handrail(p0[:3], p1[:3], (0, 0, 1), "gold_anod", "alu_anod", bolt_mat="alu")
    # handrails flanking the hatch
    for phi in (135, 225):
        f0 = surface_frame(phi, BUS_A + 0.02, 15.0) @ np.array([0, 0, 0, 1.0])
        f1 = surface_frame(phi, BUS_A + 0.02, 18.4) @ np.array([0, 0, 0, 1.0])
        d.handrail(f0[:3], f1[:3], polar(phi, 1, 0), "gold_anod", "alu_anod", bolt_mat="alu")
    # grapple fixture (dorsal)
    gxf = surface_frame(90, BUS_A - 0.004, 17.6)
    d.cylinder(0.34, 0.045, "paint_white", gxf, segs=40, chamfer=0.006)
    d.bolt_ring(gxf @ trans(0, 0, 0.045), 0.29, 12, "alu", r=0.008, h=0.006)
    d.cylinder(0.032, 0.30, "alu", gxf, segs=16, z0=0.045)
    d.sphere(0.05, "alu", gxf @ trans(0, 0, 0.36), segs=16, rings=8)
    for k in range(3):
        a = math.radians(90 + 120 * k)
        d.box((0.05, 0.16, 0.09), "alu_anod", gxf @ rot_z(a) @ trans(0, 0.15, 0.09), bevel=0.01)
    for a in (0, math.pi / 2):
        d.box((0.34, 0.03, 0.004), "stencil_black", gxf @ rot_z(a), center=(0.0, 0, 0.047))
    place_text(st, "GF-1", 0.05, (gxf @ np.array([0.0, -0.44, 0.001, 1.0]))[:3] + np.array([0, 0, BUS_A * 0 + 0.028]),
               (1, 0, 0), (0, 1, 0), "stencil_black", FONT_MONO)
    # star trackers (dorsal-starboard face near the nose)
    for i, y in enumerate((20.35, 19.55)):
        sxf = surface_frame(45, BUS_A - 0.006, y)
        d.box((0.28, 0.30, 0.22), "paint_offwhite", sxf, center=(0, 0, 0.11), bevel=0.012, segments=2)
        for bx in (-0.12, 0.12):
            for by in (-0.13, 0.13):
                d.bolt(sxf @ trans(bx, by, 0.22), "alu", r=0.006, h=0.005)
        axis = unit(sxf[:3, 2] * 0.85 + np.array([0, 0.5, 0.0]) + sxf[:3, 0] * (0.25 if i else -0.25))
        o = (sxf @ np.array([0, 0, 0.22, 1.0]))[:3]
        bxf = frame_z(o, axis)
        d.lathe([(0.075, 0), (0.075, 0.05), (0.17, 0.36), (0.162, 0.362), (0.066, 0.055), (0.066, 0.03)], 32,
                "black", bxf)
        d.cylinder(0.068, 0.03, "lens", bxf, segs=24)
        place_text(st, f"STR-{i + 1}", 0.028, (sxf @ np.array([0.0, -0.1505, 0.12, 1.0]))[:3],
                   -sxf[:3, 0], sxf[:3, 2], "stencil_black", FONT_MONO)
    # ventral optical-nav camera pod
    pxf = surface_frame(270, BUS_A - 0.006, 19.9)
    d.box((0.5, 0.7, 0.36), "paint_offwhite", pxf, center=(0, 0, 0.18), bevel=0.015, segments=2)
    d.box((0.52, 0.72, 0.03), "alu_anod", pxf, center=(0, 0, 0.02), bevel=0.004)
    axis = unit(pxf[:3, 2] * 0.55 + np.array([0, 0.85, 0]))
    cxf = frame_z((pxf @ np.array([0, 0.2, 0.24, 1.0]))[:3], axis)
    d.cylinder(0.13, 0.42, "paint_dark", cxf, segs=32, chamfer=0.01)
    d.lathe([(0.135, 0.42), (0.17, 0.62), (0.162, 0.622), (0.118, 0.43)], 32, "black", cxf)
    d.cylinder(0.105, 0.43, "lens", cxf, segs=24)
    for i in range(3):
        B["interior"].box((0.012, 0.012, 0.004), "interior", pxf, center=(-0.18 + 0.03 * i, -0.3505, 0.30))
    place_text(st, "OPNAV-2", 0.03, (pxf @ np.array([0.1, -0.3505, 0.2, 1.0]))[:3], -pxf[:3, 0], pxf[:3, 2],
               "stencil_black", FONT_MONO)
    # whip antennas at the aft corners
    for phi, tilt in ((112.5, 1.0), (292.5, -1.0)):
        base = polar(phi, BUS_R + 0.02, 12.35)
        n = polar(phi, 1, 0)
        d.cylinder(0.045, 0.1, "paint_white", frame_z(base, n), segs=12, chamfer=0.008)
        dirv = unit(n * 0.8 + np.array([0, -0.55, 0]))
        d.tube(base + n * 0.1, base + n * 0.1 + dirv * 3.4, 0.007, "gold_anod", segs=6)
        d.sphere(0.012, "gold_anod", trans(*(base + n * 0.1 + dirv * 3.4)), segs=8, rings=4)


def build_panel_face(B, rng, phi, y0, y1, kind, bw, lights):
    h, d, st = B["hull"], B["details"], B["stencils"]
    ptop = 0.018
    if kind == "equip":
        cuts = np.linspace(y0, y1, 4)
        for i in range(3):
            a, b = cuts[i] + 0.004, cuts[i + 1] - 0.004
            xf = surface_frame(phi, BUS_A, 0.5 * (a + b))
            h.box((bw + 0.03, b - a, 0.03), "paint_white", xf, center=(0, 0, ptop - 0.015), bevel=0.004, segments=2)
            for s in np.linspace(-(b - a) / 2 + 0.04, (b - a) / 2 - 0.04, 7):
                for sx in (-(bw + 0.03) / 2 + 0.035, (bw + 0.03) / 2 - 0.035):
                    d.bolt(xf @ trans(sx, s, ptop), "alu", r=0.007, h=0.005)
        # two louver assemblies on panels 2 and 3
        for yc, tag in ((0.5 * (cuts[1] + cuts[2]) + 0.35, "LOUVER ASSY 2"), (0.5 * (cuts[2] + cuts[3]), "LOUVER ASSY 3")):
            lxf = surface_frame(phi, BUS_A + ptop, yc)
            W, H = 1.46, 1.2
            for sx in (-W / 2, W / 2):
                h.box((0.04, H, 0.07), "alu_anod", lxf, center=(sx, 0, 0.035), bevel=0.004)
            for sy in (-H / 2, H / 2):
                h.box((W + 0.04, 0.04, 0.07), "alu_anod", lxf, center=(0, sy, 0.035), bevel=0.004)
            h.box((W, H, 0.004), "paint_dark", lxf, center=(0, 0, 0.004))
            nbl = 13
            for j in range(nbl):
                by = -H / 2 + (j + 0.5) * H / nbl
                ang = math.radians(12 + rng.uniform(-2, 2))
                h.box((W - 0.03, H / nbl * 0.98, 0.003), "alu", lxf @ trans(0, by, 0.04) @ rot_x(ang), bevel=0.0008)
            h.box((0.1, H, 0.08), "paint_offwhite", lxf, center=(-W / 2 - 0.08, 0, 0.04), bevel=0.01)
            place_text(st, tag, 0.03, (lxf @ np.array([-0.2, -H / 2 - 0.055, 0.0012, 1.0]))[:3], (0, 1, 0), lxf[:3, 0],
                       "stencil_black", FONT_MONO, align="CENTER")
            place_text(st, "DO NOT OBSTRUCT  -  THERMAL CONTROL", 0.022,
                       (lxf @ np.array([0.2, -H / 2 - 0.055, 0.0012, 1.0]))[:3] + np.array([0, 0.0, 0]),
                       (0, 1, 0), lxf[:3, 0], "stencil_black", FONT_MONO)
        # registration
        rxf = surface_frame(phi, BUS_A + ptop + 0.0008, 0.5 * (cuts[0] + cuts[1]))
        o = rxf[:3, 3]
        up = rxf[:3, 0]
        place_text(st, "LSV-7", 0.56, o + up * 0.12, (0, 1, 0), up, "stencil_black", FONT_SANS, spacing=1.08)
        place_text(st, "HULL 07  /  S/N 2291-A  /  DEEP RANGE SIGNAL VESSEL", 0.04, o - up * 0.3, (0, 1, 0), up,
                   "stencil_black", FONT_MONO)
        stripe = frame_z(o - up * 0.42, rxf[:3, 2], (0, 1, 0))
        h.box((1.9, 0.02, 0.0009), "stencil_red", stripe, center=(0, 0, 0.0))
        # nav light (green, starboard) on the aft end of the panel
        c = lamp_unit(B, surface_frame(phi, BUS_A + ptop, y0 + 0.25), "nav_green", r=0.038)
        lights.append(("NavGreen_Bus", "nav", c, (0.1, 1.0, 0.3), 5.0, 0.03))
        # handrail along the upper edge
        p0 = surface_frame(phi, BUS_A + ptop, y0 + 0.6) @ np.array([0.72, 0, 0, 1.0])
        p1 = surface_frame(phi, BUS_A + ptop, y1 - 0.6) @ np.array([0.72, 0, 0, 1.0])
        d.handrail(p0[:3], p1[:3], polar(phi, 1, 0), "gold_anod", "alu_anod", bolt_mat="alu")
    elif kind == "dock":
        yc = 0.5 * (y0 + y1)
        xf = surface_frame(phi, BUS_A, yc)
        h.box((bw + 0.03, y1 - y0 - 0.008, 0.03), "paint_white", xf, center=(0, 0, ptop - 0.015), bevel=0.004,
              segments=2)
        for s in np.linspace(-(y1 - y0) / 2 + 0.04, (y1 - y0) / 2 - 0.04, 9):
            for sx in (-(bw + 0.03) / 2 + 0.035, (bw + 0.03) / 2 - 0.035):
                d.bolt(xf @ trans(sx, s, ptop), "alu", r=0.007, h=0.005)
        dxf = surface_frame(phi, BUS_A + ptop, yc + 0.1)
        build_docking(B, dxf)
        # red nav light on the port side
        c = lamp_unit(B, surface_frame(phi, BUS_A + ptop, y1 - 0.25), "nav_red", r=0.038)
        lights.append(("NavRed_Bus", "nav", c, (1.0, 0.05, 0.03), 5.0, 0.03))
        u = np.array([0, -1.0, 0])     # port side reads toward the stern
        o = dxf[:3, 3]
        place_text(st, "HATCH 1  -  EVA", 0.06, o + u * 0.0 + dxf[:3, 0] * 0.0 + np.array([0, -1.18, 0]) +
                   dxf[:3, 2] * 0.0008, u, dxf[:3, 0], "stencil_black", FONT_SANS)
        place_text(st, "EQUALIZE PRESSURE BEFORE OPENING", 0.026, o + np.array([0, -1.18, 0]) - dxf[:3, 0] * 0.1 +
                   dxf[:3, 2] * 0.0008, u, dxf[:3, 0], "stencil_black", FONT_MONO)
        place_text(st, "RESCUE", 0.05, o + np.array([0, 1.25, 0]) + dxf[:3, 2] * 0.0008, u, dxf[:3, 0],
                   "stencil_red", FONT_SANS)


def build_docking(B, xf):
    d, st = B["details"], B["stencils"]
    prof = [(0.80, -0.03), (0.80, 0.30), (0.90, 0.30), (0.90, 0.38), (0.62, 0.38), (0.62, 0.12)]
    d.lathe(prof, 64, "alu_anod", xf)
    d.lathe([(0.62, 0.12), (0.60, 0.15), (0.0, 0.15)], 48, "paint_offwhite", xf)
    d.bolt_ring(xf @ trans(0, 0, 0.38), 0.76, 36, "alu", r=0.009, h=0.007)
    d.bolt_ring(xf @ trans(0, 0, 0.15), 0.54, 16, "alu", r=0.008, h=0.006, phase=0.1)
    for k in range(3):
        a = math.radians(90 + 120 * k)
        rad = np.array([math.cos(a), math.sin(a), 0])
        tan = np.array([-math.sin(a), math.cos(a), 0])
        pxf = xf @ mat4((0, 0, 0), rad, (0, 0, 1), -tan) @ trans(0, 0, -0.012)
        d.polygon_plate([(0.64, 0.38), (0.88, 0.38), (0.82, 0.64), (0.72, 0.64)], 0.024, "alu", pxf)
    for k in range(12):
        a = 2 * math.pi * (k + 0.5) / 12
        d.box((0.07, 0.05, 0.05), "paint_grey", xf @ rot_z(a) @ trans(0.575, 0, 0.36), bevel=0.006)
    # handle and window on the hatch
    for sx in (-0.18, 0.18):
        d.tube((xf @ np.array([sx, -0.22, 0.15, 1.0]))[:3], (xf @ np.array([sx, -0.22, 0.24, 1.0]))[:3], 0.014,
               "alu", segs=8)
    d.tube((xf @ np.array([-0.19, -0.22, 0.24, 1.0]))[:3], (xf @ np.array([0.19, -0.22, 0.24, 1.0]))[:3], 0.016,
           "gold_anod", segs=10)
    wxf = xf @ trans(0.0, 0.25, 0.15)
    d.lathe([(0.11, 0.0), (0.11, 0.025), (0.09, 0.025), (0.09, 0.005)], 32, "alu", wxf)
    B["interior"].lathe([(0.091, 0.006), (0.0, 0.006)], 32, "interior", wxf)


def build_service(B, rng, lights):
    h, d, st = B["hull"], B["details"], B["stencils"]
    ay = along_y()
    rc = (SVC_A - 0.03) / C22
    h.lathe([(0, SVC_Y0 + 0.01), (rc, SVC_Y0 + 0.01), (rc, SVC_Y1 - 0.01), (0, SVC_Y1 - 0.01)], 8, "paint_dark", ay,
            phase=OCT)
    h.lathe([(SVC_R, SVC_Y1), (BUS_R - 0.05, SVC_Y1)], 8, "paint_white", ay, phase=OCT)
    h.lathe([(0, SVC_Y0 - 0.02), (SVC_R, SVC_Y0 - 0.02), (SVC_R, SVC_Y0)], 8, "paint_white", ay, phase=OCT)
    pw = 2 * SVC_A * T22 - 0.085
    for k in range(8):
        phi = 45.0 * k
        for (a, b) in ((SVC_Y0 + 0.02, 10.88), (10.92, SVC_Y1 - 0.02)):
            xf = surface_frame(phi, SVC_A - 0.0125, 0.5 * (a + b))
            h.box((pw, b - a, 0.025), "paint_white", xf, bevel=0.004, segments=2)
            for sx in (-pw / 2 + 0.03, pw / 2 - 0.03):
                for sy in (-(b - a) / 2 + 0.03, (b - a) / 2 - 0.03):
                    d.bolt(xf @ trans(sx, sy, 0.0125), "alu", r=0.007, h=0.005)
        vphi = 22.5 + 45 * k
        xf = frame_z(polar(vphi, SVC_R - 0.015, SVC_Y0), (0, 1, 0), polar(vphi, 1, 0))
        h.box((0.05, 0.08, SVC_Y1 - SVC_Y0), "alu_anod", xf, center=(0, 0, (SVC_Y1 - SVC_Y0) / 2), bevel=0.008)
    # RCS quads on the diagonal corners
    for i, vphi in enumerate((22.5 + 45, 22.5 + 135, 22.5 + 225, 22.5 + 315)):
        n = polar(vphi - 22.5, 1, 0)
        xf = mat4(polar(vphi - 22.5, SVC_A, 10.9), np.cross((0, 1, 0), n), (0, 1, 0), n)
        rcs_quad(B, xf, f"RCS {i + 1}A")
    # dorsal xenon strobe + stencils next to it
    bxf = surface_frame(90, SVC_A, 10.9)
    c = lamp_unit(B, bxf, "beacon", r=0.055, mast=0.28)
    for k in range(3):
        a = 2 * math.pi * k / 3 + 0.4
        p0 = (bxf @ np.array([0.085 * math.cos(a), 0.085 * math.sin(a), 0.33, 1.0]))[:3]
        p1 = (bxf @ np.array([0.0, 0.0, 0.46, 1.0]))[:3]
        d.tube(p0, p1, 0.005, "alu_anod", segs=6)
    lights.append(("Beacon_Dorsal", "beacon", c, (0.82, 0.88, 1.0), 2600.0, 0.03))
    o = surface_frame(90, SVC_A + 0.0008, 11.55)[:3, 3]
    place_text(st, "LSV-7", 0.16, o + np.array([0.55, 0, 0]), (-1, 0, 0), (0, -1, 0), "stencil_black", FONT_SANS,
               spacing=1.08)
    place_text(st, "WARNING  XENON STROBE  EYE HAZARD", 0.024, o + np.array([-0.45, 0.0, 0]), (-1, 0, 0), (0, -1, 0),
               "stencil_black", FONT_MONO)
    st.box((0.7, 0.012, 0.0008), "stencil_red", mat4(o + np.array([-0.45, -0.05, 0]), (1, 0, 0), (0, 1, 0), (0, 0, 1)))
    # bolted instrument placard through the dorsal blankets, next to the strobe (macro hero detail)
    pxf = surface_frame(90, BUS_A - 0.01, 12.36) @ trans(0.3, 0, 0)
    h.box((0.62, 0.38, 0.085), "paint_white", pxf, center=(0, 0, 0.0425), bevel=0.006, segments=2)
    for bx in (-0.27, 0.27):
        for by in (-0.15, 0.15):
            d.bolt(pxf @ trans(bx, by, 0.085), "alu", r=0.008, h=0.006)
    po = (pxf @ np.array([0.0, 0.0, 0.0858, 1.0]))[:3]
    place_text(st, "LSV-7", 0.13, po + np.array([0.0, 0.07, 0]), (-1, 0, 0), (0, -1, 0), "stencil_black", FONT_SANS,
               spacing=1.08)
    place_text(st, "BUS THERMAL  ZONE 4", 0.026, po + np.array([0.0, -0.045, 0]), (-1, 0, 0), (0, -1, 0),
               "stencil_black", FONT_MONO)
    place_text(st, "DO NOT STEP  -  MLI", 0.022, po + np.array([0.0, -0.1, 0]), (-1, 0, 0), (0, -1, 0),
               "stencil_red", FONT_MONO)
    for sx in (-0.29, 0.29):
        st.box((0.012, 0.3, 0.0008), "stencil_yellow", mat4(po + np.array([sx, 0, 0]), (1, 0, 0), (0, 1, 0), (0, 0, 1)))
    d.tube(po + np.array([0.33, 0.1, -0.01]), po + np.array([0.33, 0.62, -0.01]), 0.012, "cable_black", segs=8)
    # ventral strobe
    vxf = surface_frame(270, SVC_A, 10.9)
    c = lamp_unit(B, vxf, "beacon", r=0.05, mast=0.2)
    lights.append(("Beacon_Ventral", "beacon", c, (0.82, 0.88, 1.0), 1800.0, 0.03))
    # service handrails (tangential) on the upper diagonals
    for phi in (45, 135):
        xf = surface_frame(phi, SVC_A, 11.45)
        d.handrail((xf @ np.array([-0.8, 0, 0, 1.0]))[:3], (xf @ np.array([0.8, 0, 0, 1.0]))[:3], xf[:3, 2],
                   "gold_anod", "alu_anod", bolt_mat="alu")
    # aft adapter: black-kapton cone with stringers
    h.lathe([(1.25, 8.0), (2.3, SVC_Y0 - 0.02)], 8, "mli_black", ay, phase=OCT)
    for k in range(8):
        a = 22.5 + 45 * k
        d.beam(polar(a, 1.25, 8.0) + polar(a, 0.03, 0), polar(a, 2.3, SVC_Y0 - 0.02) + polar(a, 0.03, 0), 0.05, 0.05,
               "alu_anod", up=polar(a, 1, 0))
    # magnetometer boom (port-dorsal)
    build_boom(B, polar(157.5, SVC_R + 0.05, 11.0), unit(polar(157.5, 1, 0) + np.array([0, -0.16, 0])), 8.5)


def build_boom(B, base, dirv, length):
    d = B["details"]
    xf = frame_z(base, dirv, (0, 1, 0))
    d.box((0.36, 0.36, 0.28), "paint_offwhite", xf, center=(0, 0, -0.1), bevel=0.012)
    d.cylinder(0.08, 0.12, "alu_anod", frame_z(base, (0, 1, 0)), segs=16, z0=-0.2)
    rr = 0.14
    nst = int(length / 0.42)
    pts = []
    for s in range(nst + 1):
        z = 0.08 + s * (length - 0.08) / nst
        ring = []
        for k in range(3):
            a = 2 * math.pi * k / 3 + s * 0.0
            ring.append((xf @ np.array([rr * math.cos(a), rr * math.sin(a), z, 1.0]))[:3])
        pts.append(ring)
    for k in range(3):
        d.tube(pts[0][k], pts[-1][k], 0.009, "paint_offwhite", segs=6)
    for s in range(nst + 1):
        for k in range(3):
            d.tube(pts[s][k], pts[s][(k + 1) % 3], 0.005, "alu_anod", segs=5)
        if s < nst:
            for k in range(3):
                d.tube(pts[s][k], pts[s + 1][(k + 1) % 3], 0.004, "alu_anod", segs=4)
    tip = (xf @ np.array([0, 0, length, 1.0]))[:3]
    d.cylinder(0.15, 0.36, "paint_white", frame_z(tip, dirv), segs=24, chamfer=0.015)
    d.cylinder(0.155, 0.02, "alu_anod", frame_z(tip, dirv), segs=24, z0=0.34)
    mid = (xf @ np.array([0, 0, length * 0.55, 1.0]))[:3]
    d.box((0.22, 0.22, 0.2), "mli_gold", frame_z(mid, dirv), bevel=0.01)


def build_mast_and_dish(B, rng):
    m = B["mast"]
    zb = -0.6
    m.beam((0, NOSE_Y1 + 0.02, zb), (0, AZ_PIVOT[1] - 0.4, zb), 0.34, 0.34, "paint_white", up=(0, 0, 1), bevel=0.02)
    for sx in (-1, 1):
        for sz in (-1, 1):
            p0 = np.array([sx * 0.95, NOSE_Y1 + 0.03, zb + sz * 0.8])
            p1 = np.array([sx * 0.17, 24.2, zb + sz * 0.17])
            m.tube(p0, p1, 0.035, "composite", segs=8)
            m.cylinder(0.06, 0.08, "alu_anod", frame_z(p0, p1 - p0), segs=12)
            m.cylinder(0.05, 0.08, "alu_anod", frame_z(p1, p0 - p1), segs=12)
    for y in (22.8, 23.6, 24.4, 25.2):
        m.box((0.36, 0.05, 0.36), "alu_anod", trans(0, y, zb), bevel=0.006)
    for sx in (-0.1, 0.0, 0.1):
        m.tube((sx, NOSE_Y1 + 0.03, zb - 0.19), (sx, AZ_PIVOT[1] - 0.45, zb - 0.19), 0.016,
               "cable_black" if sx else "cable_white", segs=8)
    # static azimuth drum
    dxf = trans(AZ_PIVOT[0], AZ_PIVOT[1], 0)
    m.cylinder(0.42, 0.42, "paint_white", dxf, segs=48, chamfer=0.02, z0=-0.8)
    m.bolt_ring(dxf @ trans(0, 0, -0.38), 0.37, 20, "alu", r=0.009, h=0.006)
    place_text(B["stencils"], "HGA GIMBAL  AZ", 0.035, np.array([0.4201, AZ_PIVOT[1], -0.6]), (0, 1, 0), (0, 0, 1),
               "stencil_black", FONT_MONO)

    # --- azimuth stage (Dish_Az local, origin at pivot)
    a = B["gaz"]
    a.cylinder(0.40, 0.12, "alu_anod", None, segs=48, z0=-0.38)
    for k in range(60):
        ang = 2 * math.pi * k / 60
        a.box((0.02, 0.025, 0.08), "alu", rot_z(ang) @ trans(0.405, 0, -0.33))
    a.box((1.44, 0.56, 0.1), "paint_white", None, center=(0, 0, -0.21), bevel=0.012, segments=2)
    for sx in (-0.66, 0.66):
        a.box((0.1, 0.5, 0.46), "paint_white", None, center=(sx, 0, 0.07), bevel=0.012, segments=2)
        a.cylinder(0.25, 0.14, "alu_anod", frame_z((sx - 0.07, 0, 0), (1, 0, 0)), segs=40, chamfer=0.01)
        a.bolt_ring(frame_z((sx + 0.07 * np.sign(sx), 0, 0), (np.sign(sx), 0, 0)), 0.2, 8, "alu", r=0.008, h=0.006)
    a.cylinder(0.15, 0.3, "paint_grey", frame_z((0.73, 0, 0), (1, 0, 0)), segs=24, chamfer=0.01)
    a.cylinder(0.12, 0.25, "paint_grey", trans(0.45, -0.18, -0.16), segs=24, chamfer=0.01)
    a.tube((0.45, -0.18, 0.09), (0.66, -0.15, 0.25), 0.02, "cable_black", segs=8)
    place_text(B["stencils"], "EL", 0.05, np.array([0.7101, 0.0, -0.08]), (0, 1, 0), (0, 0, 1),
               "stencil_black", FONT_MONO)

    # --- elevation stage (Dish_El local)
    e = B["gel"]
    e.cylinder(0.2, 1.12, "alu_anod", frame_z((-0.56, 0, 0), (1, 0, 0)), segs=32, chamfer=0.01)
    e.box((0.62, 0.36, 0.62), "paint_white", None, center=(0, 0.3, 0), bevel=0.02, segments=2)
    e.lathe([(0, 0.4), (0.46, 0.4), (0.46, DISH_V + 0.02), (0, DISH_V + 0.02)], 48, "mli_gold", along_y())
    e.lathe([(0.46, 0.95), (0.62, 0.95), (0.62, 1.0), (0.46, 1.0)], 48, "paint_white", along_y())
    e.bolt_ring(frame_z((0, 1.0, 0), (0, 1, 0)), 0.56, 24, "alu", r=0.009, h=0.006)
    for k in range(4):
        ang = math.radians(45 + 90 * k)
        e.box((0.08, 0.5, 0.06), "tape_gold", frame_z((0, 0.7, 0), (0, 1, 0)) @ rot_z(ang) @ trans(0.46, 0, 0),
              bevel=0.01)

    # --- reflector (Dish_El local; axis +Y, vertex DISH_V ahead of the pivot)
    r = B["dish"]
    zf = lambda rr: rr * rr / (4 * DISH_F)
    rs = np.concatenate([[0.0], np.linspace(0.18, DISH_R, 30)])
    back = [(x, zf(x) - DISH_T + (0.0 if x > 0 else 0.0)) for x in rs]
    lip = [(DISH_R + 0.03, zf(DISH_R) - DISH_T + 0.01), (DISH_R + 0.045, zf(DISH_R) - 0.02),
           (DISH_R + 0.03, zf(DISH_R) + 0.012)]
    r.lathe(back + lip, 96, "paint_offwhite", along_y(DISH_V))
    front = [(DISH_R + 0.03, zf(DISH_R) + 0.012), (DISH_R, zf(DISH_R))] + [(x, zf(x)) for x in rs[::-1][1:]]
    r.lathe(front, 96, "dish_white", along_y(DISH_V))
    # back ribs and ring beam
    for k in range(16):
        ang = 2 * math.pi * k / 16
        rad = np.array([math.cos(ang), 0, math.sin(ang)])
        xf = mat4((0, DISH_V, 0), rad, (0, 1, 0), np.cross(rad, (0, 1, 0))) @ trans(0, 0, -0.016)
        rr = np.linspace(0.45, DISH_R - 0.05, 12)
        top = [(x, zf(x) - DISH_T + 0.005) for x in rr]
        hgt = 0.34 * (1 - (rr - 0.45) / (DISH_R - 0.5)) + 0.05
        bot = [(x, zf(x) - DISH_T - hh) for x, hh in zip(rr, hgt)]
        r.polygon_plate(top + bot[::-1], 0.032, "alu_anod", xf)
    for rr0 in (1.6, 2.9):
        z0 = zf(rr0) - DISH_T - 0.12
        r.lathe([(rr0 - 0.04, z0 - 0.04), (rr0 + 0.04, z0 - 0.04), (rr0 + 0.04, z0 + 0.1), (rr0 - 0.04, z0 + 0.1),
                 (rr0 - 0.04, z0 - 0.04)], 96, "alu_anod", along_y(DISH_V))
    # feed horn + subreflector + quadripod
    r.lathe([(0.34, 0.0), (0.3, 0.1), (0.21, 0.95), (0.18, 0.96)], 48, "paint_white", along_y(DISH_V))
    r.lathe([(0.18, 0.96), (0.17, 0.9), (0.0, 0.9)], 48, "black", along_y(DISH_V))
    r.lathe([(0.0, 2.2), (0.3, 2.215), (0.55, 2.26), (0.565, 2.28), (0.565, 2.31), (0.5, 2.33), (0.0, 2.35)], 48,
            "paint_white", along_y(DISH_V))
    r.bolt_ring(along_y(DISH_V + 2.35), 0.3, 8, "alu", r=0.008, h=0.006)
    for k in range(4):
        ang = math.radians(45 + 90 * k)
        rad = np.array([math.cos(ang), 0, math.sin(ang)])
        p0 = rad * 3.75 + np.array([0, DISH_V + zf(3.75) + 0.01, 0])
        p1 = rad * 0.47 + np.array([0, DISH_V + 2.28, 0])
        r.tube(p0, p1, 0.042, "composite", segs=10)
        r.cylinder(0.065, 0.1, "alu_anod", frame_z(p0 - unit(p1 - p0) * 0.02, p1 - p0), segs=12, chamfer=0.01)
        r.cylinder(0.055, 0.08, "alu_anod", frame_z(p1, p0 - p1), segs=12, chamfer=0.01)


def build_truss(B, rng):
    t = B["truss"]
    ys = np.linspace(TRUSS_Y1, TRUSS_Y0, TRUSS_BAYS + 1)
    P = lambda i, y: polar(TRI[i], TRUSS_RC, y)
    for i in range(3):
        t.tube(P(i, TRUSS_Y1 + 0.1), P(i, TRUSS_Y0 - 0.1), 0.055, "alu", segs=14)
    for s, y in enumerate(ys):
        for i in range(3):
            t.cylinder(0.082, 0.2, "alu_anod", frame_z(P(i, y + 0.1), (0, -1, 0)), segs=16, chamfer=0.012)
            n = polar(TRI[i], 1, 0)
            for sy in (-0.06, 0.06):
                t.bolt(frame_z(P(i, y + sy) + n * 0.08, n, (0, 1, 0)), "alu", r=0.009, h=0.007)
            j = (i + 1) % 3
            a, b = P(i, y), P(j, y)
            dv = unit(b - a)
            t.tube(a + dv * 0.07, b - dv * 0.07, 0.034, "alu_anod", segs=10)
        if s < TRUSS_BAYS:
            y2 = ys[s + 1]
            for i in range(3):
                j = (i + 1) % 3
                a, b = (P(i, y), P(j, y2)) if (s + i) % 2 == 0 else (P(j, y), P(i, y2))
                dv = unit(b - a)
                t.tube(a + dv * 0.09, b - dv * 0.09, 0.028, "composite", segs=8)
                t.cylinder(0.04, 0.07, "alu_anod", frame_z(a + dv * 0.07, dv), segs=10)
                t.cylinder(0.04, 0.07, "alu_anod", frame_z(b - dv * 0.14, dv), segs=10)
    # harness bundle along the dorsal longeron, clamped at every node
    top = P(0, 0)
    for k, sx in enumerate((-0.075, 0.0, 0.075)):
        t.tube((sx, TRUSS_Y1 + 1.6, top[2] + 0.12), (sx, TRUSS_Y0 - 0.2, top[2] + 0.12), 0.02,
               "cable_white" if k == 1 else "cable_black", segs=8)
    for y in ys:
        t.box((0.26, 0.05, 0.05), "alu_anod", trans(0, y - 0.25, top[2] + 0.12), bevel=0.006)
        t.box((0.04, 0.05, 0.08), "alu_anod", trans(0, y - 0.25, top[2] + 0.05), bevel=0.004)
    # coolant loop pair (reactor -> radiator manifolds) under the truss
    bz = -TRUSS_RC * 0.5 - 0.22
    for sx in (-0.2, 0.2):
        t.tube((sx, TRUSS_Y0 - 0.3, bz), (sx, RAD_Y0 + 0.3, bz), 0.055, "mli_silver", segs=12)
    for y in np.linspace(TRUSS_Y0 + 0.4, RAD_Y0, 8):
        t.box((0.6, 0.06, 0.05), "alu_anod", trans(0, y, bz + 0.07), bevel=0.006)
    t.box((0.7, 0.5, 0.3), "paint_white", trans(0, RAD_Y0 + 0.4, bz), bevel=0.02, segments=2)


def build_tanks(B, rng):
    k = B["tanks"]
    st = B["stencils"]
    for phi in (45, 135, 225, 315):
        c = polar(phi, SPH_RAD, SPH_Y)
        k.sphere(SPH_R, "mli_silver", trans(*c), segs=72, rings=36)
        k.displace_last(lambda V, c=c: wrinkle_sphere(V, c, rng))
        k.lathe([(SPH_R + 0.03, -0.07), (SPH_R + 0.03, 0.07)], 64, "paint_white", frame_z(c, (0, 1, 0)))
        k.lathe([(SPH_R + 0.034, -0.06), (SPH_R + 0.034, -0.05)], 64, "alu_anod", frame_z(c, (0, 1, 0)))
        inward = -polar(phi, 1, 0)
        for dy in (-1, 1):
            for side in (-1, 1):
                t = unit(np.cross((0, 1, 0), polar(phi, 1, 0)))
                p0 = c + unit(t * side * 0.75 + inward * 1.0) * (SPH_R + 0.03)
                p0[1] = c[1]
                best = None
                for i in range(3):
                    q = polar(TRI[i], TRUSS_RC, c[1] + dy * 0.8)
                    dd = np.linalg.norm(q - p0)
                    if best is None or dd < best[0]:
                        best = (dd, q)
                q = best[1]
                k.tube(p0, q, 0.032, "alu_anod", segs=8)
                k.cylinder(0.05, 0.08, "alu_anod", frame_z(p0, q - p0), segs=10, chamfer=0.008)
    for i, phi in enumerate((0, 90, 180, 270)):
        c = polar(phi, COPV_RAD, 0.5 * (COPV_Y0 + COPV_Y1))
        L = COPV_Y1 - COPV_Y0
        cz = L / 2 - COPV_R
        prof = [(0, -L / 2)]
        for j in range(1, 9):
            a = math.pi / 2 * j / 8
            prof.append((COPV_R * math.sin(a), -cz - COPV_R * math.cos(a)))
        for j in range(0, 9):
            a = math.pi / 2 * j / 8
            prof.append((COPV_R * math.cos(a), cz + COPV_R * math.sin(a)))
        prof[-1] = (0.0, L / 2)
        axf = frame_z(c, (0, 1, 0), polar(phi, 1, 0))
        k.lathe(prof, 48, "paint_white", axf)
        for yy in (-L / 2 - 0.12, L / 2):
            k.cylinder(0.12, 0.12, "alu", axf, segs=16, chamfer=0.015, z0=yy)
        for zz in (-cz + 0.5, cz - 0.5):
            k.lathe([(COPV_R + 0.006, zz - 0.06), (COPV_R + 0.03, zz - 0.05), (COPV_R + 0.03, zz + 0.05),
                     (COPV_R + 0.006, zz + 0.06)], 48, "alu_anod", axf)
            q = polar(TRI[min(range(3), key=lambda m: np.linalg.norm(polar(TRI[m], TRUSS_RC, 0) - polar(phi, COPV_RAD, 0)))],
                      TRUSS_RC, c[1] + zz)
            p0 = c + np.array([0, zz, 0]) - polar(phi, COPV_R + 0.03, 0)
            k.tube(p0, q, 0.04, "alu_anod", segs=8)
        place_text_cyl(st, f"XE-{i + 1}   MEOP 18.6 MPA", 0.075, axf, COPV_R, 0.0, "stencil_black", FONT_SANS, z0=0.2)
        place_text_cyl(st, "DANGER  HIGH PRESSURE", 0.045, axf, COPV_R, -0.13, "stencil_red", FONT_MONO, z0=0.2)


def build_radiators(B, rng, lights):
    R = B["rads"]
    d, st = B["details"], B["stencils"]
    for ip, phi in enumerate(RAD_PHI):
        c, s = math.cos(math.radians(phi)), math.sin(math.radians(phi))
        X = np.array([c, 0, s])
        Y = np.array([0.0, 1.0, 0.0])
        Z = np.cross(X, Y)
        pf = mat4((0, 0, 0), X, Y, Z)
        poly = [(RAD_X0, RAD_Y1), (RAD_X1, RAD_TIP1), (RAD_X1, RAD_TIP0), (RAD_X0, RAD_Y0)]
        R.polygon_plate(poly, 0.05, "radiator", pf @ trans(0, 0, -0.025))
        W = lambda x, y: (pf @ np.array([x, y, 0, 1.0]))[:3]
        for a, b in zip(poly, poly[1:] + poly[:1]):
            R.beam(W(*a), W(*b), 0.06, 0.07, "alu_anod", up=Z, bevel=0.006)
        # heat pipes, both faces
        for y in np.arange(RAD_Y0 - 0.3, RAD_Y1 + 0.2, -0.5):
            if y > RAD_TIP0:
                xm = RAD_X0 + (RAD_X1 - RAD_X0) * (RAD_Y0 - y) / (RAD_Y0 - RAD_TIP0)
            elif y < RAD_TIP1:
                xm = RAD_X0 + (RAD_X1 - RAD_X0) * (y - RAD_Y1) / (RAD_TIP1 - RAD_Y1)
            else:
                xm = RAD_X1
            xm -= 0.06
            if xm < RAD_X0 + 0.3:
                continue
            for sz in (-1, 1):
                p0 = (pf @ np.array([RAD_X0 + 0.04, y, sz * 0.03, 1.0]))[:3]
                p1 = (pf @ np.array([xm, y, sz * 0.03, 1.0]))[:3]
                R.tube(p0, p1, 0.016, "alu_dark", segs=8, x_hint=Z)
        # root manifold + hinge brackets to the truss
        m0, m1 = W(1.8, RAD_Y0 + 0.2), W(1.8, RAD_Y1 - 0.2)
        R.tube(m0, m1, 0.11, "mli_silver", segs=20)
        for y in np.linspace(RAD_Y0 - 0.6, RAD_Y1 + 0.6, 4):
            hp = W(1.8, y)
            R.box((0.36, 0.14, 0.3), "paint_white", mat4(hp, X, Y, Z), bevel=0.015)
            yy = TRUSS_Y1 - round((TRUSS_Y1 - y) / ((TRUSS_Y1 - TRUSS_Y0) / TRUSS_BAYS)) * (TRUSS_Y1 - TRUSS_Y0) / TRUSS_BAYS
            for i in range(3):
                q = polar(TRI[i], TRUSS_RC, yy)
                if np.linalg.norm(q - hp) < 1.75:
                    R.tube(hp, q, 0.035, "alu_anod", segs=8)
        # deploy strut from the truss to 40 % span
        yy = TRUSS_Y1 - 16 * (TRUSS_Y1 - TRUSS_Y0) / TRUSS_BAYS
        i = min(range(3), key=lambda m: np.linalg.norm(polar(TRI[m], TRUSS_RC, 0) - W(4.0, 0) * np.array([1, 0, 1])))
        q = polar(TRI[i], TRUSS_RC, yy + 1.6)
        side = -1 if np.dot(q - W(4.0, -12.5), Z) < 0 else 1
        pnt = (pf @ np.array([4.0, -12.5, side * 0.03, 1.0]))[:3]
        R.tube(q, pnt, 0.03, "composite", segs=8)
        R.cylinder(0.05, 0.1, "alu_anod", frame_z(pnt, q - pnt), segs=10)
        # lights: nav on leading tip, running on trailing tip
        starboard = c > 0
        tip_f = mat4(W(RAD_X1 + 0.035, RAD_TIP0 - 0.15), X, Y, Z) @ mat4((0, 0, 0), Y, Z, X)
        cc = lamp_unit(B, tip_f, "nav_green" if starboard else "nav_red", r=0.04)
        lights.append((f"Nav_Rad{ip}", "nav", cc, (0.1, 1.0, 0.3) if starboard else (1.0, 0.05, 0.03), 3.0, 0.03))
        tip_a = mat4(W(RAD_X1 + 0.035, RAD_TIP1 + 0.15), X, Y, Z) @ mat4((0, 0, 0), Y, Z, X)
        lamp_unit(B, tip_a, "running", r=0.03)
        # white stencils near the root
        for sz in (-1, 1):
            o = (pf @ np.array([2.6, RAD_Y0 - 0.9, sz * 0.0262, 1.0]))[:3]
            place_text(st, f"RAD-{ip + 1}", 0.2, o, Y if sz > 0 else -Y, -X, "stencil_white", FONT_SANS)
            o2 = (pf @ np.array([2.35, RAD_Y0 - 1.0, sz * 0.0262, 1.0]))[:3]
            place_text(st, "HOT SURFACE  DO NOT CONTACT", 0.045, o2, Y if sz > 0 else -Y, -X, "stencil_white", FONT_MONO)


def build_aft(B, rng, lights):
    f, d, st = B["aft"], B["details"], B["stencils"]
    ay = along_y()
    # interface plate and truss end fittings
    f.lathe([(0, -19.5), (2.2, -19.5), (2.2, -19.2), (0, -19.2)], 8, "paint_white", ay, phase=OCT)
    for i in range(3):
        f.cylinder(0.12, 0.25, "alu_anod", frame_z(polar(TRI[i], TRUSS_RC, -19.2), (0, 1, 0)), segs=16, chamfer=0.015)
    # shadow shield (wide end forward)
    f.lathe([(0, SHIELD_Y1 - 0.05), (SHIELD_R1, SHIELD_Y1 - 0.05), (SHIELD_R1 + 0.05, SHIELD_Y1),
             (SHIELD_R0 - 0.05, SHIELD_Y0 - 0.08), (SHIELD_R0, SHIELD_Y0 - 0.05), (SHIELD_R0, SHIELD_Y0 - 0.01),
             (1.0, SHIELD_Y0 - 0.01)], 64, "paint_offwhite", ay)
    f.lathe([(SHIELD_R0 - 0.02, SHIELD_Y0 - 0.12), (SHIELD_R0 + 0.06, SHIELD_Y0 - 0.12),
             (SHIELD_R0 + 0.06, SHIELD_Y0 - 0.005), (SHIELD_R0 - 0.02, SHIELD_Y0 - 0.005)], 64, "alu_anod", ay)
    f.bolt_ring(frame_z((0, SHIELD_Y0 - 0.005, 0), (0, 1, 0)), SHIELD_R0 + 0.02, 48, "alu", r=0.011, h=0.008)
    f.lathe([(SHIELD_R1 - 0.02, SHIELD_Y1 - 0.12), (SHIELD_R1 + 0.2, SHIELD_Y1 - 0.12), (SHIELD_R1 + 0.2, SHIELD_Y1 - 0.02),
             (SHIELD_R1 - 0.02, SHIELD_Y1 - 0.02), (SHIELD_R1 - 0.02, SHIELD_Y1 - 0.12)], 48, "alu_anod", ay)
    f.bolt_ring(frame_z((0, SHIELD_Y1 - 0.12, 0), (0, -1, 0)), SHIELD_R1 + 0.12, 24, "alu", r=0.01, h=0.007)
    gen = np.array([SHIELD_R0 - SHIELD_R1, SHIELD_Y0 - SHIELD_Y1])
    nrm2 = unit(np.array([gen[1], -gen[0]]))
    for k in range(24):
        a = 2 * math.pi * k / 24
        rad = np.array([math.cos(a), 0, math.sin(a)])
        nrm = rad * nrm2[0] + np.array([0, nrm2[1], 0])
        p0 = rad * (SHIELD_R0 - 0.12) + np.array([0, SHIELD_Y0 - 0.2, 0]) + nrm * 0.03
        p1 = rad * (SHIELD_R1 + 0.1) + np.array([0, SHIELD_Y1 + 0.06, 0]) + nrm * 0.03
        f.beam(p0, p1, 0.045, 0.06, "paint_offwhite", up=nrm, bevel=0.008)
    for k in range(4):
        a = math.radians(45 + 90 * k)
        rr = 2.62
        o = np.array([rr * math.cos(a), SHIELD_Y0 - 0.008, rr * math.sin(a)])
        txf = mat4(o, (math.cos(a + math.pi / 2), 0, math.sin(a + math.pi / 2)), (-math.cos(a), 0, -math.sin(a)), (0, 1, 0))
        txf = mat4(o, txf[:3, 0], np.cross((0, 1, 0), txf[:3, 0]), (0, 1, 0))
        trefoil(st, txf, 0.03, "stencil_yellow", "stencil_black")
    # reactor vessel + heat-rejection fins
    f.lathe([(0, -25.0), (0.5, -25.0), (0.8, -24.85), (0.85, -24.6), (0.85, -22.5), (0.96, -22.46), (0.96, -22.36),
             (0, -22.36)], 48, "reactor", ay)
    for yb in (-22.9, -24.4):
        f.lathe([(0.845, yb - 0.04), (0.9, yb - 0.04), (0.9, yb + 0.04), (0.845, yb + 0.04)], 48, "nozzle", ay)
    for k in range(16):
        a = 2 * math.pi * k / 16
        rad = np.array([math.cos(a), 0, math.sin(a)])
        xf = mat4((0, 0, 0), rad, (0, 1, 0), np.cross(rad, (0, 1, 0))) @ trans(0, 0, -0.016)
        f.polygon_plate([(0.84, -24.8), (2.05, -24.55), (2.05, -22.85), (0.84, -22.6)], 0.032, "reactor", xf)
        f.tube(rad * 2.06 + np.array([0, -24.55, 0]), rad * 2.06 + np.array([0, -22.85, 0]), 0.03, "reactor", segs=8)
    for k in range(4):
        a = math.radians(11.25 + 90 * k)
        p0, p1, p2 = polar(a * 180 / math.pi, 0.84, -23.25), polar(a * 180 / math.pi, 1.28, -23.25), polar(a * 180 / math.pi, 1.28, -22.2)
        f.tube(p0, p1, 0.06, "nozzle", segs=12)
        f.tube(p1, p2, 0.06, "nozzle", segs=12)
        f.sphere(0.068, "nozzle", trans(*p1), segs=12, rings=6)
    # PPU / thrust frame (black kapton sides)
    f.lathe([(0, PPU_Y1), (PPU_R, PPU_Y1), (PPU_R, PPU_Y0), (0.87, PPU_Y0)], 8, "paint_white", ay, phase=OCT)
    pa = PPU_R * C22
    for k in range(8):
        phi = 45.0 * k
        blanket(f, surface_frame(phi, pa + 0.004, 0.5 * (PPU_Y0 + PPU_Y1)), 2 * pa * T22 - 0.1, PPU_Y0 - PPU_Y1 - 0.06,
                "black", rng, puff=0.015)
        vphi = 22.5 + 45 * k
        xf = frame_z(polar(vphi, PPU_R - 0.01, PPU_Y1), (0, 1, 0), polar(vphi, 1, 0))
        f.box((0.05, 0.08, PPU_Y0 - PPU_Y1), "alu_anod", xf, center=(0, 0, (PPU_Y0 - PPU_Y1) / 2), bevel=0.008)
    for i, vphi in enumerate((45, 135, 225, 315)):
        n = polar(vphi, 1, 0)
        xf = mat4(polar(vphi, pa + 0.01, -25.55), np.cross((0, 1, 0), n), (0, 1, 0), n)
        rcs_quad(B, xf, f"RCS {i + 1}B")
    for vphi in (22.5, 157.5, 202.5, 337.5):
        lamp_unit(B, frame_z(polar(vphi, PPU_R * 0.86, PPU_Y1), (0, -1, 0), polar(vphi, 1, 0)), "running", r=0.03)
    o = np.array([0, PPU_Y1 - 0.0008, -1.75])
    place_text(st, "PPU-A   HIGH VOLTAGE 1800 V", 0.06, o, (-1, 0, 0), (0, 0, 1), "stencil_red", FONT_MONO)
    place_text(st, "LSV-7", 0.2, np.array([0, PPU_Y1 - 0.0008, 1.95]), (-1, 0, 0), (0, 0, 1), "stencil_black", FONT_SANS)
    # ion thrusters
    for i, phi in enumerate(THR_PHI):
        base = polar(phi, THR_RAD, PPU_Y1)
        out = polar(phi, 1, 0)
        txf = frame_z(base, (0, -1, 0), out)
        f.lathe([(0.52, 0.0), (0.6, 0.0), (0.6, 0.1), (0.52, 0.1), (0.52, 0.0)], 40, "alu_anod", txf)
        f.lathe([(0, 0.1), (0.42, 0.1), (0.42, 0.2), (0.48, 0.22), (0.66, 0.5), (0.68, 0.97)], 48, "alu_anod", txf)
        f.lathe([(0.68, 0.97), (0.745, 0.985), (0.745, 1.105), (0.70, 1.125), (0.64, 1.125), (0.64, 1.10)], 48,
                "paint_dark", txf)
        f.bolt_ring(txf @ trans(0, 0, 1.125), 0.69, 24, "alu", r=0.007, h=0.005)
        for k in range(3):
            a = 2 * math.pi * k / 3 + 0.5
            p0 = (txf @ np.array([0.8 * math.cos(a), 0.8 * math.sin(a), 0.0, 1.0]))[:3]
            p1 = (txf @ np.array([0.63 * math.cos(a), 0.63 * math.sin(a), 0.42, 1.0]))[:3]
            f.tube(p0, p1, 0.028, "alu", segs=8)
            f.cylinder(0.045, 0.06, "paint_grey", frame_z(p0, p1 - p0), segs=10)
        nx = (txf @ np.array([0.8, 0.0, 0.95, 1.0]))[:3]
        ne = (txf @ np.array([0.7, 0.0, 1.28, 1.0]))[:3]
        f.box((0.08, 0.1, 0.2), "paint_dark", txf, center=(0.74, 0, 0.92), bevel=0.008)
        f.tube(nx, ne, 0.045, "nozzle", segs=12)
        f.tube((txf @ np.array([0.0, 0.64, 0.3, 1.0]))[:3], (txf @ np.array([0.0, 0.9, 0.02, 1.0]))[:3], 0.02,
               "cable_black", segs=8)
        # grid (own object: object-space shader) and plume
        g = MeshBuilder(f"SHIP_IonGrid_{i}", rng)
        g.lathe([(0.64, 0.0), (0.5, 0.008), (0.3, 0.016), (0.0, 0.021)], 64, "ion_grid")
        gxf = txf @ trans(0, 0, THR_GRID_Z - 0.01)
        B[f"grid{i}"] = (g, gxf)
        p = MeshBuilder(f"SHIP_IonPlume_{i}", rng)
        p.lathe([(0, 0.03), (0.66, 0.03), (2.9, 14.0), (0, 14.0)], 32, "plume")
        B[f"plume{i}"] = (p, gxf)
        cen = (gxf @ np.array([0, 0, 0.45, 1.0]))[:3]
        lights.append((f"Engine_{i}", "engine", cen, (0.35, 0.55, 1.0), 450.0, 0.4))


# ------------------------------------------------------------------------------------ main


def _empty(name, col, parent=None, loc=(0, 0, 0), size=1.0):
    e = bpy.data.objects.new(name, None)
    e.empty_display_type = 'PLAIN_AXES'
    e.empty_display_size = size
    e.location = loc
    col.objects.link(e)
    if parent is not None:
        e.parent = parent
    return e


def _drive(obj, path, index, ctrl, prop, expr):
    fc = obj.driver_add(path, index) if index is not None else obj.driver_add(path)
    drv = fc.driver
    drv.type = 'SCRIPTED'
    var = drv.variables.new()
    var.name = "v"
    var.type = 'SINGLE_PROP'
    var.targets[0].id_type = 'OBJECT'
    var.targets[0].id = ctrl
    var.targets[0].data_path = f'["{prop}"]'
    drv.expression = expr
    return fc


CTRL_DEFAULTS = {"beacon": 0.0, "nav": 1.0, "running": 1.0, "engine": 0.0, "interior": 0.0,
                 "dish_az_deg": 0.0, "dish_el_deg": 0.0}
LIGHTGROUP_SHIP = "ship_lights"


def build(collection_name="SHIP", seed=7):
    rng = np.random.default_rng(seed)
    scene = bpy.context.scene
    col = bpy.data.collections.new(collection_name)
    scene.collection.children.link(col)
    root = _empty("SHIP_ROOT", col, size=5.0)
    root["tls_ship"] = "LSV-7"
    ctrl = _empty("SHIP_CTRL", col, root, size=1.0)
    for k, v in CTRL_DEFAULTS.items():
        ctrl[k] = v
        ui = ctrl.id_properties_ui(k)
        if k.startswith("dish"):
            ui.update(min=-180.0, max=180.0, soft_min=-90.0, soft_max=90.0, description=f"HGA {k}")
        else:
            ui.update(min=0.0, max=50.0, soft_min=0.0, soft_max=1.0, description=f"{k} light level (1 = nominal)")
    root["tls_ctrl"] = ctrl.name
    hull = _empty("SHIP_Hull", col, root, loc=(0, -COM_Y, 0), size=2.0)
    az = _empty("Dish_Az", col, hull, loc=tuple(AZ_PIVOT), size=1.0)
    el = _empty("Dish_El", col, az, loc=(0, 0, 0), size=0.8)
    az.rotation_mode = el.rotation_mode = 'XYZ'
    _drive(az, "rotation_euler", 2, ctrl, "dish_az_deg", "v*0.017453292519943295")
    _drive(el, "rotation_euler", 0, ctrl, "dish_el_deg", "v*0.017453292519943295")

    M = SM.build_library(ctrl)
    names = ["hull", "details", "stencils", "truss", "tanks", "rads", "aft", "mast", "gaz", "gel", "dish", "lamps",
             "interior"]
    title = {"hull": "SHIP_Hull_Bus", "details": "SHIP_Details", "stencils": "SHIP_Stencils", "truss": "SHIP_Truss",
             "tanks": "SHIP_Tanks", "rads": "SHIP_Radiators", "aft": "SHIP_Aft", "mast": "SHIP_Dish_Mast",
             "gaz": "SHIP_Dish_AzStage", "gel": "SHIP_Dish_ElStage", "dish": "SHIP_Dish_Reflector",
             "lamps": "SHIP_Lamps", "interior": "SHIP_Interior"}
    B = {n: MeshBuilder(title[n], rng) for n in names}
    lights = []
    build_bus(B, rng, lights)
    build_service(B, rng, lights)
    build_mast_and_dish(B, rng)
    build_truss(B, rng)
    build_tanks(B, rng)
    build_radiators(B, rng, lights)
    build_aft(B, rng, lights)

    parents = {"gaz": az, "gel": el, "dish": el}
    objs = {}
    for n in names:
        if B[n].empty():
            continue
        ob = B[n].to_object(M, col, parents.get(n, hull))
        objs[n] = ob
    for n in ("lamps", "interior"):
        if n in objs:
            objs[n].lightgroup = LIGHTGROUP_SHIP
    for i in range(len(THR_PHI)):
        for key in (f"grid{i}", f"plume{i}"):
            mb, xf = B[key]
            ob = mb.to_object(M, col, hull)
            ob.matrix_basis = __import__("mathutils").Matrix(xf.tolist())
            ob.lightgroup = LIGHTGROUP_SHIP
            if key.startswith("plume"):
                ob.visible_shadow = False
                ob.visible_diffuse = False
                ob.visible_glossy = False
                ob.visible_transmission = False
                ob.visible_volume_scatter = False
            objs[key] = ob
    # real lights, driven by SHIP_CTRL
    for (nm, prop, pos, colr, power, radius) in lights:
        ld = bpy.data.lights.new(f"SHIP_{nm}", 'POINT')
        ld.color = colr
        ld.energy = power * CTRL_DEFAULTS[prop]
        ld.shadow_soft_size = radius
        ld["tls_power"] = power
        lo = bpy.data.objects.new(f"SHIP_{nm}", ld)
        lo.location = tuple(pos)
        col.objects.link(lo)
        lo.parent = hull
        lo.lightgroup = LIGHTGROUP_SHIP
        _drive(ld, "energy", None, ctrl, prop, f"v*{power}")
    return root

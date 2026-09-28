"""Geometry toolkit for the hero ship (Blender 4.5, bpy + numpy).

A `MeshBuilder` batches thousands of small procedural parts into one mesh per object (fast to build,
cheap for Cycles), with per-face material, UVs in metres, a second "Seam" UV map (distance to a
blanket edge, used by the MLI shaders for stitching/tape shading) and a per-part random attribute
`part_rnd` (0..1) that shaders use for panel-to-panel variation.

Conventions: metres; primitives are authored in a local frame and placed with a 4x4 numpy matrix.
Lathe primitives revolve a (radius, height) profile about local +Z.
"""
from __future__ import annotations

import math

import bmesh
import bpy
import numpy as np

# ------------------------------------------------------------------------------------ matrices


def mat4(origin=(0, 0, 0), x=(1, 0, 0), y=(0, 1, 0), z=(0, 0, 1)) -> np.ndarray:
    m = np.eye(4)
    m[:3, 0], m[:3, 1], m[:3, 2], m[:3, 3] = x, y, z, origin
    return m


def unit(v) -> np.ndarray:
    v = np.asarray(v, float)
    n = np.linalg.norm(v)
    return v / n if n > 1e-12 else v


def frame_z(origin, z_axis, x_hint=None) -> np.ndarray:
    """Frame at `origin` whose local +Z is `z_axis`; local +X as close to `x_hint` as possible."""
    z = unit(z_axis)
    if x_hint is None:
        x_hint = (1, 0, 0) if abs(z[0]) < 0.9 else (0, 1, 0)
    xh = np.asarray(x_hint, float)
    x = unit(xh - xh.dot(z) * z)
    y = np.cross(z, x)
    return mat4(origin, x, y, z)


def along_y(y0=0.0, x=0.0, z=0.0) -> np.ndarray:
    """Frame whose local +Z is ship +Y (the lathe axis runs fore-aft). local X = ship +X, local Y = ship -Z."""
    return mat4((x, y0, z), (1, 0, 0), (0, 0, -1), (0, 1, 0))


def rot_x(a):
    c, s = math.cos(a), math.sin(a)
    m = np.eye(4)
    m[1, 1], m[1, 2], m[2, 1], m[2, 2] = c, -s, s, c
    return m


def rot_y(a):
    c, s = math.cos(a), math.sin(a)
    m = np.eye(4)
    m[0, 0], m[0, 2], m[2, 0], m[2, 2] = c, s, -s, c
    return m


def rot_z(a):
    c, s = math.cos(a), math.sin(a)
    m = np.eye(4)
    m[0, 0], m[0, 1], m[1, 0], m[1, 1] = c, -s, s, c
    return m


def trans(x, y, z):
    m = np.eye(4)
    m[:3, 3] = (x, y, z)
    return m


def polar(phi_deg: float, r: float, y: float) -> np.ndarray:
    """Ship-frame point at angle phi around the fore-aft axis (0 = +X starboard, 90 = +Z dorsal)."""
    p = math.radians(phi_deg)
    return np.array([r * math.cos(p), y, r * math.sin(p)])


def surface_frame(phi_deg: float, apothem: float, y: float) -> np.ndarray:
    """Frame on an octagon face: local X = around (tangent), local Y = ship +Y, local Z = outward normal."""
    p = math.radians(phi_deg)
    n = np.array([math.cos(p), 0.0, math.sin(p)])
    t = np.array([-math.sin(p), 0.0, math.cos(p)])
    return mat4(n * apothem + np.array([0, y, 0]), t, (0, 1, 0), n)


# ------------------------------------------------------------------------------------ builder


class MeshBuilder:
    def __init__(self, name: str, rng: np.random.Generator):
        self.name = name
        self.rng = rng
        self.vs: list[np.ndarray] = []
        self.nv = 0
        self.faces: list[tuple] = []
        self.fmat: list[str] = []
        self.fuv: list = []        # per face: None (box-projected later) or list of (u, v)
        self.fuv2: list = []       # per face: None or list of (u, v) (Seam map)
        self.frnd: list[float] = []
        self.fflat: list[bool] = []

    # -- core -------------------------------------------------------------------------------
    def add(self, verts, faces, mat: str, xf=None, uv=None, uv2=None, rnd=None, flat=False):
        v = np.asarray(verts, float).reshape(-1, 3)
        if xf is not None:
            v = v @ xf[:3, :3].T + xf[:3, 3]
        base = self.nv
        self.vs.append(v)
        self.nv += len(v)
        r = float(self.rng.random()) if rnd is None else float(rnd)
        for i, f in enumerate(faces):
            self.faces.append(tuple(base + k for k in f))
            self.fmat.append(mat)
            self.fuv.append(None if uv is None else uv[i])
            self.fuv2.append(None if uv2 is None else uv2[i])
            self.frnd.append(r)
            self.fflat.append(flat)
        return base

    def empty(self) -> bool:
        return not self.faces

    def to_object(self, materials: dict, collection, parent=None, sharp_deg=38.0, name=None):
        name = name or self.name
        V = np.concatenate(self.vs) if self.vs else np.zeros((0, 3))
        me = bpy.data.meshes.new(name)
        me.from_pydata(V.tolist(), [], self.faces)
        # materials
        names = list(dict.fromkeys(self.fmat))
        for n in names:
            me.materials.append(materials[n])
        idx = {n: i for i, n in enumerate(names)}
        me.polygons.foreach_set("material_index", np.array([idx[m] for m in self.fmat], np.int32))
        # UVs
        nl = len(me.loops)
        ls = np.zeros(len(me.polygons), np.int32)
        lt = np.zeros(len(me.polygons), np.int32)
        me.polygons.foreach_get("loop_start", ls)
        me.polygons.foreach_get("loop_total", lt)
        lv = np.zeros(nl, np.int32)
        me.loops.foreach_get("vertex_index", lv)
        pn = np.zeros(len(me.polygons) * 3)
        me.polygons.foreach_get("normal", pn)
        pn = pn.reshape(-1, 3)
        co = V[lv]
        loop_poly = np.repeat(np.arange(len(me.polygons)), lt)
        ax = np.abs(pn).argmax(1)[loop_poly]
        uv = np.where(ax[:, None] == 0, co[:, [1, 2]], np.where(ax[:, None] == 1, co[:, [0, 2]], co[:, [0, 1]]))
        uv2 = np.full((nl, 2), 9.0)
        for fi, (u, u2) in enumerate(zip(self.fuv, self.fuv2)):
            if u is not None:
                uv[ls[fi]:ls[fi] + lt[fi]] = u
            if u2 is not None:
                uv2[ls[fi]:ls[fi] + lt[fi]] = u2
        l1 = me.uv_layers.new(name="UVMap")
        l1.data.foreach_set("uv", uv.astype(np.float32).ravel())
        l2 = me.uv_layers.new(name="Seam")
        l2.data.foreach_set("uv", uv2.astype(np.float32).ravel())
        me.uv_layers.active = l1
        # per-part random
        at = me.attributes.new("part_rnd", 'FLOAT', 'FACE')
        at.data.foreach_set("value", np.array(self.frnd, np.float32))
        # shading
        me.shade_smooth()
        me.set_sharp_from_angle(angle=math.radians(sharp_deg))
        if any(self.fflat):
            sf = me.attributes.get("sharp_face") or me.attributes.new("sharp_face", 'BOOLEAN', 'FACE')
            cur = np.zeros(len(me.polygons), bool)
            sf.data.foreach_get("value", cur)
            sf.data.foreach_set("value", cur | np.array(self.fflat, bool))
        me.update()
        ob = bpy.data.objects.new(name, me)
        collection.objects.link(ob)
        if parent is not None:
            ob.parent = parent
        return ob

    # -- primitives -------------------------------------------------------------------------
    def lathe(self, prof, segs: int, mat: str, xf=None, phase=0.0, rnd=None, flat=False,
              arc=None):
        """Revolve profile [(r, z), ...] about local +Z. r == 0 makes a pole. `arc`=(a0, a1) radians
        builds an open partial revolution instead of a full one."""
        prof = np.asarray(prof, float)
        m = len(prof)
        full = arc is None
        nseg = segs
        if full:
            th = phase + 2 * math.pi * np.arange(segs + 1) / segs
        else:
            th = np.linspace(arc[0], arc[1], segs + 1)
        ncol = segs if full else segs + 1
        rmax = max(prof[:, 0].max(), 1e-3)
        circ = rmax * (th[-1] - th[0])
        s = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(prof, axis=0), axis=1))])
        verts = []
        ring = []
        for i, (r, z) in enumerate(prof):
            if r <= 1e-9:
                ring.append([len(verts)] * (ncol + (1 if full else 0)))
                verts.append((0.0, 0.0, z))
            else:
                ids = []
                for k in range(ncol):
                    ids.append(len(verts))
                    verts.append((r * math.cos(th[k]), r * math.sin(th[k]), z))
                if full:
                    ids.append(ids[0])
                ring.append(ids)
        faces, uvs = [], []
        for i in range(m - 1):
            a, b = ring[i], ring[i + 1]
            pa, pb = prof[i][0] <= 1e-9, prof[i + 1][0] <= 1e-9
            if pa and pb:
                continue
            for k in range(nseg):
                u0 = (th[k] - th[0]) / (th[-1] - th[0]) * circ
                u1 = (th[k + 1] - th[0]) / (th[-1] - th[0]) * circ
                if pa:
                    faces.append((a[0], b[k + 1], b[k]))
                    uvs.append([(0.5 * (u0 + u1), s[i]), (u1, s[i + 1]), (u0, s[i + 1])])
                elif pb:
                    faces.append((a[k], a[k + 1], b[0]))
                    uvs.append([(u0, s[i]), (u1, s[i]), (0.5 * (u0 + u1), s[i + 1])])
                else:
                    faces.append((a[k], a[k + 1], b[k + 1], b[k]))
                    uvs.append([(u0, s[i]), (u1, s[i]), (u1, s[i + 1]), (u0, s[i + 1])])
        return self.add(verts, faces, mat, xf, uv=uvs, rnd=rnd, flat=flat)

    def cylinder(self, r, h, mat, xf=None, segs=16, chamfer=0.0, rnd=None, caps=True, z0=0.0):
        c = min(chamfer, r * 0.4, h * 0.4)
        if caps:
            prof = [(0, z0), (r - c, z0), (r, z0 + c), (r, z0 + h - c), (r - c, z0 + h), (0, z0 + h)]
            if c <= 0:
                prof = [(0, z0), (r, z0), (r, z0 + h), (0, z0 + h)]
        else:
            prof = [(r, z0), (r, z0 + h)]
        return self.lathe(prof, segs, mat, xf, rnd=rnd)

    def tube(self, p0, p1, r, mat, segs=8, caps=True, rnd=None, x_hint=None):
        p0, p1 = np.asarray(p0, float), np.asarray(p1, float)
        d = p1 - p0
        L = float(np.linalg.norm(d))
        if L < 1e-6:
            return None
        xf = frame_z(p0, d, x_hint)
        prof = [(0, 0), (r, 0), (r, L), (0, L)] if caps else [(r, 0), (r, L)]
        return self.lathe(prof, segs, mat, xf, rnd=rnd)

    def sphere(self, r, mat, xf=None, segs=32, rings=16, rnd=None, squash=1.0):
        prof = [(r * math.sin(math.pi * i / rings), -r * squash * math.cos(math.pi * i / rings))
                for i in range(rings + 1)]
        prof[0] = (0.0, prof[0][1])
        prof[-1] = (0.0, prof[-1][1])
        return self.lathe(prof, segs, mat, xf, rnd=rnd)

    def box(self, size, mat, xf=None, center=(0, 0, 0), bevel=0.0, segments=1, rnd=None, flat=False):
        sx, sy, sz = size
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        for v in bm.verts:
            v.co.x, v.co.y, v.co.z = v.co.x * sx + center[0], v.co.y * sy + center[1], v.co.z * sz + center[2]
        b = min(bevel, 0.45 * min(sx, sy, sz))
        if b > 0:
            bmesh.ops.bevel(bm, geom=list(bm.edges), offset=b, offset_type='OFFSET', segments=segments,
                            profile=0.5, affect='EDGES', clamp_overlap=True)
        bm.verts.index_update()
        verts = [v.co[:] for v in bm.verts]
        faces = [tuple(v.index for v in f.verts) for f in bm.faces]
        bm.free()
        return self.add(verts, faces, mat, xf, rnd=rnd, flat=flat)

    def beam(self, p0, p1, w, h, mat, up=(0, 0, 1), bevel=0.004, rnd=None):
        """Rectangular beam from p0 to p1 (w across, h along `up`)."""
        p0, p1 = np.asarray(p0, float), np.asarray(p1, float)
        d = p1 - p0
        L = float(np.linalg.norm(d))
        xf = frame_z(p0, d, up)  # local X ~ up
        return self.box((h, w, L), mat, xf, center=(0, 0, L / 2), bevel=bevel, rnd=rnd)

    def grid(self, w, h, nu, nv, mat, xf=None, height=None, uv_off=(0.0, 0.0), uv_rot=0.0, seam_uv=True,
             rnd=None, back=False, us=None, vs=None):
        """Rectangular grid in local XY centred at origin, displaced along +Z by height(u, v) (u, v in
        metres from the lower-left corner). UVMap = metres (+offset/rotation), Seam = distance to the
        nearest edge along each axis."""
        us = np.linspace(0, w, nu + 1) if us is None else np.asarray(us, float)
        vs = np.linspace(0, h, nv + 1) if vs is None else np.asarray(vs, float)
        nu, nv = len(us) - 1, len(vs) - 1
        U, Vv = np.meshgrid(us, vs, indexing="xy")
        Z = height(U, Vv) if height is not None else np.zeros_like(U)
        P = np.stack([U - w / 2, Vv - h / 2, Z], -1).reshape(-1, 3)
        idx = np.arange((nu + 1) * (nv + 1)).reshape(nv + 1, nu + 1)
        c, s = math.cos(uv_rot), math.sin(uv_rot)
        UVm = np.stack([c * U - s * Vv + uv_off[0], s * U + c * Vv + uv_off[1]], -1)
        SE = np.stack([np.minimum(U, w - U), np.minimum(Vv, h - Vv)], -1)
        faces, uvs, uv2 = [], [], []
        for j in range(nv):
            for i in range(nu):
                q = [(j, i), (j, i + 1), (j + 1, i + 1), (j + 1, i)]
                if back:
                    q = q[::-1]
                faces.append(tuple(int(idx[a, b]) for a, b in q))
                uvs.append([tuple(UVm[a, b]) for a, b in q])
                uv2.append([tuple(SE[a, b]) for a, b in q])
        return self.add(P, faces, mat, xf, uv=uvs, uv2=uv2 if seam_uv else None, rnd=rnd)

    def polygon_plate(self, pts2d, thick, mat, xf=None, rnd=None):
        """Flat extruded convex polygon (local XY, thickness along +Z from 0..thick)."""
        n = len(pts2d)
        verts = [(x, y, 0.0) for x, y in pts2d] + [(x, y, thick) for x, y in pts2d]
        faces = [tuple(range(n - 1, -1, -1)), tuple(range(n, 2 * n))]
        for i in range(n):
            j = (i + 1) % n
            faces.append((i, j, n + j, n + i))
        return self.add(verts, faces, mat, xf, rnd=rnd)

    def mesh_data(self, verts, faces, mat, xf=None, rnd=None, uv=None):
        return self.add(verts, faces, mat, xf, rnd=rnd, uv=uv)

    # -- details ----------------------------------------------------------------------------
    def bolt(self, xf, mat, r=0.011, h=0.008):
        """Hex-head bolt with washer; local +Z = out of the surface."""
        wr = r * 1.55
        self.lathe([(0, 0), (wr, 0), (wr, 0.0018), (r, 0.0018), (r, h - 0.0015), (r * 0.8, h), (0, h)],
                   6, mat, xf, phase=math.pi / 6)

    def bolt_ring(self, xf, radius, n, mat, r=0.011, h=0.008, phase=0.0):
        for k in range(n):
            a = phase + 2 * math.pi * k / n
            self.bolt(xf @ trans(radius * math.cos(a), radius * math.sin(a), 0), mat, r, h)

    def handrail(self, p0, p1, normal, mat_rail, mat_foot, standoff=0.075, n_feet=None, bolt_mat=None):
        """EVA handrail: rounded bar on standoffs, running from p0 to p1 over a surface with `normal`."""
        p0, p1, nrm = np.asarray(p0, float), np.asarray(p1, float), unit(normal)
        L = float(np.linalg.norm(p1 - p0))
        if n_feet is None:
            n_feet = max(2, int(L / 0.55) + 1)
        a0, a1 = p0 + nrm * standoff, p1 + nrm * standoff
        d = unit(p1 - p0)
        self.tube(a0 - d * 0.02, a1 + d * 0.02, 0.0165, mat_rail, segs=10)
        # rounded ends
        for q in (a0 - d * 0.02, a1 + d * 0.02):
            self.sphere(0.0165, mat_rail, trans(*q), segs=10, rings=5)
        for k in range(n_feet):
            t = k / (n_feet - 1)
            q = p0 + (p1 - p0) * (0.04 + 0.92 * t)
            self.tube(q, q + nrm * standoff, 0.012, mat_rail, segs=8)
            fxf = frame_z(q, nrm, d)
            self.box((0.06, 0.04, 0.008), mat_foot, fxf, center=(0, 0, 0.004), bevel=0.002)
            if bolt_mat:
                for sgn in (-1, 1):
                    self.bolt(fxf @ trans(sgn * 0.022, 0, 0.008), bolt_mat, r=0.0045, h=0.004)


# ------------------------------------------------------------------------------------ text


_FONTS: dict = {}


def text_geometry(body: str, font_path: str, size: float, align="CENTER", spacing=1.0):
    """Blender text converted to mesh. Returns (verts (n,3), faces) lying in XY, facing +Z, centred."""
    key = font_path
    if key not in _FONTS:
        _FONTS[key] = bpy.data.fonts.load(font_path, check_existing=True)
    cu = bpy.data.curves.new("_tls_txt", 'FONT')
    cu.body = body
    cu.size = size
    cu.font = _FONTS[key]
    cu.align_x = align
    cu.align_y = 'CENTER'
    cu.space_character = spacing
    cu.resolution_u = 3
    ob = bpy.data.objects.new("_tls_txt", cu)
    bpy.context.scene.collection.objects.link(ob)
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    me = ev.to_mesh()
    verts = np.array([v.co[:] for v in me.vertices]) if len(me.vertices) else np.zeros((0, 3))
    faces = [tuple(p.vertices) for p in me.polygons]
    ev.to_mesh_clear()
    bpy.data.objects.remove(ob)
    bpy.data.curves.remove(cu)
    return verts, faces

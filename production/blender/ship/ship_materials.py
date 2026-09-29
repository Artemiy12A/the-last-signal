"""Physically based materials for the hero ship (Cycles).

Textures come from production/cache/textures (fetched by fetch_textures.py; CC0 ambientCG). If a map
is missing the shader falls back to procedural noise so the ship still builds (with a warning).

All UV-driven shaders assume the builder's "UVMap" is in metres. Emissive shaders read a Value node
named CTRL_<prop> that is driven by the custom property <prop> on the SHIP_CTRL empty.
"""
from __future__ import annotations

import math
import os
from pathlib import Path

import bpy

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
TEX_DIR = Path(os.environ.get("TLS_TEXTURE_DIR", REPO / "production" / "cache" / "textures"))

USE_AO = True           # crevice dust/frost via the AO shader node (costs a little render time)
AO_SAMPLES = 6

_warned: set = set()


# ------------------------------------------------------------------------------------ node helpers


class NT:
    """Tiny node-graph helper. Values can be sockets (linked) or constants."""

    def __init__(self, mat):
        self.mat = mat
        self.nt = mat.node_tree
        self.nt.nodes.clear()
        self.out = self.nt.nodes.new("ShaderNodeOutputMaterial")
        self.out.location = (1200, 0)
        self._x = 0

    def n(self, typ, ins=None, **props):
        nd = self.nt.nodes.new(typ)
        nd.location = (self._x % 1000, -(self._x // 1000) * 200)
        self._x += 180
        for k, v in props.items():
            setattr(nd, k, v)
        if ins:
            for key, val in ins.items():
                self.set(nd.inputs[key], val)
        return nd

    def set(self, sock, val):
        if isinstance(val, bpy.types.NodeSocket):
            self.nt.links.new(val, sock)
        elif isinstance(val, bpy.types.Node):
            self.nt.links.new(val.outputs[0], sock)
        else:
            if isinstance(val, (tuple, list)) and len(val) == 3:
                try:
                    if len(sock.default_value) == 4:
                        val = (*val, 1.0)
                except TypeError:
                    pass
            sock.default_value = val

    def link(self, a, b):
        self.nt.links.new(a, b)

    # math shortcuts -------------------------------------------------------------------------
    def math(self, op, a, b=0.0, c=0.0, clamp=False):
        nd = self.n("ShaderNodeMath", operation=op, use_clamp=clamp)
        self.set(nd.inputs[0], a)
        self.set(nd.inputs[1], b)
        if op in ("MULTIPLY_ADD", "COMPARE", "SMOOTH_MIN", "SMOOTH_MAX", "WRAP"):
            self.set(nd.inputs[2], c)
        return nd.outputs[0]

    def mul(self, a, b):
        return self.math("MULTIPLY", a, b)

    def add(self, a, b):
        return self.math("ADD", a, b)

    def sub(self, a, b):
        return self.math("SUBTRACT", a, b)

    def vmath(self, op, a, b=(0, 0, 0), out=0):
        nd = self.n("ShaderNodeVectorMath", operation=op)
        self.set(nd.inputs[0], a)
        self.set(nd.inputs[1], b)
        return nd.outputs[out]

    def smooth(self, x, e0, e1):
        """smoothstep(e0, e1, x) via Map Range."""
        nd = self.n("ShaderNodeMapRange", interpolation_type='SMOOTHSTEP', clamp=True)
        self.set(nd.inputs["Value"], x)
        self.set(nd.inputs["From Min"], e0)
        self.set(nd.inputs["From Max"], e1)
        nd.inputs["To Min"].default_value = 0.0
        nd.inputs["To Max"].default_value = 1.0
        return nd.outputs[0]

    def maprange(self, x, a0, a1, b0, b1, clamp=True):
        nd = self.n("ShaderNodeMapRange", clamp=clamp)
        self.set(nd.inputs["Value"], x)
        nd.inputs["From Min"].default_value = a0
        nd.inputs["From Max"].default_value = a1
        nd.inputs["To Min"].default_value = b0
        nd.inputs["To Max"].default_value = b1
        return nd.outputs[0]

    def mix(self, fac, a, b, blend='MIX'):
        nd = self.n("ShaderNodeMix", data_type='RGBA', blend_type=blend, clamp_result=False)
        self.set(nd.inputs[0], fac)
        self.set(nd.inputs[6], a)
        self.set(nd.inputs[7], b)
        return nd.outputs[2]

    def mixf(self, fac, a, b):
        nd = self.n("ShaderNodeMix", data_type='FLOAT')
        self.set(nd.inputs[0], fac)
        self.set(nd.inputs[2], a)
        self.set(nd.inputs[3], b)
        return nd.outputs[0]

    def rgb(self, c):
        nd = self.n("ShaderNodeRGB")
        nd.outputs[0].default_value = (*c, 1.0)
        return nd.outputs[0]

    def uv(self, name="UVMap"):
        nd = self.n("ShaderNodeUVMap", uv_map=name)
        return nd.outputs[0]

    def mapping(self, vec, scale=(1, 1, 1), rot=(0, 0, 0), loc=(0, 0, 0)):
        nd = self.n("ShaderNodeMapping")
        self.set(nd.inputs["Vector"], vec)
        nd.inputs["Scale"].default_value = scale
        nd.inputs["Rotation"].default_value = rot
        nd.inputs["Location"].default_value = loc
        return nd.outputs[0]

    def sep(self, vec):
        nd = self.n("ShaderNodeSeparateXYZ")
        self.set(nd.inputs[0], vec)
        return nd.outputs

    def comb(self, x, y, z=0.0):
        nd = self.n("ShaderNodeCombineXYZ")
        self.set(nd.inputs[0], x)
        self.set(nd.inputs[1], y)
        self.set(nd.inputs[2], z)
        return nd.outputs[0]

    def attr(self, name, kind='GEOMETRY'):
        nd = self.n("ShaderNodeAttribute", attribute_name=name, attribute_type=kind)
        return nd.outputs["Fac"]

    def noise(self, vec, scale, detail=4.0, rough=0.55, dim='3D', out="Fac"):
        nd = self.n("ShaderNodeTexNoise", noise_dimensions=dim)
        self.set(nd.inputs["Vector"], vec)
        nd.inputs["Scale"].default_value = scale
        nd.inputs["Detail"].default_value = detail
        nd.inputs["Roughness"].default_value = rough
        return nd.outputs[out]

    def voronoi(self, vec, scale, feature='F1', rnd=1.0, out="Distance"):
        nd = self.n("ShaderNodeTexVoronoi", feature=feature)
        self.set(nd.inputs["Vector"], vec)
        nd.inputs["Scale"].default_value = scale
        nd.inputs["Randomness"].default_value = rnd
        return nd.outputs[out]

    def image(self, tex_id, mapname, vec, color=False, fallback_scale=40.0):
        """Image texture from the cache; procedural fallback if missing. Returns (color_socket, alpha)."""
        p = TEX_DIR / tex_id / f"{tex_id}_{mapname}.jpg"
        if p.exists():
            img = bpy.data.images.load(str(p), check_existing=True)
            img.colorspace_settings.name = 'sRGB' if color else 'Non-Color'
            nd = self.n("ShaderNodeTexImage", image=img, interpolation='Linear', extension='REPEAT')
            self.set(nd.inputs["Vector"], vec)
            return nd.outputs["Color"]
        if str(p) not in _warned:
            print(f"[ship] WARNING missing texture {p} - using procedural fallback "
                  f"(run production/blender/ship/fetch_textures.py)")
            _warned.add(str(p))
        if mapname.startswith("Normal"):
            nz = self.n("ShaderNodeTexNoise")
            self.set(nz.inputs["Vector"], vec)
            nz.inputs["Scale"].default_value = fallback_scale
            nz.inputs["Detail"].default_value = 8
            return self.mix(0.25, (0.5, 0.5, 1.0), nz.outputs["Color"])
        return self.noise(vec, fallback_scale, 6)

    def normal_map(self, col, strength, uvname="UVMap"):
        nd = self.n("ShaderNodeNormalMap", space='TANGENT', uv_map=uvname)
        nd.inputs["Strength"].default_value = strength
        self.set(nd.inputs["Color"], col)
        return nd.outputs[0]

    def bump(self, height, strength, dist, normal=None):
        nd = self.n("ShaderNodeBump")
        nd.inputs["Strength"].default_value = strength
        nd.inputs["Distance"].default_value = dist
        self.set(nd.inputs["Height"], height)
        if normal is not None:
            self.set(nd.inputs["Normal"], normal)
        return nd.outputs[0]

    def tangent_uv(self, uvname="UVMap"):
        nd = self.n("ShaderNodeTangent", direction_type='UV_MAP', uv_map=uvname)
        return nd.outputs[0]

    def ao(self, dist=0.3):
        nd = self.n("ShaderNodeAmbientOcclusion", samples=AO_SAMPLES, only_local=True, inside=False)
        nd.inputs["Distance"].default_value = dist
        return nd.outputs["AO"]

    def principled(self, **ins):
        p = self.n("ShaderNodeBsdfPrincipled")
        names = {
            "base": "Base Color", "metal": "Metallic", "rough": "Roughness", "ior": "IOR",
            "normal": "Normal", "spec": "Specular IOR Level", "aniso": "Anisotropic",
            "aniso_rot": "Anisotropic Rotation", "tangent": "Tangent", "coat": "Coat Weight",
            "coat_rough": "Coat Roughness", "coat_normal": "Coat Normal", "emit": "Emission Color",
            "emit_str": "Emission Strength", "film": "Thin Film Thickness", "film_ior": "Thin Film IOR",
            "trans": "Transmission Weight", "alpha": "Alpha", "spec_tint": "Specular Tint",
            "diff_rough": "Diffuse Roughness",
        }
        for k, v in ins.items():
            val = v
            if k in ("base", "emit", "spec_tint") and isinstance(v, tuple) and len(v) == 3:
                val = (*v, 1.0)
            self.set(p.inputs[names[k]], val)
        return p

    def output(self, surf=None, vol=None, disp=None):
        if surf is not None:
            self.set(self.out.inputs["Surface"], surf)
        if vol is not None:
            self.set(self.out.inputs["Volume"], vol)
        if disp is not None:
            self.set(self.out.inputs["Displacement"], disp)

    def ctrl(self, prop: str, ctrl_obj):
        """Value node driven by SHIP_CTRL[prop]."""
        nd = self.n("ShaderNodeValue", name=f"CTRL_{prop}", label=f"CTRL_{prop}")
        nd.outputs[0].default_value = float(ctrl_obj.get(prop, 0.0)) if ctrl_obj else 0.0
        if ctrl_obj is not None:
            fc = nd.outputs[0].driver_add("default_value")
            drv = fc.driver
            drv.type = 'AVERAGE'
            var = drv.variables.new()
            var.name = "v"
            var.type = 'SINGLE_PROP'
            var.targets[0].id_type = 'OBJECT'
            var.targets[0].id = ctrl_obj
            var.targets[0].data_path = f'["{prop}"]'
        return nd.outputs[0]


def _new(name):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    return m, NT(m)


# ------------------------------------------------------------------------------------ shared pieces


def _crevice(t: NT, dist=0.25):
    """1 in open areas, towards 0 in crevices."""
    if not USE_AO:
        return 1.0
    return t.ao(dist)


def _smudge(t: NT, uvv, scale_m=1.7):
    """Fingerprint/handling smudge mask 0..1 from SurfaceImperfections003."""
    vec = t.mapping(uvv, scale=(1 / scale_m, 1 / scale_m, 1), rot=(0, 0, 0.6))
    return t.image("SurfaceImperfections003", "Opacity", vec)


def _scratch(t: NT, uvv, scale_m=0.9):
    vec = t.mapping(uvv, scale=(1 / scale_m, 1 / scale_m, 1), rot=(0, 0, 1.1), loc=(0.37, 0.11, 0))
    return t.image("Scratches002", "Opacity", vec)


# ------------------------------------------------------------------------------------ MLI


def mli(name, kind="gold", tile_m=1.05):
    """Crinkled multi-layer insulation. kind: gold (aluminised kapton), silver, black (carbon kapton).
    Uses Seam UV (distance to blanket edge) for stitching, edge folds and tacks."""
    m, t = _new(name)
    uvv = t.uv()
    rnd = t.attr("part_rnd")
    tex_id = "Foil001" if kind == "silver" else "Foil002"
    fvec = t.mapping(uvv, scale=(1 / tile_m, 1 / tile_m, 1))
    ncol = t.image(tex_id, "NormalGL", fvec)
    nstr = {"gold": 1.0, "silver": 0.95, "black": 0.8}[kind]
    fvec2 = t.mapping(uvv, scale=(1 / 0.31, 1 / 0.31, 1), rot=(0, 0, 0.7), loc=(0.3, 0.6, 0))
    fine = t.image(tex_id, "Displacement", fvec2)
    # low-frequency blanket billow on top of the crinkle map
    billow = t.noise(uvv, 1.3, detail=2.0, rough=0.5)
    seam = t.sep(t.uv("Seam"))
    edge = t.math("MINIMUM", seam[0], seam[1])
    # stitch rows 22 mm in from the blanket edge, dashes 9 mm pitch
    along = t.mixf(t.math("LESS_THAN", seam[0], seam[1]), t.sep(uvv)[0], t.sep(uvv)[1])
    band = t.math("SUBTRACT", 1.0, t.smooth(t.math("ABSOLUTE", t.sub(edge, 0.022)), 0.0008, 0.0016))
    dash = t.math("LESS_THAN", t.math("FRACT", t.mul(along, 1 / 0.009)), 0.55)
    stitch = t.mul(band, dash)
    # tacks: 30 cm grid of small buttons (in blanket-local coords from the Seam distances are not
    # enough, so use UV metres; blankets get random UV offsets so the grid shifts per blanket)
    tv = t.mapping(uvv, scale=(1 / 0.42, 1 / 0.42, 1))
    fr = t.vmath("FRACTION", tv)
    dctr = t.vmath("LENGTH", t.vmath("SUBTRACT", fr, (0.5, 0.5, 0.0)), out=1)
    tack = t.mul(t.math("SUBTRACT", 1.0, t.smooth(dctr, 0.018, 0.024)), 0.8)
    dimple = t.smooth(dctr, 0.02, 0.16)
    edge_fold = t.math("SUBTRACT", 1.0, t.smooth(edge, 0.0, 0.012))   # 1 at the tucked edge
    # normal: crinkle map + billow + dimples around tacks
    nrm = t.normal_map(ncol, nstr)
    nrm = t.bump(fine, 0.22, 0.004, nrm)
    h = t.add(t.mul(billow, 1.0), t.mul(dimple, 0.5))
    nrm = t.bump(h, 0.3, 0.03, nrm)
    nrm = t.bump(stitch, 0.4, 0.0006, nrm)
    smudge = _smudge(t, uvv)
    ao = _crevice(t)
    if kind == "gold":
        c_new = (0.86, 0.56, 0.19)
        c_old = (0.64, 0.36, 0.10)
        base = t.mix(t.mul(rnd, 0.6), c_new, c_old)
        rough = t.add(0.1, t.mul(smudge, 0.16))
        metal = 0.93
    elif kind == "silver":
        base = t.mix(t.mul(rnd, 0.4), (0.86, 0.87, 0.89), (0.72, 0.73, 0.76))
        rough = t.add(0.1, t.mul(smudge, 0.18))
        metal = 0.97
    else:
        base = t.mix(rnd, (0.018, 0.018, 0.02), (0.03, 0.03, 0.032))
        rough = t.add(0.28, t.mul(smudge, 0.3))
        metal = 0.0
    rough = t.add(rough, t.mul(t.noise(uvv, 3.0, 3), 0.06))
    # edge folds are darker (shadowed tuck) and matte; stitching is white polyester thread
    base = t.mix(t.mul(edge_fold, 0.5), base, t.mix(0.5, base, (0.0, 0.0, 0.0), 'MULTIPLY'))
    thread = (0.55, 0.53, 0.48)
    base = t.mix(stitch, base, thread)
    base = t.mix(tack, base, (0.62, 0.60, 0.55))
    metal_s = t.math("SUBTRACT", metal, t.math("MAXIMUM", stitch, tack), clamp=True)
    rough = t.mixf(t.math("MAXIMUM", stitch, tack), rough, 0.6)
    # crevice dust / frost
    if USE_AO:
        dust = t.math("SUBTRACT", 1.0, t.smooth(ao, 0.25, 0.9))
        dust = t.mul(dust, t.smooth(t.noise(uvv, 9.0, 4), 0.35, 0.65))
        base = t.mix(t.mul(dust, 0.55), base, (0.42, 0.43, 0.46))
        rough = t.mixf(t.mul(dust, 0.8), rough, 0.75)
        metal_s = t.mixf(t.mul(dust, 0.7), metal_s, 0.0)
    p = t.principled(base=base, metal=metal_s, rough=rough, normal=nrm, aniso=0.25,
                     tangent=t.tangent_uv(), spec=0.5)
    t.output(p)
    return m


def tape(name, kind="silver"):
    """Aluminised / kapton tape over blanket seams: flatter, finely wrinkled."""
    m, t = _new(name)
    uvv = t.uv()
    fvec = t.mapping(uvv, scale=(1 / 0.25, 1 / 0.9, 1))
    ncol = t.image("Foil001", "NormalGL", fvec)
    nrm = t.normal_map(ncol, 0.35)
    smudge = _smudge(t, uvv, 1.1)
    col = (0.86, 0.86, 0.88) if kind == "silver" else (0.78, 0.46, 0.14)
    p = t.principled(base=col, metal=1.0, rough=t.add(0.14, t.mul(smudge, 0.3)), normal=nrm)
    t.output(p)
    return m


# ------------------------------------------------------------------------------------ paints


def paint(name, base=0.70, rough=0.48, tint=(1.0, 1.0, 1.0), pits=True, grime=1.0, seams_obj=False):
    """Thermal-control paint (white by default): panel tint variation, orange peel, smudges,
    scratches, micrometeoroid pits with spall halos, crevice grime + frost."""
    m, t = _new(name)
    uvv = t.uv()
    rnd = t.attr("part_rnd")
    col0 = tuple(base * c for c in tint)
    colw = tuple(min(1.0, base * c * 1.06) for c in tint)
    colc = tuple(base * c * 0.9 for c in (tint[0] * 0.97, tint[1] * 0.99, tint[2] * 1.03))
    c = t.mix(rnd, t.mix(0.5, colc, colw), col0)
    smudge = _smudge(t, uvv, 2.3)
    scr = _scratch(t, uvv, 1.3)
    c = t.mix(t.mul(smudge, 0.45 * grime), c, t.mix(0.5, c, (0.30, 0.28, 0.25), 'MULTIPLY'))
    c = t.mix(t.mul(scr, 0.35), c, t.mix(0.5, c, (0.55, 0.55, 0.56), 'MULTIPLY'))
    r = t.add(rough, t.add(t.mul(smudge, 0.2 * grime), t.mul(scr, 0.15)))
    r = t.add(r, t.mul(t.noise(uvv, 4.0, 3), 0.06))
    h = t.mul(t.noise(uvv, 180.0, 2, 0.5), 0.3)        # orange peel
    h = t.sub(h, t.mul(scr, 0.4))
    if pits:
        # sparse micrometeoroid pits (1-3 mm) with lighter spall rings
        vd = t.voronoi(uvv, 11.0, out="Distance")
        vc = t.sep(t.n("ShaderNodeTexVoronoi", ins={"Vector": uvv, "Scale": 11.0}).outputs["Color"])[0]
        keep = t.math("GREATER_THAN", vc, 0.72)
        pit = t.mul(t.math("SUBTRACT", 1.0, t.smooth(vd, 0.012, 0.022)), keep)
        ring = t.mul(t.math("SUBTRACT", t.smooth(vd, 0.015, 0.03), t.smooth(vd, 0.03, 0.06)), keep)
        c = t.mix(t.mul(pit, 0.85), c, (0.06, 0.055, 0.05))
        c = t.mix(t.mul(ring, 0.25), c, (0.85, 0.85, 0.86))
        r = t.mixf(pit, r, 0.85)
        h = t.sub(h, t.mul(pit, 2.0))
    nrm = t.bump(h, 0.12, 0.002)
    if USE_AO:
        ao = _crevice(t, 0.2)
        cre = t.math("SUBTRACT", 1.0, t.smooth(ao, 0.2, 0.95))
        c = t.mix(t.mul(cre, 0.55 * grime), c, (0.16, 0.15, 0.14))
        frost = t.mul(cre, t.smooth(t.noise(uvv, 30.0, 6, 0.7), 0.52, 0.62))
        c = t.mix(t.mul(frost, 0.8), c, (0.80, 0.84, 0.90))
        r = t.mixf(cre, r, 0.7)
    p = t.principled(base=c, metal=0.0, rough=r, normal=nrm, spec=0.5)
    t.output(p)
    return m


def dish_paint(name):
    """White dish reflector with radial panel seams (24 petals, 2 rings) in object space."""
    m, t = _new(name)
    oc = t.n("ShaderNodeTexCoord").outputs["Object"]
    x, y, z = t.sep(oc)
    ang = t.math("ARCTAN2", y, x)
    rad = t.vmath("LENGTH", t.comb(x, y, 0.0), out=1)
    petal = t.math("FRACT", t.mul(t.add(ang, math.pi), 24 / (2 * math.pi)))
    d_rad = t.mul(t.math("MINIMUM", petal, t.math("SUBTRACT", 1.0, petal)), t.mul(rad, 2 * math.pi / 24))
    ring = t.math("MINIMUM", t.math("ABSOLUTE", t.sub(rad, 1.55)), t.math("ABSOLUTE", t.sub(rad, 2.85)))
    dmin = t.math("MINIMUM", d_rad, ring)
    gap = t.mul(t.math("SUBTRACT", 1.0, t.smooth(dmin, 0.0012, 0.0035)), 0.7)
    uvv = t.uv()
    smudge = _smudge(t, uvv, 2.5)
    pr = t.math("FLOOR", t.mul(t.add(ang, math.pi), 24 / (2 * math.pi)))
    wn = t.n("ShaderNodeTexWhiteNoise", noise_dimensions='1D')
    t.set(wn.inputs["W"], pr)
    pv = wn.outputs["Value"]
    c = t.mix(pv, (0.56, 0.555, 0.54), (0.64, 0.635, 0.62))
    c = t.mix(t.mul(smudge, 0.4), c, (0.36, 0.34, 0.31))
    c = t.mix(gap, c, t.mix(0.5, c, (0.25, 0.25, 0.25), 'MULTIPLY'))
    r = t.add(0.36, t.add(t.mul(smudge, 0.2), t.mul(pv, 0.08)))
    h = t.sub(t.mul(t.noise(uvv, 150.0, 2), 0.2), t.mul(gap, 1.0))
    h = t.add(h, t.mul(t.noise(oc, 1.1, 2), 1.5))
    nrm = t.bump(h, 0.12, 0.002)
    if USE_AO:
        ao = _crevice(t, 0.4)
        c = t.mix(t.mul(t.math("SUBTRACT", 1.0, ao), 0.5), c, (0.1, 0.1, 0.1))
    p = t.principled(base=c, rough=r, normal=nrm, spec=0.5)
    t.output(p)
    return m


# ------------------------------------------------------------------------------------ metals


def brushed_alu(name, base=(0.80, 0.81, 0.83), rough=0.22, aniso=0.55):
    """Bare brushed aluminium; brush lines follow UV v (tube length)."""
    m, t = _new(name)
    uvv = t.uv()
    vec = t.mapping(uvv, scale=(1 / 0.35, 1 / 0.35, 1), rot=(0, 0, math.pi / 2))
    rtex = t.image("Metal009", "Roughness", vec)
    ntex = t.image("Metal009", "NormalGL", vec)
    rnd = t.attr("part_rnd")
    c = t.mix(t.mul(rnd, 0.6), base, tuple(b * 0.86 for b in base))
    smudge = _smudge(t, uvv, 1.4)
    r = t.add(t.add(rough, t.mul(rtex, 0.22)), t.mul(smudge, 0.2))
    nrm = t.normal_map(ntex, 0.35)
    p = t.principled(base=c, metal=1.0, rough=r, normal=nrm, aniso=aniso, tangent=t.tangent_uv())
    t.output(p)
    return m


def anodized(name, base=(0.50, 0.51, 0.53), rough=0.34, film=0.0):
    m, t = _new(name)
    uvv = t.uv()
    rnd = t.attr("part_rnd")
    c = t.mix(t.mul(rnd, 0.5), base, tuple(b * 0.85 for b in base))
    smudge = _smudge(t, uvv, 1.2)
    r = t.add(rough, t.mul(smudge, 0.2))
    r = t.add(r, t.mul(t.noise(uvv, 20.0, 3), 0.05))
    p = t.principled(base=c, metal=1.0, rough=r, film=film, film_ior=1.6)
    t.output(p)
    return m


def composite(name):
    """Dark carbon-fibre composite tubes with a glossy resin coat and a fine weave bump."""
    m, t = _new(name)
    uvv = t.uv()
    w1 = t.n("ShaderNodeTexWave", wave_type='BANDS', bands_direction='DIAGONAL')
    t.set(w1.inputs["Vector"], uvv)
    w1.inputs["Scale"].default_value = 180.0
    w1.inputs["Distortion"].default_value = 0.0
    chk = t.n("ShaderNodeTexChecker", ins={"Vector": uvv, "Scale": 160.0})
    h = t.add(t.mul(w1.outputs["Fac"], 0.5), t.mul(chk.outputs["Fac"], 0.5))
    nrm = t.bump(h, 0.08, 0.001)
    rnd = t.attr("part_rnd")
    smudge = _smudge(t, uvv, 1.0)
    c = t.mix(rnd, (0.020, 0.020, 0.022), (0.035, 0.035, 0.037))
    p = t.principled(base=c, rough=t.add(0.32, t.mul(smudge, 0.2)), normal=nrm, coat=0.7,
                     coat_rough=t.add(0.06, t.mul(smudge, 0.25)))
    t.output(p)
    return m


def radiator(name):
    """High-emissivity radiator: near-black, specular, finely ribbed along local U."""
    m, t = _new(name)
    uvv = t.uv()
    u, v, _ = t.sep(uvv)
    rib = t.math("SINE", t.mul(v, 2 * math.pi / 0.028))
    h = t.mul(t.math("ABSOLUTE", rib), 1.0)
    nrm = t.bump(h, 0.35, 0.0015)
    streak = t.noise(t.mapping(uvv, scale=(0.4, 12.0, 1)), 3.0, 4)
    smudge = _smudge(t, uvv, 2.0)
    rnd = t.attr("part_rnd")
    c = t.mix(rnd, (0.014, 0.015, 0.017), (0.022, 0.022, 0.024))
    r = t.add(0.16, t.add(t.mul(streak, 0.1), t.mul(smudge, 0.2)))
    p = t.principled(base=c, rough=r, normal=nrm, spec=0.65, coat=0.3, coat_rough=t.add(0.05, t.mul(smudge, 0.2)))
    t.output(p)
    return m


def heat_metal(name, base=(0.40, 0.39, 0.38), film_lo=180.0, film_hi=520.0, rough=0.32):
    """Refractory metal with heat-tint oxide (thin-film iridescence varying over the part)."""
    m, t = _new(name)
    oc = t.n("ShaderNodeTexCoord").outputs["Object"]
    uvv = t.uv()
    nz = t.noise(oc, 1.2, 3)
    grad = t.sep(oc)[2]
    f = t.maprange(t.add(t.mul(nz, 0.6), t.mul(grad, 0.25)), 0.0, 1.0, film_lo, film_hi)
    smudge = _smudge(t, uvv, 1.0)
    p = t.principled(base=base, metal=1.0, rough=t.add(rough, t.mul(smudge, 0.2)), film=f, film_ior=2.2)
    t.output(p)
    return m


def gold_anodized(name):
    return anodized(name, base=(0.84, 0.60, 0.26), rough=0.3)


def black_matte(name, base=0.012, rough=0.75):
    m, t = _new(name)
    uvv = t.uv()
    smudge = _smudge(t, uvv, 1.0)
    p = t.principled(base=(base, base, base * 1.05), rough=t.add(rough, t.mul(smudge, -0.2)), spec=0.35)
    t.output(p)
    return m


def cable(name, white=False):
    """Harness cable: spiral-wrapped bundle (tube UV v runs along the cable)."""
    m, t = _new(name)
    uvv = t.uv()
    u, v, _ = t.sep(uvv)
    sp = t.math("SINE", t.mul(t.add(v, t.mul(u, 0.7)), 2 * math.pi / 0.02))
    nrm = t.bump(sp, 0.3, 0.001)
    col = (0.62, 0.61, 0.58) if white else (0.02, 0.02, 0.022)
    p = t.principled(base=col, rough=0.5 if white else 0.45, normal=nrm, spec=0.4)
    t.output(p)
    return m


def glass_lens(name):
    """Coated optics: black glass with a purple-green AR coating sheen."""
    m, t = _new(name)
    p = t.principled(base=(0.0, 0.0, 0.0), rough=0.03, ior=1.52, coat=1.0, coat_rough=0.02, film=320.0,
                     film_ior=1.38, spec=1.0)
    t.output(p)
    return m


def stencil(name, col=(0.02, 0.02, 0.022)):
    m, t = _new(name)
    uvv = t.uv()
    scr = _scratch(t, uvv, 0.8)
    smudge = _smudge(t, uvv, 1.3)
    c = t.mix(t.mul(scr, 0.6), col, (0.6, 0.6, 0.6))
    p = t.principled(base=c, rough=t.add(0.45, t.mul(smudge, 0.2)), spec=0.45)
    t.output(p)
    return m


# ------------------------------------------------------------------------------------ emissive


def lamp(name, color, strength, prop, ctrl, lens_col=(0.8, 0.8, 0.8)):
    """Light lens: clear/tinted glossy when off, emits color*strength*CTRL when on."""
    m, t = _new(name)
    k = t.ctrl(prop, ctrl)
    p = t.principled(base=lens_col, rough=0.12, spec=0.8, coat=1.0, coat_rough=0.03, emit=color,
                     emit_str=t.mul(k, strength))
    t.output(p)
    return m


def ion_grid(name, ctrl, strength=5.5, color=(0.22, 0.46, 1.0), grid_r=0.62):
    """Molybdenum accelerator grid with a hexagonal aperture array (object space, grid in local XY).
    Apertures glow with the beam plasma when CTRL_engine > 0, brighter at the centre."""
    m, t = _new(name)
    k = t.ctrl("engine", ctrl)
    oc = t.n("ShaderNodeTexCoord").outputs["Object"]
    x, y, _ = t.sep(oc)
    pitch = 0.024
    s3 = math.sqrt(3.0)

    def lattice_dist(ox, oy):
        px = t.mul(t.add(x, ox), 1 / pitch)
        py = t.mul(t.add(y, oy), 1 / (pitch * s3))
        fx = t.sub(t.math("FRACT", t.add(px, 0.5)), 0.5)
        fy = t.mul(t.sub(t.math("FRACT", t.add(py, 0.5)), 0.5), s3)
        return t.vmath("LENGTH", t.comb(fx, fy, 0.0), out=1)

    d = t.math("MINIMUM", lattice_dist(0.0, 0.0), lattice_dist(pitch / 2, pitch * s3 / 2))
    hole = t.math("SUBTRACT", 1.0, t.smooth(d, 0.30, 0.36))
    rr = t.vmath("LENGTH", t.comb(x, y, 0.0), out=1)
    inside = t.math("SUBTRACT", 1.0, t.smooth(rr, grid_r - 0.03, grid_r - 0.01))
    hole = t.mul(hole, inside)
    prof = t.math("POWER", t.math("SUBTRACT", 1.0, t.math("POWER", t.mul(rr, 1 / grid_r), 2.0), clamp=True), 0.6)
    emit = t.mul(t.mul(hole, t.add(0.25, prof)), t.mul(k, strength))
    film = t.maprange(rr, 0.0, grid_r, 420.0, 180.0)
    base = t.mix(hole, (0.40, 0.40, 0.42), (0.004, 0.004, 0.006))
    rough = t.mixf(hole, 0.35, 0.9)
    h = t.mul(hole, -1.0)
    nrm = t.bump(h, 0.6, 0.002)
    metal = t.math("SUBTRACT", 1.0, hole)
    p = t.principled(base=base, metal=metal, rough=rough, normal=nrm, emit=color, emit_str=emit,
                     film=film, film_ior=2.0)
    t.output(p)
    return m


def plume(name, ctrl, strength=1.1, color=(0.26, 0.48, 1.0), r0=0.55, spread=0.14, length=4.5):
    """Emission-only volume for an ion-beam plume. Object local +Z runs downstream from the grid."""
    m, t = _new(name)
    k = t.ctrl("engine", ctrl)
    oc = t.n("ShaderNodeTexCoord").outputs["Object"]
    x, y, z = t.sep(oc)
    zc = t.math("MAXIMUM", z, 0.0)
    w = t.add(r0, t.mul(zc, spread))
    rr = t.vmath("LENGTH", t.comb(x, y, 0.0), out=1)
    q = t.math("DIVIDE", rr, w)
    radial = t.math("EXPONENT", t.mul(t.mul(q, q), -2.2))
    axial = t.math("EXPONENT", t.mul(zc, -1.0 / length))
    onset = t.math("SUBTRACT", 1.0, t.math("EXPONENT", t.mul(zc, -1.0 / 0.12)))
    area = t.math("DIVIDE", r0 * r0, t.mul(w, w))
    turb = t.add(0.8, t.mul(t.noise(t.mapping(oc, scale=(1.0, 1.0, 0.25)), 1.5, 3), 0.4))
    dens = t.mul(t.mul(t.mul(radial, axial), t.mul(onset, area)), turb)
    em = t.n("ShaderNodeEmission")
    em.inputs["Color"].default_value = (*color, 1.0)
    t.set(em.inputs["Strength"], t.mul(dens, t.mul(k, strength)))
    t.output(vol=em.outputs[0])
    return m


def interior_glow(name, ctrl, strength=6.0, color=(1.0, 0.55, 0.22)):
    m, t = _new(name)
    k = t.ctrl("interior", ctrl)
    oc = t.n("ShaderNodeTexCoord").outputs["Object"]
    nz = t.noise(oc, 25.0, 2)
    p = t.principled(base=(0.02, 0.02, 0.02), rough=0.05, coat=1.0, emit=color,
                     emit_str=t.mul(t.mul(k, strength), t.add(0.6, t.mul(nz, 0.8))))
    t.output(p)
    return m


def backdrop(name, color=(1.0, 0.62, 0.30), strength=4.0):
    m, t = _new(name)
    em = t.n("ShaderNodeEmission")
    em.inputs["Color"].default_value = (*color, 1.0)
    em.inputs["Strength"].default_value = strength
    t.output(em.outputs[0])
    return m


# ------------------------------------------------------------------------------------ library


def build_library(ctrl) -> dict:
    """All ship materials keyed by short name."""
    M = {}
    M["mli_gold"] = mli("SHIP_MLI_Gold", "gold")
    M["mli_silver"] = mli("SHIP_MLI_Silver", "silver")
    M["mli_black"] = mli("SHIP_MLI_Black", "black")
    M["tape_silver"] = tape("SHIP_Tape_Silver", "silver")
    M["tape_gold"] = tape("SHIP_Tape_Kapton", "gold")
    M["paint_white"] = paint("SHIP_Paint_White", 0.70, 0.46)
    M["paint_offwhite"] = paint("SHIP_Paint_OffWhite", 0.60, 0.5, tint=(1.0, 0.98, 0.93))
    M["paint_grey"] = paint("SHIP_Paint_Grey", 0.23, 0.5, tint=(1.0, 1.0, 1.02), pits=True, grime=0.6)
    M["paint_dark"] = paint("SHIP_Paint_Dark", 0.035, 0.6, pits=False, grime=0.3)
    M["dish_white"] = dish_paint("SHIP_Dish_White")
    M["alu"] = brushed_alu("SHIP_Alu_Brushed")
    M["alu_anod"] = anodized("SHIP_Alu_Anodized")
    M["alu_polish"] = brushed_alu("SHIP_Alu_Polished", base=(0.88, 0.89, 0.90), rough=0.12, aniso=0.5)
    M["alu_dark"] = anodized("SHIP_Alu_DarkAnod", base=(0.10, 0.10, 0.11), rough=0.38)
    M["composite"] = composite("SHIP_Composite")
    M["radiator"] = radiator("SHIP_Radiator")
    M["reactor"] = heat_metal("SHIP_Reactor_HeatTint")
    M["nozzle"] = heat_metal("SHIP_Nozzle_Niobium", base=(0.30, 0.30, 0.32), film_lo=250, film_hi=450, rough=0.28)
    M["gold_anod"] = gold_anodized("SHIP_Handrail_Gold")
    M["black"] = black_matte("SHIP_Black_Matte")
    M["cable_black"] = cable("SHIP_Cable_Black")
    M["cable_white"] = cable("SHIP_Cable_White", white=True)
    M["lens"] = glass_lens("SHIP_Glass_Lens")
    M["stencil_black"] = stencil("SHIP_Stencil_Black")
    M["stencil_red"] = stencil("SHIP_Stencil_Red", (0.36, 0.025, 0.02))
    M["stencil_yellow"] = stencil("SHIP_Stencil_Yellow", (0.62, 0.42, 0.04))
    M["stencil_white"] = stencil("SHIP_Stencil_White", (0.62, 0.62, 0.60))
    M["beacon"] = lamp("SHIP_Lamp_Beacon", (0.82, 0.88, 1.0), 900.0, "beacon", ctrl, (0.85, 0.85, 0.88))
    M["nav_red"] = lamp("SHIP_Lamp_NavRed", (1.0, 0.02, 0.01), 60.0, "nav", ctrl, (0.35, 0.02, 0.02))
    M["nav_green"] = lamp("SHIP_Lamp_NavGreen", (0.02, 1.0, 0.22), 45.0, "nav", ctrl, (0.02, 0.3, 0.06))
    M["running"] = lamp("SHIP_Lamp_Running", (1.0, 0.93, 0.82), 40.0, "running", ctrl, (0.8, 0.8, 0.78))
    M["interior"] = interior_glow("SHIP_Interior_Glow", ctrl)
    M["ion_grid"] = ion_grid("SHIP_Ion_Grid", ctrl)
    M["plume"] = plume("SHIP_Ion_Plume", ctrl)
    return M

"""Blender batch renderer for the ship layers (runs inside Blender).

  blender -b -P production/blender/render_frame.py -- job.json

job.json:
  {"width": W, "height": H, "samples": N, "ship_blend": optional cache path,
   "frames": [{"out": "x.exr",
               "camera": [c_prev, c, c_next],     # each {pos, fwd, up, hfov, focus, fstop}; shutter blur
               "ship":   [m_prev, m, m_next],     # 4x4 world matrices of the ship root (metres)
               "controls": {beacon, nav, running, engine, interior, dish_az_deg, dish_el_deg},
               "world": {"env": exr|null, "strength": s, "color": [r,g,b]},
               "keys": [{"dir": [x,y,z] (towards the light), "color": [..], "strength": s, "angle": deg}],
               "props": [{"kind": "rocks", ...}] }]}

Output: multilayer EXR per frame with Combined (RGBA, premultiplied), Z, and light groups
env / key / lamps (the ship's own lights), so the compositor can grade them independently.
"""
import json
import math
import os
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "ship"))
sys.path.insert(0, str(HERE))


def args():
    a = sys.argv
    return a[a.index("--") + 1:] if "--" in a else []


# ------------------------------------------------------------------ ship
def build_proxy():
    """Placeholder silhouette used until the hero ship exists (keeps the pipeline running)."""
    col = bpy.data.collections.new("SHIP")
    bpy.context.scene.collection.children.link(col)
    root = bpy.data.objects.new("SHIP_ROOT", None)
    col.objects.link(root)
    ctrl = bpy.data.objects.new("SHIP_CTRL", None)
    col.objects.link(ctrl)
    ctrl.parent = root
    for k in ("beacon", "nav", "running", "engine", "interior"):
        ctrl[k] = 0.0
    mat = bpy.data.materials.new("proxy_paint")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (0.55, 0.55, 0.56, 1)
    bsdf.inputs["Roughness"].default_value = 0.45
    bsdf.inputs["Metallic"].default_value = 0.3

    def add(obj):
        col.objects.link(obj)
        obj.parent = root
        obj.data.materials.append(mat)

    bpy.ops.mesh.primitive_cylinder_add(radius=2.2, depth=12, location=(0, 4, 0), rotation=(math.pi / 2, 0, 0))
    o = bpy.context.active_object; bpy.context.scene.collection.objects.unlink(o); add(o)
    bpy.ops.mesh.primitive_cylinder_add(radius=0.5, depth=30, location=(0, -16, 0), rotation=(math.pi / 2, 0, 0))
    o = bpy.context.active_object; bpy.context.scene.collection.objects.unlink(o); add(o)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=4.0, location=(0, 12.5, 0), scale=(1, 0.25, 1))
    o = bpy.context.active_object; bpy.context.scene.collection.objects.unlink(o); add(o)
    for sx in (-1, 1):
        bpy.ops.mesh.primitive_cube_add(size=1, location=(sx * 7, -14, 0), scale=(10, 5, 0.1))
        o = bpy.context.active_object; bpy.context.scene.collection.objects.unlink(o); add(o)
    # beacon: emissive sphere + point light, driven by SHIP_CTRL["beacon"]
    bmat = bpy.data.materials.new("proxy_beacon")
    bmat.use_nodes = True
    nt = bmat.node_tree
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (0.85, 0.92, 1.0, 1)
    out = nt.nodes.get("Material Output")
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    drv = em.inputs["Strength"].driver_add("default_value").driver
    v = drv.variables.new(); v.name = "b"; v.targets[0].id = ctrl; v.targets[0].data_path = '["beacon"]'
    drv.expression = "b * 400"
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.18, location=(0, 6, 2.4))
    o = bpy.context.active_object; bpy.context.scene.collection.objects.unlink(o); col.objects.link(o)
    o.parent = root; o.data.materials.append(bmat)
    return root


def get_ship(ship_blend: str | None):
    if ship_blend and os.path.exists(ship_blend):
        with bpy.data.libraries.load(ship_blend, link=False) as (src, dst):
            dst.collections = [c for c in src.collections if c == "SHIP"]
        for c in dst.collections:
            bpy.context.scene.collection.children.link(c)
        return bpy.data.objects.get("SHIP_ROOT") or next(o for o in bpy.data.objects if o.parent is None and "SHIP" in o.name)
    try:
        import ship_api  # the hero ship (production/blender/ship/ship_api.py)
        root = ship_api.build_ship("SHIP")
        if ship_blend:
            bpy.ops.wm.save_as_mainfile(filepath=ship_blend, copy=True)
        return root
    except Exception as e:  # missing or broken hero ship: keep the pipeline alive with the proxy
        print(f"render_frame: ship_api unavailable ({type(e).__name__}: {e}); using proxy ship", flush=True)
        for c in [c for c in bpy.data.collections if c.name.startswith("SHIP")]:
            bpy.data.collections.remove(c)
        return build_proxy()


def set_controls(root, controls: dict):
    try:
        import ship_api
        ship_api.set_controls(root, **controls)
        return
    except Exception:
        pass
    ctrl = bpy.data.objects.get("SHIP_CTRL")
    if ctrl:
        for k, v in controls.items():
            if k in ctrl.keys():
                ctrl[k] = float(v)


# ------------------------------------------------------------------ scene
def setup_scene(W, H, samples):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples
    sc.cycles.use_adaptive_sampling = True
    sc.cycles.adaptive_threshold = 0.015
    sc.cycles.use_denoising = True
    sc.cycles.denoiser = "OPENIMAGEDENOISE"
    sc.cycles.max_bounces = 6
    sc.cycles.glossy_bounces = 4
    sc.cycles.transparent_max_bounces = 8
    sc.cycles.caustics_reflective = False
    sc.cycles.caustics_refractive = False
    sc.render.resolution_x, sc.render.resolution_y = W, H
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = True
    sc.render.use_motion_blur = True
    sc.render.motion_blur_shutter = 0.5
    sc.view_settings.view_transform = "Standard"
    sc.view_settings.look = "None"
    sc.render.image_settings.file_format = "OPEN_EXR_MULTILAYER"
    sc.render.image_settings.color_depth = "16"
    sc.render.image_settings.exr_codec = "ZIP"
    vl = sc.view_layers[0]
    vl.use_pass_z = True
    for name in ("env", "key", "lamps"):
        if name not in [lg.name for lg in vl.lightgroups]:
            vl.lightgroups.add(name=name)
    sc.render.threads_mode = "AUTO"
    sc.frame_start, sc.frame_end = 1, 3
    return sc


def world_setup(w: dict):
    world = bpy.data.worlds.get("TLS_WORLD") or bpy.data.worlds.new("TLS_WORLD")
    bpy.context.scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld")
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs["Strength"].default_value = float(w.get("strength", 1.0))
    env = w.get("env")
    if env and os.path.exists(env):
        tex = nt.nodes.new("ShaderNodeTexEnvironment")
        tex.image = bpy.data.images.load(env, check_existing=False)
        tex.image.colorspace_settings.name = "Linear Rec.709" if "Linear Rec.709" in [
            c.name for c in bpy.types.ColorManagedInputColorspaceSettings.bl_rna.properties["name"].enum_items] else "Non-Color"
        tex.interpolation = "Linear"
        nt.links.new(tex.outputs["Color"], bg.inputs["Color"])
    else:
        bg.inputs["Color"].default_value = (*w.get("color", (0.0, 0.0, 0.0)), 1)
    nt.links.new(bg.outputs[0], out.inputs["Surface"])
    world.lightgroup = "env"
    world.cycles.sampling_method = "MANUAL"
    world.cycles.sample_map_resolution = 1024


def keys_setup(keys: list):
    for o in [o for o in bpy.data.objects if o.name.startswith("TLS_KEY")]:
        bpy.data.objects.remove(o, do_unlink=True)
    for i, k in enumerate(keys):
        ld = bpy.data.lights.new(f"TLS_KEY{i}", "SUN")
        ld.energy = float(k.get("strength", 3.0))
        ld.color = k.get("color", (1, 1, 1))
        ld.angle = math.radians(float(k.get("angle", 0.5)))
        ob = bpy.data.objects.new(f"TLS_KEY{i}", ld)
        bpy.context.scene.collection.objects.link(ob)
        d = Vector(k["dir"]).normalized()
        # sun shines along its local -Z: point -Z opposite to the direction towards the light
        ob.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
        ob.lightgroup = "key"


def cam_matrix(c: dict) -> Matrix:
    f = Vector(c["fwd"]).normalized()
    up = Vector(c.get("up", (0, 0, 1)))
    r = f.cross(up).normalized()
    u = r.cross(f)
    m = Matrix((r, u, -f)).transposed().to_4x4()
    m.translation = Vector(c["pos"])
    return m


def camera_setup(cams: list):
    cam = bpy.data.objects.get("TLS_CAM")
    if cam is None:
        cd = bpy.data.cameras.new("TLS_CAM")
        cam = bpy.data.objects.new("TLS_CAM", cd)
        bpy.context.scene.collection.objects.link(cam)
    bpy.context.scene.camera = cam
    cd = cam.data
    cd.sensor_fit = "HORIZONTAL"
    cd.sensor_width = 36.0
    cd.clip_start = 0.02
    cd.clip_end = 1e6
    cam.animation_data_clear()
    for fr, c in zip((1, 2, 3), cams):
        cam.matrix_world = cam_matrix(c)
        cam.keyframe_insert("location", frame=fr)
        cam.keyframe_insert("rotation_euler", frame=fr)
    c = cams[1]
    cd.lens = 36.0 / (2 * math.tan(math.radians(c["hfov"]) / 2))
    focus = float(c.get("focus", 1e9))
    cd.dof.use_dof = focus < 1e5
    if cd.dof.use_dof:
        cd.dof.focus_distance = focus
        cd.dof.aperture_fstop = float(c.get("fstop", 8.0))
        cd.dof.aperture_ratio = 0.5          # anamorphic: bokeh taller than wide
        cd.dof.aperture_blades = 0


def ship_pose(root, mats: list):
    root.animation_data_clear()
    for fr, m in zip((1, 2, 3), mats):
        root.matrix_world = Matrix(m)
        root.keyframe_insert("location", frame=fr)
        root.keyframe_insert("rotation_euler", frame=fr)


# ------------------------------------------------------------------ props: debris stream + dust
def _rock_material():
    m = bpy.data.materials.get("TLS_rock")
    if m:
        return m
    m = bpy.data.materials.new("TLS_rock")
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    bsdf.inputs["Roughness"].default_value = 0.86
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 6.0
    noise.inputs["Detail"].default_value = 8.0
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (0.035, 0.032, 0.03, 1)
    ramp.color_ramp.elements[1].color = (0.16, 0.14, 0.12, 1)
    nt.links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.6
    nt.links.new(noise.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return m


def _rock_meshes(n=6):
    out = []
    for i in range(n):
        name = f"TLS_rockmesh{i}"
        me = bpy.data.meshes.get(name)
        if me is None:
            bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=4, radius=1.0)
            o = bpy.context.active_object
            o.scale = (1.0, 0.6 + 0.35 * ((i * 37) % 7) / 7, 0.45 + 0.4 * ((i * 53) % 5) / 5)
            tex = bpy.data.textures.new(f"TLS_rocktex{i}", "VORONOI")
            tex.noise_scale = 0.55 + 0.1 * i
            d = o.modifiers.new("disp", "DISPLACE"); d.texture = tex; d.strength = 0.35
            tex2 = bpy.data.textures.new(f"TLS_rocktex2_{i}", "CLOUDS")
            tex2.noise_scale = 0.25
            d2 = o.modifiers.new("disp2", "DISPLACE"); d2.texture = tex2; d2.strength = 0.12
            bpy.ops.object.modifier_apply(modifier="disp")
            bpy.ops.object.modifier_apply(modifier="disp2")
            bpy.ops.object.transform_apply(scale=True)
            bpy.ops.object.shade_smooth()
            me = o.data
            me.name = name
            me.materials.append(_rock_material())
            bpy.data.objects.remove(o, do_unlink=True)
        out.append(me)
    return out


def debris(prop: dict, times: list):
    import random
    seed = int(prop.get("seed", 1))
    n = int(prop.get("count", 90))
    col = bpy.data.collections.get("TLS_PROPS")
    if col is None:
        col = bpy.data.collections.new("TLS_PROPS")
        bpy.context.scene.collection.children.link(col)
        meshes = _rock_meshes()
        rng = random.Random(seed)
        nb = int(prop.get("boulders", 12))
        for i in range(n + nb):
            o = bpy.data.objects.new(f"TLS_rock{i}", meshes[i % len(meshes)])
            if i < n:
                size = math.exp(rng.uniform(math.log(0.06), math.log(3.0)))
                pos = (rng.uniform(*prop.get("x", (-44.0, -12.0))), rng.uniform(-120.0, 120.0),
                       rng.uniform(*prop.get("z", (-14.0, 12.0))))
            else:  # big boulders beyond the ship, for depth
                size = rng.uniform(4.0, 11.0)
                pos = (rng.uniform(25.0, 90.0), rng.uniform(-120.0, 120.0), rng.uniform(-30.0, 30.0))
            o["size"] = size
            o["p0"] = pos
            o["axis"] = (rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1))
            o["spin"] = rng.uniform(-1.2, 1.2) / max(size, 0.3)
            col.objects.link(o)
        if prop.get("dust", True):
            me = bpy.data.meshes.new("TLS_dust")
            vs = [(x, y, z) for x in (-0.5, 0.5) for y in (-0.5, 0.5) for z in (-0.5, 0.5)]
            fs = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
            me.from_pydata(vs, [], fs)
            v = bpy.data.objects.new("TLS_dust", me)
            v.location = (-25.0, 0.0, 0.0)
            v.scale = (110.0, 320.0, 70.0)
            col.objects.link(v)
            vm = bpy.data.materials.new("TLS_dust")
            vm.use_nodes = True
            nt = vm.node_tree
            nt.nodes.remove(nt.nodes.get("Principled BSDF"))
            pv = nt.nodes.new("ShaderNodeVolumePrincipled")
            pv.inputs["Color"].default_value = (0.8, 0.74, 0.66, 1)
            pv.inputs["Anisotropy"].default_value = 0.72
            nz = nt.nodes.new("ShaderNodeTexNoise")
            nz.inputs["Scale"].default_value = float(prop.get("dust_scale", 0.02))
            nz.inputs["Detail"].default_value = 4.0
            mr = nt.nodes.new("ShaderNodeMapRange")
            mr.inputs["From Min"].default_value = 0.46
            mr.inputs["From Max"].default_value = 0.78
            mr.inputs["To Min"].default_value = 0.0
            mr.inputs["To Max"].default_value = float(prop.get("dust_density", 0.004))
            nt.links.new(nz.outputs["Fac"], mr.inputs["Value"])
            nt.links.new(mr.outputs["Result"], pv.inputs["Density"])
            nt.links.new(pv.outputs[0], nt.nodes.get("Material Output").inputs["Volume"])
            v.data.materials.append(vm)
    vel = prop.get("vel", (0.0, -38.0, 2.5))
    for o in [o for o in col.objects if o.name.startswith("TLS_rock")]:
        o.animation_data_clear()
        for fr, tt in zip((1, 2, 3), times):
            p0 = o["p0"]
            y = (p0[1] + vel[1] * tt + 120.0) % 240.0 - 120.0
            o.location = (p0[0] + vel[0] * tt, y, p0[2] + vel[2] * (tt % 20.0))
            o.rotation_mode = "AXIS_ANGLE"
            ax = Vector(o["axis"]).normalized()
            o.rotation_axis_angle = (o["spin"] * tt, ax.x, ax.y, ax.z)
            s_ = o["size"]
            o.scale = (s_, s_, s_)
            o.keyframe_insert("location", frame=fr)
            o.keyframe_insert("rotation_axis_angle", frame=fr)


def assign_lightgroups(root):
    for o in bpy.data.objects:
        p, inside = o, False
        while p is not None:
            if p == root:
                inside = True
                break
            p = p.parent
        if inside and o.type in ("MESH", "LIGHT", "CURVE", "FONT"):
            o.lightgroup = "lamps"


def main():
    job = json.loads(Path(args()[0]).read_text())
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    sc = setup_scene(job["width"], job["height"], job.get("samples", 64))
    root = get_ship(job.get("ship_blend"))
    assign_lightgroups(root)
    layout = os.environ.get("TLS_LAYOUT") == "1"
    for fj in job["frames"]:
        world_setup({"color": [0.25, 0.25, 0.25]} if layout else fj.get("world", {}))
        keys_setup(fj.get("keys", []))
        camera_setup(fj["camera"])
        ship_pose(root, fj["ship"])
        set_controls(root, fj.get("controls", {}))
        root.hide_render = bool(fj.get("hide_ship", False))
        for pr in fj.get("props", []):
            if pr.get("kind") == "debris":
                debris(pr, fj.get("times", [0, 0, 0]))
        sc.frame_set(2)
        sc.render.filepath = fj["out"]
        bpy.ops.render.render(write_still=True)
        print(f"render_frame: wrote {fj['out']}", flush=True)


main()

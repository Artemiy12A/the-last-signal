"""Public API for the LSV-7 hero ship (Blender 4.5 / Cycles).

Usage from any Blender Python script (headless: blender -b -P your_script.py -- args):

    import sys; sys.path.insert(0, "<repo>/production/blender/ship")
    import ship_api as S
    S.reset_scene()
    root = S.build_ship()
    S.set_controls(root, beacon=1, engine=1, dish_az_deg=30)
    S.setup_world_from_equirect("probe.exr", strength=1.0, rotation_z_deg=0)
    S.add_key_light((1, 0.3, 0.2), (1.0, 0.8, 0.6), 4.0, 0.5)
    S.set_camera((40, 40, 10), (0, 10, 0), hfov_deg=35, fstop=5.6)
    S.setup_render(1920, 804, 128)
    S.render("out/frame_####.exr")

Frame: ship local +Y = bow, +Z = dorsal, +X = starboard, metres, origin (SHIP_ROOT) = estimated centre
of mass. Animate the ship by keying SHIP_ROOT's transform; animate lights/dish by keying the custom
properties on SHIP_CTRL (set_controls(..., frame=f) does that for you).
"""
from __future__ import annotations

import math
import os
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Matrix, Vector

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import ship_build  # noqa: E402

CONTROL_KEYS = tuple(ship_build.CTRL_DEFAULTS)
LIGHTGROUPS = ("ship_lights", "env", "key")


# ------------------------------------------------------------------------------------ scene


def reset_scene():
    """Empty the current scene (factory-startup cube/camera/light) and orphan data."""
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.lights, bpy.data.cameras, bpy.data.curves,
                 bpy.data.images, bpy.data.worlds, bpy.data.node_groups):
        for block in list(coll):
            if block.users == 0:
                coll.remove(block)
    for c in list(bpy.data.collections):
        bpy.data.collections.remove(c)


def build_ship(collection_name="SHIP", seed=7):
    """Build the whole ship in the current scene. Deterministic for a given seed. Returns SHIP_ROOT."""
    root = ship_build.build(collection_name, seed)
    _ensure_lightgroups()
    bpy.context.view_layer.update()
    return root


def ship_ctrl(root):
    return bpy.data.objects[root["tls_ctrl"]]


def set_controls(root, beacon=0.0, nav=1.0, running=1.0, engine=0.0, interior=0.0, dish_az_deg=0.0,
                 dish_el_deg=0.0, frame=None):
    """Set the ship's light levels (0 = off, 1 = nominal; >1 allowed for flashes) and HGA pointing.
    dish_az_deg: rotation about the gimbal's local Z (+ turns the dish toward port).
    dish_el_deg: rotation about local X (+ tilts the dish up/dorsal). Safe range |az| <= 90, -60..60 el.
    If `frame` is given, the values are also keyframed at that frame (constant interpolation for
    lights so strobes stay crisp, Bezier for the dish)."""
    ctrl = ship_ctrl(root)
    vals = dict(beacon=beacon, nav=nav, running=running, engine=engine, interior=interior,
                dish_az_deg=dish_az_deg, dish_el_deg=dish_el_deg)
    for k, v in vals.items():
        ctrl[k] = float(v)
        if frame is not None:
            ctrl.keyframe_insert(f'["{k}"]', frame=frame)
    if frame is not None and ctrl.animation_data and ctrl.animation_data.action:
        for fc in _fcurves(ctrl.animation_data.action):
            if not fc.data_path.startswith('["dish'):
                for kp in fc.keyframe_points:
                    kp.interpolation = 'CONSTANT'
    ctrl.update_tag()
    bpy.context.view_layer.update()


def _fcurves(action):
    if hasattr(action, "fcurves") and len(getattr(action, "fcurves", [])):
        return list(action.fcurves)
    out = []
    for layer in getattr(action, "layers", []):
        for strip in layer.strips:
            for bag in getattr(strip, "channelbags", []):
                out.extend(bag.fcurves)
    return out


# ------------------------------------------------------------------------------------ lighting


def _ensure_lightgroups():
    vl = bpy.context.view_layer
    have = {lg.name for lg in vl.lightgroups}
    for n in LIGHTGROUPS:
        if n not in have:
            vl.lightgroups.add(name=n)


def setup_world_from_equirect(exr_path, strength=1.0, rotation_z_deg=0.0, visible_to_camera=False):
    """World lighting from an HDR equirect probe (Blender/Cycles convention, Z up: image centre looks
    along world -Y... i.e. standard Cycles Environment Texture mapping). rotation_z_deg spins the probe
    about world Z. The world is put in light group 'env'. With visible_to_camera=False the background
    renders transparent/black to camera rays (the tracer supplies the plate) but still lights the ship."""
    scene = bpy.context.scene
    w = scene.world or bpy.data.worlds.new("TLS_World")
    scene.world = w
    w.use_nodes = True
    nt = w.node_tree
    nt.nodes.clear()
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Rotation"].default_value = (0, 0, math.radians(rotation_z_deg))
    env = nt.nodes.new("ShaderNodeTexEnvironment")
    env.projection = 'EQUIRECTANGULAR'
    env.interpolation = 'Linear'
    env.image = bpy.data.images.load(str(exr_path), check_existing=True)
    env.image.colorspace_settings.name = 'Linear Rec.709' if 'Linear Rec.709' in _colorspaces() else 'Linear'
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs["Strength"].default_value = strength
    out = nt.nodes.new("ShaderNodeOutputWorld")
    nt.links.new(tc.outputs["Generated"], mp.inputs["Vector"])
    nt.links.new(mp.outputs["Vector"], env.inputs["Vector"])
    nt.links.new(env.outputs["Color"], bg.inputs["Color"])
    if visible_to_camera:
        nt.links.new(bg.outputs[0], out.inputs["Surface"])
    else:
        lp = nt.nodes.new("ShaderNodeLightPath")
        blk = nt.nodes.new("ShaderNodeBackground")
        blk.inputs["Color"].default_value = (0, 0, 0, 1)
        mix = nt.nodes.new("ShaderNodeMixShader")
        nt.links.new(lp.outputs["Is Camera Ray"], mix.inputs["Fac"])
        nt.links.new(bg.outputs[0], mix.inputs[1])
        nt.links.new(blk.outputs[0], mix.inputs[2])
        nt.links.new(mix.outputs[0], out.inputs["Surface"])
    w.lightgroup = "env"
    w.cycles.sampling_method = 'MANUAL'
    w.cycles.sample_map_resolution = 1024
    _ensure_lightgroups()
    return w


def _colorspaces():
    try:
        return [i.identifier for i in bpy.types.ColorManagedInputColorspaceSettings.bl_rna.properties["name"].enum_items]
    except Exception:  # noqa: BLE001
        return []


def setup_world_color(color=(0, 0, 0), strength=1.0):
    """Plain world (e.g. black space) in light group 'env'."""
    scene = bpy.context.scene
    w = scene.world or bpy.data.worlds.new("TLS_World")
    scene.world = w
    w.use_nodes = True
    nt = w.node_tree
    nt.nodes.clear()
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs["Color"].default_value = (*color, 1.0)
    bg.inputs["Strength"].default_value = strength
    out = nt.nodes.new("ShaderNodeOutputWorld")
    nt.links.new(bg.outputs[0], out.inputs["Surface"])
    w.lightgroup = "env"
    _ensure_lightgroups()
    return w


def add_key_light(direction_xyz, color=(1.0, 0.85, 0.65), strength=4.0, angle_deg=0.5, name="TLS_Key",
                  lightgroup="key"):
    """Sun lamp. direction_xyz points FROM the scene TOWARD the light source (world axes), e.g. toward
    the accretion disk. strength = irradiance in W/m2 (Blender sun units); angle_deg = angular
    diameter of the source (0.5 = hard, 5-20 = soft disk-like)."""
    d = Vector(direction_xyz).normalized()
    ld = bpy.data.lights.new(name, 'SUN')
    ld.color = color
    ld.energy = strength
    ld.angle = math.radians(angle_deg)
    ob = bpy.data.objects.new(name, ld)
    bpy.context.scene.collection.objects.link(ob)
    # sun shines along its local -Z, so local +Z = toward the light
    ob.rotation_euler = d.to_track_quat('Z', 'Y').to_euler()
    ob.lightgroup = lightgroup
    _ensure_lightgroups()
    return ob


# ------------------------------------------------------------------------------------ camera


def set_camera(pos, look_at, up=(0, 0, 1), hfov_deg=40.0, fstop=None, focus_dist=None, aperture_ratio=2.0,
               blades=0, sensor_width=36.0, clip_start=0.05, clip_end=1.0e6, name="TLS_Camera", shift=(0, 0)):
    """Place (or update) the scene camera from position / look-at / up, horizontal FOV with horizontal
    sensor fit. fstop enables depth of field (focus_dist defaults to the look-at distance);
    aperture_ratio 2.0 gives vertically stretched, anamorphic-style oval bokeh."""
    scene = bpy.context.scene
    ob = bpy.data.objects.get(name)
    if ob is None or ob.type != 'CAMERA':
        cd = bpy.data.cameras.new(name)
        ob = bpy.data.objects.new(name, cd)
        scene.collection.objects.link(ob)
    cam = ob.data
    cam.sensor_fit = 'HORIZONTAL'
    cam.sensor_width = sensor_width
    cam.angle = math.radians(hfov_deg)
    cam.clip_start, cam.clip_end = clip_start, clip_end
    cam.shift_x, cam.shift_y = shift
    p, t, u = Vector(pos), Vector(look_at), Vector(up)
    f = (t - p).normalized()
    r = f.cross(u).normalized()
    uu = r.cross(f)
    m = Matrix((r, uu, -f)).transposed()
    ob.matrix_world = Matrix.Translation(p) @ m.to_4x4()
    cam.dof.use_dof = fstop is not None
    if fstop is not None:
        cam.dof.aperture_fstop = fstop
        cam.dof.focus_distance = focus_dist if focus_dist is not None else (t - p).length
        cam.dof.aperture_ratio = aperture_ratio
        cam.dof.aperture_blades = blades
    scene.camera = ob
    return ob


# ------------------------------------------------------------------------------------ render


def setup_render(width, height, samples=128, denoise=True, motion_blur=True, transparent=True,
                 output_path=None, shutter=0.5, threads=0):
    """Cycles CPU, view transform Standard (no Filmic/AgX baked in), linear multilayer EXR with alpha
    and passes: Combined, Depth (Z), Emission, plus light-group passes ship_lights / env / key so the
    compositor can grade the ship's own lights separately."""
    scene = bpy.context.scene
    r = scene.render
    scene.render.engine = 'CYCLES'
    cy = scene.cycles
    cy.device = 'CPU'
    cy.samples = samples
    cy.use_adaptive_sampling = True
    cy.adaptive_threshold = 0.01
    cy.use_denoising = denoise
    if denoise:
        cy.denoiser = 'OPENIMAGEDENOISE'
        cy.denoising_input_passes = 'RGB_ALBEDO_NORMAL'
        cy.denoising_prefilter = 'ACCURATE'
    cy.max_bounces = 8
    cy.diffuse_bounces = 3
    cy.glossy_bounces = 4
    cy.transmission_bounces = 4
    cy.volume_bounces = 0
    cy.transparent_max_bounces = 8
    cy.sample_clamp_indirect = 8.0
    cy.blur_glossy = 0.5
    cy.caustics_reflective = False
    cy.caustics_refractive = False
    cy.volume_step_rate = 1.0
    cy.volume_max_steps = 256
    r.threads_mode = 'FIXED' if threads else 'AUTO'
    if threads:
        r.threads = threads
    r.resolution_x, r.resolution_y, r.resolution_percentage = width, height, 100
    r.pixel_aspect_x = r.pixel_aspect_y = 1.0
    r.film_transparent = transparent
    r.use_motion_blur = motion_blur
    r.motion_blur_shutter = shutter
    r.use_persistent_data = True
    vs = scene.view_settings
    scene.display_settings.display_device = 'sRGB'
    vs.view_transform = 'Standard'
    vs.look = 'None'
    vs.exposure = 0.0
    vs.gamma = 1.0
    im = r.image_settings
    im.file_format = 'OPEN_EXR_MULTILAYER'
    im.color_depth = '32'
    im.exr_codec = 'ZIP'
    im.color_mode = 'RGBA'
    vl = bpy.context.view_layer
    vl.use_pass_combined = True
    vl.use_pass_z = True
    vl.use_pass_emit = True
    _ensure_lightgroups()
    if output_path:
        r.filepath = str(output_path)
    return scene


def setup_review_output(path_jpg, quality=88, exposure=0.0, look='AgX - Medium High Contrast'):
    """Display-referred JPG for review stills (AgX, like production/comp/tonemap.py)."""
    scene = bpy.context.scene
    im = scene.render.image_settings
    im.file_format = 'JPEG'
    im.color_mode = 'RGB'
    im.quality = quality
    vs = scene.view_settings
    vs.view_transform = 'AgX'
    try:
        vs.look = look
    except TypeError:
        vs.look = 'None'
    vs.exposure = exposure
    scene.render.film_transparent = False
    scene.render.filepath = str(path_jpg)


def render(path=None, animation=False):
    """Render the current frame (or the frame range if animation=True). '#' in a still's path is
    replaced by the zero-padded current frame number."""
    scene = bpy.context.scene
    if path:
        scene.render.filepath = str(path)
    if not animation and "#" in scene.render.filepath:
        base = scene.render.filepath
        scene.render.filepath = scene.render.frame_path(frame=scene.frame_current)
        bpy.ops.render.render(write_still=True)
        scene.render.filepath = base
        return
    bpy.ops.render.render(write_still=not animation, animation=animation)


# ------------------------------------------------------------------------------------ utilities


def polycount(root=None):
    """(objects, triangles) of the evaluated ship meshes."""
    dg = bpy.context.evaluated_depsgraph_get()
    tris = 0
    n = 0
    for ob in bpy.data.objects:
        if ob.type != 'MESH' or not ob.name.startswith("SHIP_"):
            continue
        ev = ob.evaluated_get(dg)
        me = ev.to_mesh()
        me.calc_loop_triangles()
        tris += len(me.loop_triangles)
        n += 1
        ev.to_mesh_clear()
    return n, tris


def write_equirect_exr(path, rgb):
    """Save an (H, W, 3) float array as an equirect OpenEXR (for test probes)."""
    h, w, _ = rgb.shape
    img = bpy.data.images.new(Path(path).stem, w, h, alpha=True, float_buffer=True)
    px = np.ones((h, w, 4), np.float32)
    px[..., :3] = rgb[::-1]            # Blender images are bottom-up
    img.pixels.foreach_set(px.ravel())
    img.filepath_raw = str(path)
    img.file_format = 'OPEN_EXR'
    img.save()
    bpy.data.images.remove(img)
    return path


def make_test_probe(path, w=1024, h=512, disk_az_deg=60.0, disk_el_deg=8.0, disk_intensity=40.0,
                    fill=(0.004, 0.006, 0.012)):
    """Synthetic disk-like env probe in the Cycles equirect convention (u -> azimuth, v -> elevation,
    world Z up): a thin blazing warm arc centred at azimuth `disk_az_deg` (measured from +X toward +Y),
    a soft warm glow around it, and a faint cool sky elsewhere. Used by lookdev only."""
    u = (np.arange(w) + 0.5) / w
    v = (np.arange(h) + 0.5) / h
    az = (0.5 - u) * 2 * math.pi                    # Cycles: u=0.5 looks along +X? (see _dir below)
    el = (0.5 - v) * math.pi
    AZ, EL = np.meshgrid(az, el)
    d = np.stack([np.cos(EL) * np.cos(AZ), np.cos(EL) * np.sin(AZ), np.sin(EL)], -1)
    a0, e0 = math.radians(disk_az_deg), math.radians(disk_el_deg)
    c = np.array([math.cos(e0) * math.cos(a0), math.cos(e0) * math.sin(a0), math.sin(e0)])
    # disk plane tilted: band = small angle to a great circle through c, tilted 12 deg
    ax = np.cross(c, [0, 0, 1.0])
    ax /= np.linalg.norm(ax)
    tilt = math.radians(12)
    nrm = np.cross(ax, c) * math.cos(tilt) + np.cross(np.cross(ax, c), c) * 0 + ax * math.sin(tilt)
    nrm /= np.linalg.norm(nrm)
    off = np.arcsin(np.clip(d @ nrm, -1, 1))
    along = np.arccos(np.clip(d @ c, -1, 1))
    span = np.exp(-(along / math.radians(55)) ** 4)
    band = np.exp(-(off / math.radians(1.2)) ** 2) * span
    glow = np.exp(-(off / math.radians(10)) ** 2) * np.exp(-(along / math.radians(70)) ** 2)
    warm = np.array([1.0, 0.72, 0.42])
    white = np.array([1.0, 0.93, 0.85])
    sky = np.array(fill)[None, None, :] * (0.6 + 0.4 * (d[..., 2:3] + 1) / 2)
    rgb = sky + band[..., None] * white * disk_intensity + glow[..., None] * warm * disk_intensity * 0.03
    return write_equirect_exr(path, rgb.astype(np.float32))

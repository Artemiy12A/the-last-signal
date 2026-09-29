# LSV-7 — hero ship (procedural, Blender 4.5 / Cycles)

A ~57 m nuclear-electric deep-space vessel, built entirely from Python (no hand-edited binaries):
8 m high-gain dish on a two-axis gimbal, gold/silver/black-kapton MLI bus, white service ring with
RCS quads and xenon strobes, 27 m triangular lattice spine, xenon spheres + COPV tanks, four dark
ribbed radiator wings (28° dihedral), shadow shield, finned reactor, black-kapton PPU and three
gridded ion thrusters with emission-volume plumes.

```
python3 production/blender/ship/fetch_textures.py          # once: CC0 ambientCG maps -> production/cache/textures
blender -b --factory-startup -P production/blender/ship/lookdev.py -- [--shots 1,2,3,4,5] [--samples 64]
```

Missing textures fall back to procedural noise (with a warning) so the ship always builds.

## API (`ship_api.py`)

```python
import sys; sys.path.insert(0, "<repo>/production/blender/ship")
import ship_api as S
S.reset_scene()                                   # optional: clear factory-startup objects
root = S.build_ship(collection_name="SHIP", seed=7)   # -> SHIP_ROOT empty; deterministic
S.set_controls(root, beacon=0, nav=1, running=1, engine=0, interior=0,
               dish_az_deg=0, dish_el_deg=0, frame=None)   # frame=N also keyframes them
S.setup_world_from_equirect(exr_path, strength=1.0, rotation_z_deg=0, visible_to_camera=False)
S.setup_world_color((0, 0, 0))                    # plain black space instead of a probe
S.add_key_light(direction_xyz, color, strength, angle_deg)  # sun; direction points TOWARD the source
S.set_camera(pos, look_at, up=(0,0,1), hfov_deg=40, fstop=None, focus_dist=None,
             aperture_ratio=2.0, blades=0, clip_start=0.05, clip_end=1e6, shift=(0,0))
S.setup_render(width, height, samples=128, denoise=True, motion_blur=True, transparent=True,
               output_path=None, shutter=0.5)
S.render("out/S03_####.exr")                      # still (# -> frame) or animation=True
S.polycount()                                     # (mesh objects, triangles)
S.make_test_probe(path, ...)                      # synthetic disk-like equirect EXR (lookdev only)
S.setup_review_output(jpg, quality=88, exposure=0) # AgX JPG instead of EXR (review stills)
```

- **Frame:** ship local +Y = bow, +Z = dorsal, +X = starboard, metres. `SHIP_ROOT` sits at the
  estimated centre of mass (mass budget in `ship_build.MASS_TABLE`; CoM is 4.83 m aft of the design
  origin, applied by the `SHIP_Hull` offset empty). Move/rotate/key the ship through `SHIP_ROOT` only.
- **Camera:** horizontal FOV, sensor fit HORIZONTAL (36 mm sensor). `fstop` turns on DOF; focus
  defaults to the look-at distance. `aperture_ratio=2.0` makes vertically stretched (anamorphic-style) oval bokeh.
- **World probe:** standard Cycles Environment Texture mapping (equirect, world Z up, u → azimuth,
  `az = (0.5 - u)·2π` from +X toward +Y), the same as the tracer's `world_equirect` projection. The
  world is black to camera rays by default (the tracer supplies the plate) but still lights the ship.
- **Render output:** Cycles CPU, OIDN, adaptive sampling, view transform **Standard** (no Filmic/AgX
  baked in), film transparent, 32-bit ZIP **multilayer EXR** with passes `Combined` (RGBA),
  `Depth`, `Emit`, and light groups `Combined_ship_lights` (every ship lamp, strobe, nav, grid and
  plume, including the light they throw on the hull), `Combined_env` (world probe) and
  `Combined_key` (sun lamps from `add_key_light`), plus Cycles' `Noisy Image`. Only `Combined` is
  denoised. Light-group passes stay noisy, so denoise them in comp or use more samples.

## Control properties (custom props on the `SHIP_CTRL` empty)

| prop | drives | 1.0 = nominal |
|---|---|---|
| `beacon` | dorsal + ventral xenon strobe lenses (emission 900) and 2 real point lights (2600 W / 1800 W) | on; >1 allowed for flash peaks |
| `nav` | red port / green starboard lenses on the bus and radiator leading tips + 6 small point lights | on |
| `running` | small warm-white hull lights (nose, PPU corners, radiator trailing tips) | on |
| `engine` | ion-grid aperture glow (hex array, object space), 3 plume volumes, 3 blue point lights | full thrust |
| `interior` | hatch window + OPNAV pod status LEDs (warm) | on |
| `dish_az_deg` | `Dish_Az` rotation about its local Z (+ = dish turns toward port) | — |
| `dish_el_deg` | `Dish_El` rotation about its local X (+ = dish tilts dorsal) | — |

Everything is wired with drivers (material Value nodes named `CTRL_<prop>`, light `energy`, pivot
rotations), so keying the props animates the ship. `set_controls(..., frame=f)` keys all seven.
Light props get CONSTANT interpolation (crisp strobes); the dish gets Bezier. Collision-free HGA
range: |az| ≤ 90°, −60° ≤ el ≤ 60°.

## Objects

- `SHIP_ROOT` → `SHIP_CTRL`, `SHIP_Hull` (CoM offset) → everything below
- `Dish_Az` (pivot on the gimbal, design (0, 26, 0)) → `SHIP_Dish_AzStage`, `Dish_El` → `SHIP_Dish_ElStage`, `SHIP_Dish_Reflector`
- Meshes: `SHIP_Hull_Bus` (bus core, MLI blankets with real pillow/fold geometry, tape, service
  ring, louvers, adapter), `SHIP_Details` (RCS, handrails, bolts, docking ring/hatch, star trackers,
  OPNAV pod, grapple fixture, whips, magnetometer boom, lamp housings), `SHIP_Stencils` (text converted
  to mesh: LSV-7 registration, warnings, trefoils, tank/radiator/PPU markings), `SHIP_Truss`,
  `SHIP_Tanks`, `SHIP_Radiators`, `SHIP_Aft` (shield, reactor + fins, PPU, thrusters), `SHIP_Dish_Mast`,
  `SHIP_Lamps` and `SHIP_Interior` (emissive, light group `ship_lights`),
  `SHIP_IonGrid_0..2`, `SHIP_IonPlume_0..2` (emission-only volume; camera-visible only, casts nothing).
- Lights: `SHIP_Beacon_Dorsal`, `SHIP_Beacon_Ventral`, `SHIP_NavGreen_Bus`, `SHIP_NavRed_Bus`,
  `SHIP_Nav_Rad0..3`, `SHIP_Engine_0..2` (all light group `ship_lights`).
- Mesh attributes: `UVMap` (metres), `Seam` (distance to blanket edge, used for stitching/folds),
  `part_rnd` (per-part random 0..1 for panel-to-panel variation).

**Polycount:** 288,292 triangles in 19 mesh objects (no subdivision modifiers). **Build:** ~3 s.

## Materials

All are Principled BSDF node setups (`ship_materials.py`). Gold kapton / silver / black-kapton MLI
use ambientCG Foil002/Foil001 normal + displacement maps at two scales, with anisotropy, per-blanket
UV offset/rotation, and billow. Stitching, edge tucks and tack buttons come from the Seam UV. Crevice
dust comes from the AO node. White thermal paint has panel tint variation, orange peel, smudges
(SurfaceImperfections003), scratches (Scratches002), micrometeoroid pits with spall halos, and
crevice grime + frost. There are also brushed/anodised aluminium (Metal009), carbon composite, the
ribbed near-black radiator coating, heat-tinted refractory metal (thin-film oxide), a hex-aperture
molybdenum ion grid, AR-coated optics, stencil paints and emissive lenses. `USE_AO` /
`AO_SAMPLES` in `ship_materials.py` trade crevice detail against speed.

## Render times (4 shared CPU cores, OIDN, adaptive sampling)

| shot | resolution / samples | time |
|---|---|---|
| hero 3/4 medium, full EXR passes, DOF f/8 | **1920×804 / 64** | **191 s** |
| review 01 hero 3/4 | 1280×536 / 64 | 45 s |
| review 02 macro MLI + strobe (f/2.8 DOF) | 1280×536 / 64 | 109 s |
| review 03 silhouette (ship 10 % of width) | 1280×536 / 64 | 13 s |
| review 04 aft 3/4, engines + plume volumes | 1280×536 / 64 | 77–148 s (CPU contention) |
| review 05 dish slewed | 1280×536 / 64 | 49 s |

Expect roughly 3–4 min per 1920×804 frame at 64 spp for medium shots, about 2× that for macro
(DOF + AO) and plume shots, and well under a minute for far/silhouette shots.

## Review stills (`review/`)

`01_hero_34_medium.jpg`, `02_macro_mli_beacon.jpg`, `03_silhouette_far.jpg`,
`04_aft_34_engines.jpg`, `05_dish_slewed.jpg`. These use AgX in Blender, a synthetic disk probe and
a warm hard key, standing in for the tracer probes.

## Physics departures (for docs/physics.md; the orchestrator owns that file)

- The ion thrusters sit aft of the reactor, on its unshielded side. A real NEP ship would put the
  thrusters and PPU in the shield's shadow. Cinema wins: the reactor/shield/engine stack reads as one
  aft power section.
- The xenon strobe is far brighter than a real beacon (2.6 kW point light, emission 900) so it can
  light the foil in the macro shot. The compositor grades it via `Combined_ship_lights`.
- The ion plumes glow visibly (real gridded-ion plumes are nearly invisible). They are soft and
  faint, and scale with `engine`.
- The radiators sit at 28° dihedral, inside the shield's shadow cone only approximately.

# THE LAST SIGNAL: state of the art research (Sept 2026)

Scope: a 90 s teaser at 24 fps (2160 frames), made entirely in code on CPUs. It uses a custom C++ Kerr tracer, Blender
Cycles (CPU), a numpy compositor and Python audio, and renders on GitHub Actions. Units: G = c = M = 1 unless stated.
Every number below is a starting value to tune by eye. "(unverified)" marks claims that came from memory or a
secondary source and were not checked against a primary source.

---

## 0. Recommendations for THE LAST SIGNAL: the 15 most impactful choices

1. **Spin a ≈ 0.6, camera inclination 78–86°, disk from ISCO (3.83 M) to about 30 M.** This is the Interstellar
   compromise. At a = 0.999 the shadow's left edge goes flat and the disk sits off-centre, which Nolan and Franklin
   judged "too confusing" ([DNGR paper §4.1](https://arxiv.org/abs/1502.03808)). Record it in `docs/physics.md`.
2. **Volumetric disk for hero and close shots, thin disk only for distant and background shots.** Use a Gaussian
   vertical profile with H/r ≈ 0.02–0.05 and emission plus absorption ray marching. DNGR used three disk models:
   thin, a voxel volume of about 17 M voxels, and a procedural Mantra model for close-ups.
3. **Turn the relativistic look down.** DNGR removed Doppler colour and intensity shifts for the film. Keep an
   asymmetry so the rotation reads: intensity ∝ g^k with k ≈ 1.5–2.5 (physical: 3–4), and colour-temperature
   shift at about 30–50 % of the physical value. The warm, nearly uniform 4500 K disk is the Gargantua look.
4. **Animate turbulence with two advected layers that reset per radius and cross-fade.** Neyret 2003 does this, and
   Heitz & Neyret 2018 add a variance-preserving blend. Pure Keplerian advection winds the noise into a vinyl-record
   pattern within a few orbits (§1.5.3).
5. **Stars come from a catalogue and are splatted, never sampled from a texture.** Use triangle inverse mapping of the
   per-pixel lens map. Each lensed image goes in at sub-pixel position with a fixed Gaussian PSF (σ ≈ 0.8 px) and
   clamped magnification. The diffuse Milky Way (SVS Deep Star Maps with point sources removed) comes from
   texture lookups with ray-differential filtering. DNGR held star flicker at ≤2 % (§1.5.5).
6. **Adaptively supersample around the critical curve.** Where neighbouring rays differ in fate or equator-crossing
   count, use 16–64 spp, and 4 spp elsewhere. The photon ring is what reads as a real black hole.
7. **Sell scale with a ladder: ship, then debris and dust, then disk, then hole.** Keep deep focus on the immense
   objects (shallow depth of field makes things look like miniatures), move big things slowly across frame, and
   add a disk-lit forward-scattering haze as a stand-in for atmospheric perspective.
8. **Make the camera feel operated.** Use a critically damped spring follow (ζ ≈ 0.8, fn ≈ 0.5 Hz), 1/f drift of
   0.05–0.2° at 0.05–2 Hz, and no handheld shake in open space. Hard-mounted hull cameras get 8–15 Hz
   micro-jitter of ≤0.3 px (the Interstellar "IMAX GoPro" approach).
9. **Use one scene-linear pipeline with one display transform, applied in the compositor.** Render Blender layers as
   linear EXR with the "Standard" view and no look, and never bake AgX in Blender. Use an AgX-style log2 plus
   sigmoid (−12.5 to +4 EV around 0.18). Avoid ACES 1.x, which skews saturated oranges.
10. **Finishing order:** lens effects in linear (energy-conserving multi-Gaussian bloom at a gain of 0.02–0.05,
    veiling glare, streaks only above about 200× mid grey, edge-only chromatic aberration, horizontal barrel
    distortion, vignette), then halation (red and orange, linear), then the tone map, then grain (display space,
    luma-dependent), then encode. Render the 2.39:1 area only (1920×804) and letterbox to 1080.
11. **Edit to trailer grammar.** Hold slow openers for 4–7 s, cut escalation shots to 1.5–3 s, and hold the reveal for
    at least 8 s. Put 1–2 s of true silence before the title hit, then add a post-title button. Cut 1–2 frames before
    the hit, and let sound lead picture by 6–12 frames on reveals.
12. **Build every hit from layers:** transient (0–20 ms), body (20–200 ms), sub (40–55 Hz sine with a 5–10 ms
    attack) and tail (convolution reverb with RT60 of 4–8 s). Precede big hits with a reverse-reverb swell or a
    Shepard riser.
13. **Make it phone-proof.** Micro-speakers resonate at about 500–1000 Hz and roll off at 12 dB/oct below that. Add
    parallel harmonic generation (2nd–5th harmonics of the sub band, band-passed to about 150–1000 Hz). Master to
    about −14 LUFS integrated, short-term peaks of −10 to −8 LUFS, and ≤ −1 dBTP.
14. **Keep licensing clean.** Synthesise everything, including the reverb IRs. Optional real space audio from
    space-audio.org is CC BY 4.0 with an exact credit line. Chandra sonifications carry no copyright claim but have
    a third-party caveat. Use only OIDN (Apache-2.0, in Blender). Skip the upscalers, interpolators and music
    models.
15. **Farm: plan job, then a cost-balanced matrix of 60–120 jobs of 30–90 min each, then an assemble job, then a
    pre-release.** Cache the Blender tarball and pass the compiled tracer as an artifact. Every frame must be
    idempotent and resumable. Budget: 20 runners × 6 h × 4 vCPU ≈ 480 vCPU-h per wave, about 13 vCPU-min per frame
    for 2160 frames.

---

## 1. How black holes have been rendered for film and visualization

### 1.1 DNGR: Double Negative for *Interstellar* (James, von Tunzelmann, Franklin, Thorne, CQG 2015)

Paper: <https://arxiv.org/abs/1502.03808>. Facts taken from the text:

- **Ray bundles (beams), not single rays.** DNGR integrates the central null geodesic together with the evolving
  elliptical cross-section of a beam (from the geodesic deviation / optical scalar equations). The authors say this
  was "crucial for achieving IMAX-quality smoothness without flickering" at 23 M pixels per frame.
- **Star anti-flicker spec.** Stars are points. Each pixel's beam starts with a radius of 2× the pixel spacing. A
  star's intensity across the beam is weighted by a truncated Gaussian. The filter is tuned so that a star centred
  on a pixel and a star between four pixels differ by at most 2 % in summed brightness, which the authors found
  unnoticeable. Stars "don't stretch when magnified". The beam's solid-angle change gives the lensing magnification.
- **Disk models.** (1) An infinitely thin disk coloured from an artist's image, with optical thickness.
  (2) A Houdini voxel volume of about 17 M voxels with a mip-mapped density, where the beam's major axis selects the
  mip level (this is how they avoided moiré). (3) A procedural disk for close-ups, made by running DNGR ray
  segments through Mantra. Layers close to the camera were rendered in flat space. The final images were composited
  from blended layers.
- **Look decisions.** The artist's disk is "anemic", thin, marginally optically thick, and has a uniform 4500 K
  blackbody temperature. Spin was lowered from 0.999 to 0.6 for readability. The true image, with Doppler factors of
  about 1.5 and 0.4 and I_ν ∝ ν³ beaming, is "exceedingly lopsided". The film used the version with no frequency
  shifts. White balance was set so that 6500 K renders as neutral.
- **Lens flare.** The flare is a convolution with a measured point spread function. They shot an HDR point source
  through Nolan's actual 35 mm and 65 mm IMAX and anamorphic lenses. The result is a "veiling flare": a soft glow
  that is "very characteristic of IMAX camera lenses", and this is the main reason the disk looks photographed.
- **Motion blur.** They used a 180° shutter (1/48 s). Motion blur is analytic: beams are swept through time, which
  roughly doubles cost but is much cheaper than Monte Carlo. Frames took 30 min to several hours on 10 cores.

**Takeaways for us:** beam footprints (or ray differentials) for stars, a volume mip-mapped by footprint, a PSF-based
veiling glare, turned-down Doppler, and a = 0.6. Their Fig. 16 image is licensed CC BY-NC-ND. Use it only as an
internal reference and never in the film.

### 1.2 NASA Goddard: Jeremy Schnittman (2019, 2024)

- **2019 "warped world"** ([SVS 13326](https://svs.gsfc.nasa.gov/13326/)). A thin, hot disk around a
  **non-rotating** hole, seen nearly edge-on to get the double-humped "carnival mirror" look. "Bright knots
  constantly form and dissipate … as magnetic fields wind and twist." Doppler beaming is left in. The photon ring is
  explicitly multiple nested rings. **Steal:** knots that are born and die (finite lifetime, never pure advection),
  and a near-edge-on framing.
- **2024 "plunge"** ([SVS 14576](https://svs.gsfc.nasa.gov/14576),
  [behind-the-scenes transcript](https://svs.gsfc.nasa.gov/vis/a010000/a014800/a014818/14818PlungeBHViz_BTS_HTML_Transcript.html)).
  It was prototyped at low resolution on laptops and produced on the Discover supercomputer: about 10 TB in about
  5 days on 0.3 % of 129k cores, at a few hours per frame. They reported **jitter** from large camera time steps
  with non-smooth interpolation. **Steal:** keep the camera path C² (Catmull-Rom or B-spline) and sample it per
  sub-frame. Never interpolate between coarse keyed states.
- Credit line if we ever reference their media: "NASA's Goddard Space Flight Center/Jeremy Schnittman".

### 1.3 EHT and ESO simulations

EHT image libraries use GRMHD simulations plus GR radiative transfer codes (ipole, RAPTOR, BHOSS and others). Their
optically thin hot flow looks like a **ring and crescent**: Doppler beaming brightens one side, and a sharp n = 1
photon subring sits on top of broader emission. The subrings are exponentially demagnified. In Schwarzschild each
half-orbit narrows a subring by about e^−π ≈ 1/23 (Johnson et al. 2020, *Sci. Adv.*;
[OSTI](https://www.osti.gov/pages/servlets/purl/1626057)). ESO and NASA "artist impressions" typically use a thin
disk with glow and a bright photon ring. **Lesson:** the crescent asymmetry reads as rotation to audiences who have
seen the EHT images, so keep some of it.

### 1.4 Open-source Kerr and Schwarzschild tracers: what to borrow

| Code | Type / hardware | License | Borrow |
|---|---|---|---|
| [GYOTO](https://github.com/gyoto/Gyoto) | C++, general metrics, thick tori, stars | GPL-3.0 | Kerr–Schild and BL metrics, RK adaptive steps, torus models (reference only; GPL) |
| [Odyssey](https://arxiv.org/abs/1601.02063) | CUDA GPU, Kerr radiative transfer | GPL-3.0 | RKF step control near the horizon; analytic photon-orbit tests |
| [ipole](https://github.com/AFD-Illinois/ipole) | C, polarized GRRT on GRMHD | **BSD-3** (2024) | Emission and absorption integration and camera tetrad code, which can be adapted with attribution |
| [RAPTOR](https://github.com/tbronzwaer/raptor) ([ASCL](https://ascl.net/1803.015)) | C/CUDA, arbitrary spacetimes | GRMONTY-derived license (check) | RK4 step h ∝ distance to horizon; adaptive camera grids |
| [kgeo](https://github.com/achael/kgeo) | Python, analytic Kerr geodesics (Gralla–Lupsasca) | GPL-3.0 | **Ground truth** for unit-testing our integrator (crossings, n-image positions) |
| [AART](https://github.com/iAART/aart) (arXiv 2211.07469) | Python, adaptive analytic ray tracing | MIT | Adaptive grids that sample photon-ring lensing bands densely |
| [starless](https://rantonels.github.io/starless/) (rantonels) | Python/numpy, Schwarzschild | GPL-3.0 | Binet-equation trick (geodesic as a Newtonian force r̈ = −(3/2)h²x/r⁵); disk T ∝ r^−3/4, blackbody LUT |
| [black_hole_shader](https://ebruneton.github.io/black_hole_shader/) (Bruneton 2020, [arXiv 2010.08735](https://arxiv.org/abs/2010.08735)) | C++ precompute + WebGL2, Schwarzschild | **BSD-3** | Star cube map filter (one star per texel, sum-mipmaps, tent-weighted footprint ≤9×9 texels); disk made of *particles on precessing orbits*; retarded time; bloom on mips |
| Riazuelo, *Seeing Relativity I–III* ([arXiv 1511.06025](https://arxiv.org/abs/1511.06025), [2008.04384](https://arxiv.org/pdf/2008.04384)) | Research code | papers | Correct star rendering (magnification, aberration), inside-horizon views, Kerr journeys |

Bruneton's measurements are a useful sanity check. Plain ray marching needed about 1000 steps per ray to reach
sub-degree star accuracy, and with 25 steps stars land several degrees off. Accuracy near the critical curve costs
time, so our tracer should use adaptive steps (below). He also names our risk: with approximate footprint filtering,
"a few stars flicker when the camera moves".

### 1.5 Techniques that matter for the look

#### 1.5.1 Integrator
- Use a Hamiltonian formulation, H = ½ g^{μν} p_μ p_ν = 0, in **Kerr–Schild** coordinates, which are
  horizon-penetrating and have no BL pole or horizon blow-up. The conserved E, L_z and Carter Q serve as error
  monitors.
- Integrate with adaptive Dormand–Prince RK45: rtol 1e-8 near r < 10, looser far away. Clamp
  h ≤ 0.1·(r − r₊) near the horizon. Stop at r < r₊·1.01 (captured) or r > 1000 (escaped). Map the final momentum
  to a sky direction.
- **Validate against kgeo:** check crossing radii and image positions to 1e-5, and that the shadow edge sits at
  b = 3√3 ≈ 5.196 M for a = 0.
- Parallelise with OpenMP over 8×8 tiles, and use a deterministic per-pixel seed of hash(shot, frame, px) for
  temporally coherent sampling.

#### 1.5.2 Disk: thin vs volumetric, and the recommended model
- **Thin disk:** one intersection per equatorial crossing, with opacity accumulated per crossing. It gives crisp
  higher-order images and is cheap. Up close it looks like a CG "vinyl record". Use it for wide and background shots.
- **Volumetric disk:** gives thickness, soft self-occlusion, a far-side arc with parallax, and supports fly-overs.
  Solve dI/ds = j − α I only inside the slab |z| < 3H(r). Use steps of about H/6, jittered per pixel. Cost is 3–10×
  that of the thin disk.
- **Density:** ρ = ρ₀ · R(r) · exp(−z²/2H²) · (0.35 + 0.65·turb), where H = h·r and h = 0.02–0.05.
  R(r) = smoothstep(r_isco·0.95, r_isco·1.3, r) · (r/r_isco)^−1.5 · (1 − smoothstep(0.6 r_out, r_out, r)). Add a
  faint plunging region (5–10 % density) inside the ISCO for fall-in wisps.
- **Emission:** Novikov–Thorne T(r) ∝ [r^−3(1 − √(r_in/r))]^{1/4}, which peaks at **r ≈ 1.36 r_in**. For the
  cinematic version, map it to about 3500–6500 K with a white-hot inner disk and amber outer disk, or use DNGR's
  constant 4500 K and let structure carry the variation. Store a blackbody→RGB LUT (CIE 1931, Wyman et al. 2013 fit,
  already in the repo).
- **Shading:** g = 1/[u^t(1 − Ω λ)] with λ = −p_φ/p_t and Ω = 1/(r^{3/2} + a) (prograde Kepler). Observed
  intensity is g^k × I(T·g^c). Physics has k = 4 (bolometric) and c = 1. Cinema uses k ≈ 2 and c ≈ 0.4. Expose
  so the approaching inner edge clips softly into white under the tone map.

#### 1.5.3 Turbulence that does not over-shear over time
The problem: the inner disk orbits much faster than the outer (Ω ∝ r^−3/2). Advecting noise with Ω(r) winds it into
thin concentric rings within a couple of orbits, and the rings then read as grooves.

The fix is Neyret's *Advected Textures* (SCA 2003,
[paper](http://www-evasion.imag.fr/Publications/2003/Ney03/)), which regenerates and cross-fades texture layers
based on accumulated deformation. Combine it with a variance-preserving blend (Heitz & Neyret, HPG 2018, "by-example
noise … histogram-preserving blending"). Recipe:

1. Use texture coordinates u = ln r (so features scale with radius) and φ. Build anisotropic fBm stretched 4–10×
   along φ for filaments. Use 4–6 octaves, lacunarity 2.0, gain 0.5.
2. Choose a visual time scale. Real periods are far too slow: for 10⁹ M☉, GM/c³ ≈ 4917 s and the ISCO period at
   a = 0.6 is 50.8 M ≈ 70 h. Pick s so the ISCO period is about 20–40 s on screen, and note this in physics.md.
3. Give each radius its own reset period T(r) = f · 2π/Ω_vis(r), with f ≈ 0.3–0.5 of an orbit. Shear is then equal
   at every radius.
4. Run two layers offset by T/2: φ_i = φ − Ω_vis(r)·((t + i·T/2) mod T). Weights are w_i = triangle(phase_i) or
   sin² of it, and w₀ + w₁ = 1. Give each layer a new noise seed or offset at each reset.
5. Blend: n = μ + [w₀(n₀ − μ) + w₁(n₁ − μ)] / √(w₀² + w₁²). Without the √ term, contrast visibly "breathes" at
   every cross-fade.
6. Add slow evolution with a 4D noise w-coordinate (about 0.05–0.1 per second) so structure changes as well as moves,
   like Schnittman's knots. Add sparse "hot spots" (Gaussian blobs with lifetimes of 3–8 s and emission ×2–4)
   on Keplerian orbits.
7. The radial dependence of T(r) causes seams between annuli, so jitter the reset phase with a smooth function of
   ln r (not white noise). A Bruneton-style sum of orbiting "linear particles" is an alternative that shears
   naturally without resets.
8. **Retarded time:** evaluate the disk texture at t_emit = t_cam − Δt_ray (from the integrated coordinate time).
   Higher-order images then show earlier states, which is correct and subtly alive. Bruneton precomputes this.

#### 1.5.4 Photon ring
- At a = 0.6 and 1080p, with a shadow about 400 px across, the n = 1 ring is a few px wide and the n = 2 ring is
  about 0.2–0.4 px. It shows only with anti-aliasing, as a single bright hairline.
- **Adaptive sampling:** trace a base grid at 1–4 spp. Flag pixels whose 3×3 neighbours differ in fate
  (captured/escaped/disk), in equator-crossing count n, or in escape direction by more than 3 px. Resample flagged
  pixels at 16–64 stratified spp. Expect about 3–6 % of pixels to be flagged.
- Accumulate each equatorial crossing with transmittance for the thin disk, or integrate the whole path for the
  volume. The ring appears on its own, so never paint it on. If needed, a cinematic boost of the n ≥ 1 contribution
  by ×1.2–1.5 is fine; document it.

#### 1.5.5 Star lensing without flicker (the most common failure)
- **Don't** look stars up in an equirectangular texture per ray. They will stretch, alias and twinkle as the
  lensing map moves.
- **Method A (recommended, forward splat by triangle inverse mapping):**
  1. Store each pixel corner's escape direction (the lens map) at render resolution, including the supersampled
     rows near the ring.
  2. Split each pixel quad into 2 triangles. For every catalogue star (bucketed in a HEALPix or cube map grid), find
     the triangles whose sky-space images contain it, then barycentric-interpolate its sub-pixel image position.
     Magnification μ = area_pixel / area_sky, and its sign gives parity.
  3. Skip triangles that straddle captured and escaped rays, or that span multiple crossing counts.
  4. Splat flux F·min(|μ|, 30) with an energy-normalised Gaussian, σ = 0.7–0.9 px, truncated at 3σ. This gives
     multiple images, Einstein-ring arcs and exact sub-pixel motion, and no flicker because the splat integral is
     constant.
  5. For motion blur, splat at every sub-frame, or as a swept segment.
- **Method B (DNGR/Bruneton gather):** use ray differentials (finite differences to neighbouring pixel rays) to build
  a footprint ellipse on the sky, then sum stars inside it with a tent or Gaussian weight. Apply Bruneton's
  one-star-per-texel mip scheme: sum colours, and take a luminosity-weighted average position.
- **Catalogue:** use Gaia DR3 or Tycho-2 and Hipparcos. Flux F = 10^(−0.4 m). Colour from B−V via Ballesteros 2012:
  T = 4600 K·(1/(0.92(B−V)+1.7) + 1/(0.92(B−V)+0.62)). Cut at about m ≤ 9–10 for 1080p; fainter stars belong in
  the diffuse map. Gamma-map the magnitudes for cinema, and keep the brightest 20–50 stars well above the rest so
  the sky has hierarchy, not snow.
- **Diffuse sky** (Milky Way texture with point sources removed, as the repo already does from
  [SVS 4851](https://svs.gsfc.nasa.gov/4851)): sample with an anisotropic footprint from ray differentials, or 4–16
  spp, with a mip level chosen from the major axis (DNGR).

#### 1.5.6 Useful numbers (M = 1)

| a | r₊ | ISCO (prograde) | photon orbit pro / retro | ISCO period |
|---|---|---|---|---|
| 0 | 2.000 | 6.000 | 3.000 / 3.000 | 92.3 M |
| 0.6 | 1.800 | 3.829 | 2.189 / 3.630 | 50.8 M |
| 0.9 | 1.436 | 2.321 | 1.558 / 3.910 | 27.9 M |
| 0.99 | 1.141 | 1.454 | 1.168 / 3.991 | 17.2 M |

GM/c³ is 19.7 s for Sgr A* (4×10⁶ M☉) and 4917 s for 10⁹ M☉. The shadow radius for a = 0 is 5.196 M.

---

## 2. Premium sci-fi trailer and VFX craft

### 2.1 Shot grammar worth stealing
- **2001 (1968):** long, silent, slow traverses of models against black. Scale comes from time and detail, and
  there is no sound in vacuum except breathing. **Steal:** silence as a design choice, and slow lateral traverses.
- **Interstellar (2014):** hard-mounted IMAX cameras on large miniatures. Van Hoytema "mimicked NASA IMAX
  documentaries" with the camera fixed to the craft, adding jitter only for launch G-forces
  ([Wikipedia](https://en.wikipedia.org/wiki/Interstellar_(film))). The Endurance appears as a speck against Saturn
  or Gargantua with silence on the soundtrack. **Steal:** a camera that belongs to an object (the hull, an antenna
  or a debris shard), never an omniscient floating camera, plus a single tiny ship against an immense body with
  near-silence.
- **Gravity (2013):** very long takes with the Earth filling the frame, where the tiny human against a huge curved
  horizon carries the scale, and sound is only what travels through contact. **Steal:** vibration-conducted sound
  (hull thumps, low-passed) instead of airborne sound.
- **Sunshine (2007):** the star as an overwhelming light source. It over-exposes, filters get pulled, and people
  squint. **Steal:** exposure itself as drama. Let the disk push the whole frame into flare and halation for one beat.
- **Arrival (2016):** the shell reveal. Low cloud rolls over Montana hills, the helicopter is tiny, and the camera
  approaches slowly and patiently. **Steal:** reveal through a veil (dust or the disk edge), then hold.
- **Dune (2021) and Part Two:** Fraser: "I love playing with scale". The harvester sequence is a **scale ladder**:
  intimate ornithopter, then the harvester, then the sandworm in the distance
  ([GoldDerby](https://www.goldderby.com/film/2022/greig-fraser-dune-cinematographer-video-interview/)). Epic wides
  are cut against extreme close-ups, and the image went out to film and back for texture. **Steal:** alternate
  macro-scale shots with detail close-ups of the ship (dish, beacon, frost).
- **Prometheus and Alien: Covenant:** ship landings as small silhouettes against terrain, with lights for scale,
  and a slow push on the derelict. **Ad Astra (2019):** grounded, practical and sparse, with long lenses and a
  restrained palette.

### 2.2 Selling scale in space: checklist
1. **Known-size foreground:** hull panels, the beacon light, a dish. Put dust and debris with parallax between the
   camera and the subject.
2. **Angular speed means size.** Immense objects cross the frame slowly, over 10 s or more. The ship may move fast
   in frame, but the hole never snaps.
3. **Deep focus on big things.** Shallow depth of field reads as a miniature ("tilt-shift"). Use DoF only for
   out-of-focus foreground motes and debris close to the lens.
4. **Atmospheric perspective analog:** a thin forward-scattering haze lit by the disk (Henyey–Greenstein g ≈ 0.6–0.8,
   optical depth 0.02–0.1 over the shot) reduces contrast with distance and glows around bright sources.
5. **Frame-breaking size:** crop the disk with the frame edges so the object is bigger than the screen. Use partial
   reveals: an occluding limb, the disk edge rising.
6. **Shared light:** the disk lights the ship, including its warm key light, disk-coloured rim and the shadow it
   casts. This ties the two objects into one space.
7. **Long lens for relationships, wide lens for intimacy.** Use 150–300 mm-equivalent compression for "ship before
   the hole", and 24–35 mm near the hull.
8. **Sound:** sub-bass weight on big objects, and near-silence plus small ship sounds on the tiny subject.

### 2.3 Teaser editing rhythm (proposed 90 s beat map)
Trailers follow a compressed three-act build: setup with shots held 2–4 s, then a turn often marked by a smash cut
or drop to silence, then a montage with shortening cuts, the title, and a "button"
([Film Editing Pro](https://www.filmeditingpro.com/trailers-teasers-promos-lengths-formats-tips/),
[Derek Lieu](https://www.derek-lieu.com/blog/2017/9/10/the-matrix-is-a-trailer-editors-dream): "if a trailer feels
high energy all the time, none of it will feel high energy").

| t (s) | beat | shot lengths |
|---|---|---|
| 0–6 | cold open: black, signal blips, drone fades in | 1–2 shots, or black |
| 6–28 | the void and the ship (world and scale ladder) | 4–7 s holds, 4–5 shots |
| 28–50 | signal gets stronger and wrongness appears (lensing hints, ship reacts) | 2–4 s, cuts land on pulses |
| 50–54 | drop to near-silence, the "breath" | one held shot |
| 54–66 | **the reveal:** braam, disk and photon ring | one 8–12 s hold with a slow push |
| 66–78 | escalation montage: debris, the ship dwarfed, the arc overhead | 0.7–2 s, accelerating |
| 78–80 | **true silence** (or room tone at −50 dBFS) on black or a held frame | 1–2 s |
| 80–85 | title on the biggest hit | 3–5 s |
| 85–90 | button: one last short ominous beat (the signal answers, or the beacon goes dark) | 2–4 s |

Cutting rules:
- Cut on or 1–2 frames before a hit, so the picture change seems to cause the sound.
- Use J-cuts, where sound leads the next picture by 6–12 frames, for reveals.
- A new complex image needs about 2 s to parse, so never cut a big wide shorter than 2.5 s.
- Every signal pulse and sound cue comes from `production/tls/edl.py`.

### 2.4 CG camera language: an operated feel
- **Motion model:** the operator target is a keyed spline. The camera follows it through a damped spring (ζ 0.7–0.9,
  natural frequency 0.3–1 Hz), which gives ease-in, slight overshoot and correction.
- **Drift:** pink (1/f) noise, band-limited to 0.05–2 Hz. Rotation amplitude is 0.05–0.2°, translation is tiny.
  Use independent seeds per axis, and give roll about 30 % of the pan and tilt amplitude.
- **Handheld** (interiors only): body sway below 3 Hz, plus 3–9 Hz tremor, with nothing above 15 Hz (from camera
  image-stabilisation literature). **Hard-mounted hull camera:** 8–15 Hz vibration at ≤0.3 px, plus a slow attitude
  wobble.
- **Focus pulls:** a 0.5–1.5 s ease on focus distance, with **lens breathing** of a 1–2 % FOV change over the pull.
  Pull only when a foreground object exists.
- **Shutter:** 180° (1/48 s). Accumulate 4–8 sub-frames, or splat analytic streaks for stars. At immense scale motion
  blur is small, so it matters most for debris and dust.

### 2.5 Anamorphic 2.39:1 characteristics (apply in the compositor)

| Trait | Real lenses | Our parameter |
|---|---|---|
| Frame | 2.39:1 inside 16:9 | render **1920×804** and letterbox 138 px top and bottom |
| Bokeh | 2× squeeze gives **vertical ovals, width ≈ 50 % of height** ([DFI](https://www.dfirentals.com/news/anamorphic-lenses-explained-why-filmmakers-love-the-squeeze)) | DoF kernel with an elliptical aperture, aspect 1:1.6–1:2 (tall) |
| Flares | horizontal streaks, often blue, from bright points only | threshold ≈ 200× mid grey (scene-linear ≥ 36), 1D exponential kernel of 0.25–0.5 × frame width, tint (0.55, 0.75, 1.0), gain 0.002–0.01 |
| Distortion | barrel distortion stronger on the horizontal axis; modern designs add edge pincushion to stop "swimming" | render 4–6 % overscan, barrel k₁ ≈ −0.02 to −0.04 on x (half that on y), then crop |
| Mumps | at close focus the effective squeeze falls and centre subjects widen | ignore (no faces), or add +1–2 % x-stretch on close-focus shots |
| Edge softness | falls off toward corners | radial blur σ from 0 at r = 0.6 to 1.0–1.5 px at the corners |
| Vignette | about 0.5–1 stop at the corners | cos⁴-like, −0.7 stop at the corners, applied in linear |
| Chromatic aberration | lateral CA at edges only | radial scale R ×(1 + c), B ×(1 − c) with c ≈ 0.0006–0.0012 (1–2 px at the corners, 0 at centre); 3–5 spectral taps avoid hard fringes |

### 2.6 Grading and finishing

**Order (all linear until the tone map):**
1. merge layers
2. veiling glare and bloom
3. anamorphic streaks
4. CA, distortion, vignette, edge softness
5. halation
6. exposure and white balance
7. **display transform**
8. display-referred trims
9. grain
10. letterbox, then Rec.709 (BT.1886) encode

**Display transform: ACES vs AgX vs custom.**
- **ACES 1.x:** saturated lights such as neon blues and reds and hot oranges skew or clip
  ([ACESCentral](https://acescentral.com/knowledge-base-2/crushed-colors-caused-by-brightly-colored-lights/)). Avoid it
  for a blackbody disk.
- **ACES 2.0** (end-user releases in 2025): tone-maps J in a JMh space, preserves hue, and gives a gentler
  roll-off ([docs](https://docs.acescentral.com/background/about-rendering/)). It is good but needs OCIO 2.4+ and is
  heavy to reimplement in numpy.
- **AgX (Troy Sobotka; default in Blender since 4.0):** bright saturated colours path to white "similar to real
  cameras" ([Blender notes](https://developer.blender.org/docs/release_notes/4.0/color_management/)). It avoids
  the ACES hue skews and Filmic's "Notorious 6". Minimal form (Wrensch,
  [iolite blog](https://iolite-engine.com/blog_posts/minimal_agx_implementation)):
  1. inset matrix
  2. log2 encode clamped to [−12.47393, +4.026069] EV around 0.18
  3. a 6th-order polynomial sigmoid
  4. outset matrix
- **Recommendation:** use the AgX structure, reimplemented in numpy with our own tunable sigmoid (contrast,
  toe, shoulder) plus a "look". The look should have slightly cool shadows, warm highlights and −10 to −20 %
  saturation in the top stop.
- Keep true black (0) away from the disk. Blacks lift only through veiling glare.
- Blender renders go out as linear EXR, view "Standard", no look, so there is exactly one tone map.

**Bloom that does not take over.** Use an energy-conserving, thresholdless blend: out = (1 − k)·img + k·(PSF ∗ img),
with k = 0.02–0.05. The PSF is a sum of Gaussians with a long tail, for example σ = {2, 6, 16, 48, 128} px with
weights {0.45, 0.25, 0.15, 0.10, 0.05}. Alternatively use a 6–8 level mip chain (Call of Duty: AW style,
13-tap downsample and tent upsample; unverified detail).

Add a separate **veiling glare** term: a very wide PSF (σ ≈ 300–600 px) at ≈0.5–1 % energy. This is the "IMAX
veiling flare" of DNGR, and it lifts the blacks around the disk. Bruneton applies bloom before the tone map on
mips. Check the result: a single star must not grow a halo wider than about 3 px.

**Halation** (film: light passes the emulsion, reflects off the base and re-exposes the red layer, giving a
red-orange fringe; [color.io](https://www.color.io/user-guide/film-halation)). Steps:
1. Build a soft-knee highlight mask in linear, h = img · smoothstep(1.0, 8.0, luma) (mid grey 0.18).
2. Blur with an exponential-like kernel made of Gaussians at σ ≈ 3, 10 and 25 px (1080p).
3. Compute halo = max(blur(h) − 0.6·h, 0), which emphasises the fringe outside edges.
4. Add halo × (1.0, 0.35, 0.05) × strength, with strength 0.04–0.12.

Halation goes after lens effects and before the tone map. It should be visible on the disk edge, the ship's lit rim
and the title.

**Grain.** Newson et al. 2017 ([CGF](https://onlinelibrary.wiley.com/doi/abs/10.1111/cgf.13159),
[IPOL](https://www.ipol.im/pub/art/2017/192/)) is a physically based Boolean grain model:
- grain radius µ_r ≈ 0.1 input px, filter σ = 0.8 output px, and N Monte Carlo samples
- cost is 2.4 s for 512² with the pixel-wise algorithm, which is too slow per frame
- the code is **GPL-3.0**, so reimplement it from the paper; do not vendor it

Practical plan:
1. Precompute Newson-style grain plates offline: 16 grey levels × 8 seeds at 1024², then tile with random
   offsets and flips per frame.
2. Alternatively, use luma-dependent Gaussian grain: generate noise, blur it with σ 0.6–0.9 px, and scale it with
   σ(L) that peaks in the midtones at 1.5–3 % of code value and falls to about 0.5 % in deep black.
3. Mix colour as 70 % shared luma noise and 30 % independent per-channel noise, with blue strongest.
4. Apply grain in display space after the tone map, with new noise every frame.
5. Encode with x264 `-tune grain` at CRF 14–16. Otherwise the encoder smears the grain into blocks, and YouTube
   will re-encode on top of that.

---

## 3. Trailer sound design

### 3.1 Anatomy of a modern trailer mix
- **Bed:** drones (detuned oscillator stacks, filtered noise, granular or stretched space audio) with slow
  0.02–0.2 Hz movement and a tonal centre.
- **Pulses:** the signal itself (a sine ping plus formant, with pitch sagging for gravitational redshift). Pulses
  accelerate through Act 2.
- **Braam:** a massive low brass-like blast. It came from Mike Zarin's work on the first *Inception* teaser, which
  combined subway recordings, processing and pitch-shifted brass to make "a sound that cleared the room"
  ([Wikipedia](https://en.wikipedia.org/wiki/BRAAAM),
  [THR](https://www.hollywoodreporter.com/movies/movie-news/braaams-beginners-how-a-horn-793220/)).
- **Hits and impacts:** transient + body + sub + tail
  ([BOOM Library](https://www.boomlibrary.com/blog/top-tips-for-trailer-sound-design/)). Spread the layers across
  frequency and time, or the result gets muddy.
- **Risers:** noise sweeps, pitch rises and Shepard–Risset glissandi that build without resolving.
  **Reverse-reverb swells** lead into hits. **Whooshes** accent motion and transitions.
- **Sub drops:** a falling sine under a hit.
- **Silence:** the strongest element. Two seconds of silence before the last hit makes it land far harder.

### 3.2 Synthesis recipes (numpy/scipy, 48 kHz, float64, stereo)

| Element | Recipe |
|---|---|
| Drone | 5–9 saws or sines per note, detuned ±3–12 cents, through a lowpass at 200–800 Hz with a 0.03 Hz LFO. Add a pink-noise band (bandpass 60–300 Hz), slow stereo decorrelation, and a −3 dB sidechain dip under hits |
| Braam | Root C1 or D1 (32.7–36.7 Hz) + octave + fifth, 8 saws per voice. `tanh(4x)` waveshape, then a formant bandpass (500–1200 Hz, Q≈1.5) mixed with the raw signal. Attack 40–80 ms, pitch bend −1 to −2 semitones over 2 s, sustain 2–4 s. Add a 36–45 Hz sine sub with 10 ms attack. Convolve with a large-hall IR (RT60 6 s, 30 % wet) |
| Sub drop | Exponential sine sweep 150 → 32 Hz over 1.5–3 s, `a(t) = (1−e^{−t/0.008})·e^{−t/1.2}`, plus 2nd and 3rd harmonics at −12 and −18 dB (§3.4) |
| Impact | Transient: 0–15 ms, HP 2–4 kHz noise burst plus click. Body: 60–120 Hz sine with a pitch envelope (×2 → ×1 in 40 ms) and a distorted 200–800 Hz band, 20–200 ms. Sub: 45 Hz, 5–10 ms attack, 0.8 s decay. Tail: filtered rumble noise plus convolution reverb, 2–6 s. Align transients sample-accurately |
| Shepard riser | 8–10 sine partials spaced one octave apart, all gliding up at 1 octave per 4–8 s (wrapping). Amplitude uses a Gaussian envelope in log2 f, centred near 400–600 Hz with σ ≈ 1.5 oct |
| Reverse swell | Convolve the hit's first 200 ms with the IR (100 % wet), reverse it, fade in over 0.5–2 s, and end exactly on the hit sample |
| Whoosh | Pink noise through a bandpass that sweeps 300 Hz → 4 kHz → 800 Hz, with an amplitude bell and a pan sweep. Optionally add Doppler pitch ±3 % |
| Signal ping | 0.8–1.6 kHz sine plus a 3rd partial, 5 ms attack, 300 ms decay, with a feedback delay of 180–350 ms. Increase redshift (pitch down) with proximity |

Libraries:
- **numpy/scipy** (`scipy.signal` for butter, sosfiltfilt and oaconvolve) cover everything above.
- **[pedalboard](https://github.com/spotify/pedalboard)** is **GPL-3.0**. Using it as a tool is fine, since its
  outputs are not GPL, but importing it from our MIT code and redistributing both mixes licences. Prefer scipy.
- **[pyroomacoustics](https://github.com/LCAV/pyroomacoustics)** (MIT) simulates rooms, which is useful only for
  interior or hull resonances.
- **pyloudnorm** (MIT, BS.1770) measures LUFS in Python (licence from memory).

### 3.3 Convolution reverb with synthetic IRs (no licensing questions)
Build the IR in these steps:
1. Split the frequency range into octave bands from 63 Hz to 8 kHz. In each band, take independent Gaussian noise
   per channel and multiply by exp(−6.91 t / RT60_band).
2. Use RT60 from 8 s at 63 Hz down to 2 s at 8 kHz for "cathedral in the void". Use 1.2 s for a small hull.
3. Pre-delay 20–80 ms.
4. Add 6–12 sparse early reflections in the first 80 ms.
5. Decorrelate L and R (independent noise gives about 0 correlation; blend 10 % shared for a solid centre).
6. Fade in 2–5 ms.
7. Normalise to unit energy.

Apply the IR with `scipy.signal.oaconvolve`. Use it as a send (wet 15–40 %), and high-pass the wet signal at
80–120 Hz so sub hits stay tight.

### 3.4 Making sub-bass audible on phone speakers
Micro-speakers resonate at about **500–1000 Hz** and fall off at **12 dB/oct** below resonance; below about 300 Hz
they are nearly silent ([EE Times](https://www.eetimes.com/achieving-loud-rich-sound-from-micro-speakers/)).
The **missing fundamental** effect lets the ear infer a pitch from its harmonics, extending perceived bass by
about 1.5 octaves (Larsen & Aarts, *JAES* 50(3), 2002; see the
[MathWorks example](https://www.mathworks.com/help/audio/ug/psychoacoustic-bass-enhancement-for-band-limited-signals.html)).

Recipe:
1. Split off the sub band (LP at 120 Hz) and make it mono.
2. Pass it through a nonlinear device: a Chebyshev polynomial mix gives exact harmonic weights. For example, 2nd:
   0.5, 3rd: 0.35, 4th: 0.2 and 5th: 0.12. Normalise the input by an envelope follower, then re-apply the envelope.
3. Band-pass 150–1000 Hz.
4. Mix in at −10 to −4 dB under the original, and keep the true fundamental for headphones.
5. Check the result by auditioning it through an HP at 300 Hz ("phone sim") and an LP at 60 Hz ("sub only").

### 3.5 Loudness targets
- **Web:** YouTube normalises to about −14 LUFS integrated, so a hotter master only gets turned down. The target is
  **−14 LUFS integrated and ≤ −1 dBTP**
  ([Youlean table](https://youlean.co/loudness-standards-full-comparison-table/)).
- **Theatrical trailers:** limited to **85 dB Leq(m)** under TASA ([TASA](https://www.tasatrailers.org/leqm.html)).
  This is not needed for us.
- **Dynamics:** short-term peaks of −10 to −8 LUFS on the reveal and title, and quiet passages at −30 to −26 LUFS
  short-term. Anything quieter vanishes on phones. Aim for LRA 10–15 LU, and put a gentle bus compressor (2:1,
  slow attack) before the limiter.
- **Measure and finalise:** measure in Python (BS.1770), then run a final two-pass ffmpeg
  `loudnorm=I=-14:TP=-1.0:LRA=14:linear=true`, using the measured values in pass 2. Check true peak at 4×
  oversampling. Deliver AAC at 320 kbps, 48 kHz.

### 3.6 Free, properly licensed sources

| Source | Licence and terms | Exact credit |
|---|---|---|
| [space-audio.org](https://space-audio.org/) (U. Iowa: Voyager, Juno, Cassini, whistlers) | **CC BY 4.0**. Adaptation is allowed. Do not claim copyright on the material ([citation page](https://space-audio.org/citation.html)) | "Original space audio recordings provided courtesy of NASA and The University of Iowa. https://space-audio.org/" |
| Juno Ganymede flyby audio, [PIA25030](https://www.jpl.nasa.gov/images/pia25030-audio-of-junos-ganymede-flyby/) | NASA/JPL media guidelines | "NASA/JPL-Caltech/SwRI/Univ of Iowa" |
| Chandra sonifications (e.g., [Perseus 2022](https://chandra.harvard.edu/photo/2022/sonify5/)) | "No claim to copyright is being asserted"; use "in accordance with NASA guidelines". **Caveat:** audio segments and music "may require permission from the source" ([policy](https://chandra.harvard.edu/photo/image_use.html)). Sound design is by SYSTEM Sounds | Perseus: "X-ray: NASA/CXC/Univ. of Cambridge/C. Reynolds et al.; Sonification: NASA/CXC/SAO/K.Arcand, SYSTEM Sounds (M. Russo, A. Santaguida)" |
| NASA generally | Generally not copyrighted in the US. Do not imply endorsement, and do not use NASA insignia ([guidelines](https://www.nasa.gov/nasa-brand-center/images-and-media/)) | "NASA" plus the mission credit |
| [OpenAIR](https://www.openair.hosted.york.ac.uk/) IRs | Licence per IR, **mostly CC BY 4.0**; check each file | per-IR author and venue |
| [Voxengo IRs](https://www.voxengo.com/impulses/) | Royalty-free use, but **no redistribution for profit** and copyright retained. Committing them to a public repo is redistribution: fetch them at build time or avoid them | none required |

**Verdict:** synthesise everything by default. If real space audio is used, it should come from space-audio.org
(CC BY 4.0 with a credit line in CREDITS.md and ASSETS.md), fetched by `production/tools/fetch_assets.py`. Use it
granularly, time-stretched and layered as texture. Avoid the Chandra sonifications unless the credit and caveat are
accepted.

---

## 4. Free ML and processing tools on CPU: verdicts

| Tool | Licence (code / weights) | CPU viability | Verdict for THE LAST SIGNAL |
|---|---|---|---|
| [Intel Open Image Denoise](https://www.openimagedenoise.org/) 2.5.x | Apache-2.0 | Good: SSE4.1+ and ARM64; quality modes high, balanced (default) and fast | **Use** inside Blender Cycles with albedo and normal passes (prefilter "Accurate", quality "High"). For our tracer, **don't**: disk and volume emission has no meaningful albedo, and per-frame denoising flickers (OIDN is not temporal). Use deterministic stratified sampling and enough spp instead. Standalone `oidnDenoise` is fine for the odd Blender layer (PFM input, `--hdr --alb --nrm`) |
| [RIFE / Practical-RIFE](https://github.com/hzwer/Practical-RIFE) | MIT / MIT | About 1 s per 1080p frame pair (rough estimate) | **Skip.** Multi-image lensing, stars and thin rings produce warps and ghosts. Rendering real frames is cheaper than fixing artifacts |
| [FILM](https://github.com/google-research/frame-interpolation) | Apache-2.0 | TensorFlow, slow | **Skip** for the same reasons |
| [Real-ESRGAN](https://github.com/xinntao/Real-ESRGAN) | BSD-3 | Slow at 4×, feasible at 2× | **Skip.** It hallucinates texture, merges or kills faint stars and gives an "oil paint" look to smooth gradients. Render natively at 1920×804 |
| [AudioCraft/MusicGen](https://github.com/facebookresearch/audiocraft) | MIT / **CC-BY-NC 4.0** | Slow | **Avoid** (weights are non-commercial) |
| [Stable Audio Open 1.0](https://huggingface.co/stabilityai/stable-audio-open-1.0) | tools MIT / **Stability AI Community License**, gated | 1 B params, slow on CPU | **Avoid.** It is not an open licence (revenue-threshold and separate commercial terms) |
| [Bark](https://github.com/suno-ai/bark), [Demucs](https://github.com/facebookresearch/demucs) | MIT | OK | Not needed (TTS and source separation) |

**Bottom line:** only OIDN (via Blender) earns a place. Everything else costs quality, licence clarity or runtime.

---

## 5. GitHub Actions render farm

### 5.1 Limits (checked Sept 2026)

| Item | Value |
|---|---|
| Public-repo standard runners | **free, unlimited minutes** ([billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions)) |
| `ubuntu-latest` / `ubuntu-24.04` (public) | **4 vCPU, 16 GB RAM, 14 GB SSD**. Private repos get 2 vCPU and 8 GB ([runners](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)) |
| `ubuntu-24.04-arm` (public) | 4 vCPU and 16 GB, free. There is **no official Blender ARM64 build**, so use it for the tracer and compositor only |
| Job timeout | **6 h**. The workflow run limit is 35 days ([limits](https://docs.github.com/en/actions/reference/limits)) |
| Concurrency, Free plan | **20 jobs** (5 macOS) |
| Matrix | **256 jobs per workflow run** |
| Cache | **10 GB per repo**. Evicted after 7 days without access. Readable from the default branch by feature branches, but not the reverse. PR caches are scoped to the merge ref |
| Artifacts | upload-artifact **v7**. 500 artifacts per job, immutable, unique names. Retention 1–90 days on public repos (default 90). `archive: false` uploads a single file unzipped |
| Private-repo quota (for reference) | 2,000 min per month, 500 MB of artifacts |
| Releases | each asset **< 2 GiB**, up to 1000 assets per release, no total size limit |
| GITHUB_TOKEN | 1,000 API requests per hour per repo. Events it creates (push, release) **do not trigger other workflows** (this prevents loops) |

### 5.2 Sharding and budget
- 2160 frames. One wave gives 20 × 6 h × 4 vCPU ≈ **480 vCPU-h ≈ 13 vCPU-min per frame**, or about 3.3 min of wall
  time per frame per runner. Shots near the ring and in the volume cost 5–20× more than a starfield. **Budget per
  shot, not per frame.**
- **Plan job:** read the EDL and a per-shot cost model (measured on a 10-frame probe: seconds per frame per
  megapixel). Bin-pack frames into N jobs of 30–90 min each, and emit the matrix as JSON
  (`strategy.matrix: ${{ fromJSON(needs.plan.outputs.matrix) }}`). Short jobs lose less on a failure, balance better
  and fit under the 256-job cap.
- Use `fail-fast: false`, `max-parallel: 20`, and `timeout-minutes` of about 1.5× the estimate (≤ 330).
- **Idempotent frames:** the file name encodes shot, frame and quality. Seed = hash(shot, frame). A job first
  downloads any existing artifacts or cache for its frames and skips those already done. Frames are written as
  they finish, and upload runs under `if: always()`, so a timed-out job still delivers its partial work.
- **Layers:** the tracer writes half-float EXR (ZIP or DWAA). Blender writes multilayer EXR, and the compositor runs
  per shot in a later job. Keep intermediate artifacts at `retention-days: 3–7` and `compression-level: 0` (EXR and
  PNG are already compressed).
- Each job needs 1–3 min of setup (checkout, cache restore, apt). Keep jobs ≥ 20 min so this overhead stays < 10 %.

### 5.3 Caching and binaries
- **Blender:** download the pinned tarball (5.2 LTS, released 14 Jul 2026) from download.blender.org and check its
  sha256. Cache it with `actions/cache@v4` or newer (v6 is current) under the key `blender-5.2.x-linux-x64-<sha>`.
  Use `lookup-only` in the plan job to warm it once before the matrix fans out.
- **Tracer:** build once in a `build` job with `-O3 -march=x86-64-v3` (the runners have AVX2; confirm with lscpu)
  and ccache (cache key `hashFiles('production/tracer/**')`). Upload the binary as an artifact and download it in
  every render job. This beats compiling 20×.
- **Python:** `actions/setup-python` with `cache: pip`, or cache a venv keyed on the requirements hash.
- **Disk:** 14 GB is guaranteed. Deleting `/usr/share/dotnet`, `/usr/local/lib/android` and `/opt/ghc` frees
  roughly 20–30 GB if needed (unverified amount).

### 5.4 Triggers, releases and workflow skeleton
- **Triggers:**
  - `on: push: branches: [claude/**, main]` with `paths: ['production/**', '.github/workflows/farm.yml']`
    (`paths` and `paths-ignore` cannot both be used on one event)
  - `workflow_dispatch` with inputs `quality` and `shots`
  - `concurrency: { group: farm-${{ github.ref }}, cancel-in-progress: true }`
- **Pre-releases:** `softprops/action-gh-release@v3` with `permissions: contents: write`, `tag_name: preview-${{
  github.run_number }}`, `prerelease: true` and `make_latest: false`, uploading the MP4 and contact sheet.
  Alternatively, in a step with `GH_TOKEN`, run `gh release create "$TAG" out/*.mp4 --prerelease --title ...
  --notes-file notes.md --target "$GITHUB_SHA"`. Final cuts use `make_latest: true`. Never touch the
  `trailer-final-5` release.
- Write a job summary to `$GITHUB_STEP_SUMMARY` with the contact sheet link, per-shot timings and loudness stats.

```yaml
jobs:
  plan:    # outputs.matrix = JSON list of {shot, frames, est_min}
  build:   # compile tracer (ccache) -> upload-artifact tracer-bin; warm Blender cache
  render:
    needs: [plan, build]
    strategy: { fail-fast: false, max-parallel: 20, matrix: { job: "${{ fromJSON(needs.plan.outputs.matrix) }}" } }
    timeout-minutes: 330
    steps: [checkout, restore blender cache, download tracer-bin, "tls render --job ...", upload-artifact (if: always())]
  comp:    # per shot: download-artifact pattern: layers-<shot>-* merge-multiple: true -> graded frames
  assemble: # frames + audio mix -> ffmpeg (x264 -tune grain, CRF 14-16, AAC 320k), loudness check, contact sheet
  release:  # softprops/action-gh-release@v3, prerelease unless quality == final
```

### 5.5 Better free compute that runs from the repo without a human?

**Honest answer:** for fully automated CPU rendering, GitHub Actions on a **public** repo (80 free vCPUs in
parallel, unlimited minutes) is the best option available. The alternatives:

| Option | Automatable from a repo? | Notes |
|---|---|---|
| Modal (Starter) | **Yes**, once a human creates the account and API token (stored as a secret) | [$30 per month credits](https://modal.com/pricing), about 27 T4-GPU hours; per-second billing. GPU Cycles (OptiX) would be about 10–50× a runner for the ship layers. The only realistic GPU add-on |
| Kaggle | Partly: `kaggle kernels push` with a token; one-time phone verification | [30 GPU-h per week](https://www.kaggle.com/docs/efficient-gpu-usage), 9 h sessions. The terms target data science, so rendering is a grey area |
| Google Colab | **No** | needs an interactive browser session and forbids headless farming |
| Oracle Always Free A1 | Yes, as a self-hosted runner, after signup with a card | **Cut to 2 OCPU / 12 GB on 15 Jun 2026** ([InfoQ](https://www.infoq.com/news/2026/07/oracle-cloud-free-tier-limits/)) and often out of capacity. Not worth it |
| Azure Pipelines (public projects) | Yes, after a free-grant request form (unverified) | about 2 vCPU agents, fewer parallel jobs than GitHub Actions. No gain |
| SheepIt (community Blender farm) | No: web upload, points system, Blender only | cannot run our tracer |

---

## Sources (primary)
- James et al. 2015, DNGR: <https://arxiv.org/abs/1502.03808>
- Bruneton 2020: <https://arxiv.org/abs/2010.08735>, code <https://github.com/ebruneton/black_hole_shader>
- Neyret 2003, Advected Textures: <http://www-evasion.imag.fr/Publications/2003/Ney03/>
- NASA SVS: <https://svs.gsfc.nasa.gov/13326/>, <https://svs.gsfc.nasa.gov/14576>, <https://svs.gsfc.nasa.gov/14818>
- Johnson et al. 2020, photon ring: <https://www.osti.gov/pages/servlets/purl/1626057>
- Newson et al. 2017, grain: <https://www.ipol.im/pub/art/2017/192/>
- AgX: <https://developer.blender.org/docs/release_notes/4.0/color_management/>, <https://iolite-engine.com/blog_posts/minimal_agx_implementation>
- ACES 2: <https://docs.acescentral.com/background/about-rendering/>
- OIDN: <https://www.openimagedenoise.org/>
- GitHub Actions: <https://docs.github.com/en/actions/reference/limits>, <https://docs.github.com/en/actions/reference/runners/github-hosted-runners>, <https://docs.github.com/en/actions/reference/workflows-and-actions/dependency-caching>, <https://github.com/actions/upload-artifact>, <https://github.com/softprops/action-gh-release>, <https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases>
- Audio licensing: <https://space-audio.org/citation.html>, <https://chandra.harvard.edu/photo/image_use.html>, <https://www.voxengo.com/impulses/>

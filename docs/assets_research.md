# Asset research: THE LAST SIGNAL (90 s remake)

Verified from the Linux container on **2026-09-28**. For every URL below I checked that it
answers **HTTP 200 without login, cookies or API keys** (HEAD request or a small ranged GET).
Sizes are the `Content-Length` the server reported. Polycounts and texture sizes of GLB models
come from parsing each file's glTF JSON chunk. Nothing larger than about 25 MB was downloaded in
full, and all probe files have been deleted.

Legend: **PD** = public domain (US federal work), **CC0**, **CC BY** (credit required),
**⚠ NC/SA** = flagged licence problem.

---

## Top picks

| need | pick | licence | why |
|---|---|---|---|
| Hero ship | **Procedural Blender ship, kitbashed** from NASA 3D Resources parts: *Cassini Assembly* (RTGs, twin main engines, 4 m HGA, 454k tris), *Voyager Probe (B) (antenna)* dish, *Deep Space 1* / *Dawn* ion engines, *MRO (A)* modelled crinkled foil, *ISS (C) High Res* truss | PD (NASA) | No free model holds up from macro close-up to a speck. The NASA models are good mid-distance references and part donors. Build the hero procedurally and use these for proportions and parts. |
| MLI foil | **ambientCG `Foil002`** (gold, crinkled) + **`Foil001`** (silver) | CC0 | Real crinkled-foil normal and displacement maps. The best free MLI look I found. |
| Painted/worn metal | ambientCG `PaintedMetal002`, `Scratches001–005`, `SurfaceImperfections003`; Poly Haven `blue_metal_plate`, `metal_plate` | CC0 | Wear and breakup masks. |
| Brushed aluminium / gold | ambientCG `Metal009` / `Metal011` / `Metal012` (brushed), `Metal048B` (gold with fingerprints) | CC0 | |
| Carbon fibre | ambientCG `Fabric004` (carbon weave) | CC0 | The only CC0 carbon weave on either site. |
| Solar cells | ambientCG `SolarPanel001–004` | CC0 | Terrestrial mono-Si look (busbars). For space GaAs cells, re-tint and re-grid them procedurally. |
| Debris / asteroids | **Poly Haven `moon_rock_01…07`** models (≈18.6k tris, 2K PBR, lunar regolith) + `moon_meteor_01` texture; ambientCG `Rock035`, `Rock058` | CC0 | Scanned, space-appropriate rock. |
| Diffuse Milky Way | **NASA SVS Deep Star Maps 2020 `milkyway_2020_{8k,16k}_gal.exr`**: the map with the Hipparcos and Tycho stars *already removed* | PD (NASA SVS) | It is exactly complementary to an analytic star catalogue down to V≈11.5, so no star is drawn twice and no star-removal step is needed. |
| Point stars | **AT-HYG v4.0** (Tycho-2 + Gaia DR3 + Hipparcos + BSC; 2.55 M stars, V/VT magnitude + B−V `ci`), one gzip CSV of 199.7 MB, or its *m11* subset (875k stars, 70 MB) | ⚠ CC BY-SA 4.0 on the compilation; the underlying ESA data is **CC BY-NC 3.0 IGO** | Magnitude range and colours match what we need in a single file. For a licence-clean fallback, see §3. |
| Title font | **Jost** (already in repo), **Michroma**, **Cormorant Garamond** | OFL 1.1 | See §4. |
| Space audio | **space-audio.org / U. Iowa** Voyager 1 interstellar, Juno Waves, Cassini SKR; **NASA "Sounds from Beyond"** WAVs (Juno Ganymede 48 kHz stereo, InSight, Perseverance) | CC BY 4.0 (U. Iowa); PD (NASA) | Real plasma-wave and radio recordings. |
| Reverb IRs | **Synthesize the IR in `production/audio`** (noise × decay × filtered EQ). The real public-domain IRs are only small AAC files (Purnodes railway tunnel, St Lawrence church). | own / PD | OpenAIR's host is suspended, Freesound needs login, and the rest carry NC/SA terms. |

**Credit lines to add to `ASSETS.md` / `CREDITS.md`** (verbatim where the source prescribes one):

* NASA/Goddard Space Flight Center Scientific Visualization Studio. Gaia DR2: ESA/Gaia/DPAC.
* 3D models: NASA 3D Resources (https://github.com/nasa/NASA-3D-Resources).
* Textures: ambientCG.com (CC0), Poly Haven (CC0). Credit is optional but courteous.
* "Original space audio recordings provided courtesy of NASA and The University of Iowa. https://space-audio.org/" (CC BY 4.0)
* NASA/JPL-Caltech (plus the partner list printed next to each NASA sound, e.g. /SwRI/Univ. of Iowa, /LANL/CNES/CNRS/ISAE-Supaero).
* Star data: "This work has made use of data from the European Space Agency (ESA) mission Gaia (https://www.cosmos.esa.int/gaia), processed by the Gaia Data Processing and Analysis Consortium (DPAC)…"; Hipparcos/Tycho-2: ESA 1997, Høg et al. 2000; AT-HYG by David Nash / astronexus (CC BY-SA 4.0).

### Licence flags to decide on now

1. **ESA star catalogues (Hipparcos, Tycho-2, Gaia) are CC BY-NC 3.0 IGO.**
   * The CDS ReadMe files for I/239 and I/259 print `License: CC-BY-NC-3.0 IGO`.
   * The Gaia licence page says: "Gaia data are distributed under the CC BY-NC 3.0 IGO license."
   * Commercial use requires contacting `data.licences@esa.int`.
   * Every catalogue that reaches V≈11–12 with colour is built from this data, including AT-HYG.
   * **What this means:**
     * A non-commercial short on a non-monetised channel is fine with credit.
     * If the film will be sold or monetised, either ask ESA, or use the licence-clean route: NASA SVS maps (NASA declares them public domain) plus BSC5 for the bright stars.
   * Positions and magnitudes are facts, so US copyright is doubtful, but the EU database right and the licence terms still apply.
2. **AT-HYG is ShareAlike** (CC BY-SA 4.0). We would only ship rendered frames, never a redistributed catalogue, but if we commit a derived star binary to the repo, that file must be CC BY-SA.
3. **Chandra sonifications:** SAO asserts no copyright, but each one is co-credited to *SYSTEM Sounds (M. Russo, A. Santaguida)*. The policy says third parties "may claim copyright", so do not use them.
4. **OpenAIR IRs:** each IR has its own licence (PD, BY, BY-SA, BY-NC-SA, BY-NC-ND), and the original site is currently suspended.

---

## 1. Spacecraft 3D models

### 1a. Source availability (script-download without login?)

| source | scriptable? | licence | verdict |
|---|---|---|---|
| **NASA 3D Resources** (github.com/nasa/NASA-3D-Resources) | **Yes.** `https://raw.githubusercontent.com/nasa/NASA-3D-Resources/master/<url-encoded path>` returns 200 anonymously. No LFS. The repo is 1,199 files; do *not* clone it whole, fetch individual files. | README: "These assets are free and without copyright." Usage guidelines: https://www.nasa.gov/nasa-brand-center/images-and-media/ (no NASA insignia or implied endorsement) | Main source. Mostly glTF-binary (Blender 4.2 exporter), plus a few .blend/.7z/.fbx files. |
| nasa3d.arc.nasa.gov | Now points to science.nasa.gov/3d-resources/, which is the same assets as the GitHub repo | PD | Use the GitHub raw URLs. |
| Smithsonian Open Access 3D (3d.si.edu) | **No.** 3d.si.edu returned 403 to curl from this container, and the Open Access API needs an api.data.gov key. | CC0 | Not usable in CI without a key. Skip. |
| Sketchfab | **No.** The download API needs an OAuth token (`/v3/models/{uid}/download` returns 401); the web download needs login. | varies | Not usable. |
| Blend Swap | **No.** Download needs a free account; scripted request got 403. | CC0 / CC BY per model | Not usable in CI. |
| OpenGameArt | Yes, direct links | CC0/CC BY/GPL per item | Spacecraft there are low-poly game assets, not film quality. Not worth it. |
| Poly Haven models | Yes (API + dl.polyhaven.org CDN) | CC0 | No spacecraft, but **excellent rocks** (§2). |

### 1b. NASA 3D Resources: evaluated candidates

Direct URL = `https://raw.githubusercontent.com/nasa/NASA-3D-Resources/master/3D%20Models/` + the path below.
Encode spaces as `%20`. Parentheses can stay literal. All return HTTP/2 200.
tris = triangles; tex = embedded textures (max resolution).

| model | path (after `3D%20Models/`) | size | geometry / textures | quality verdict | recommended use |
|---|---|---|---|---|---|
| Cassini Assembly | `Cassini%20Assembly/Cassini%20Assembly.glb` | 2.4 MB | **454k tris**, 13 meshes, 8 mats, untextured | Engineering-grade detail: 3 RTGs, twin main engines, 4 m HGA, struts, tanks. Materials are flat. | **Kitbash donor #1**: RTG, engine bells, HGA, propulsion module. Re-shade with our foil and paint. |
| Cassini-Huygens (A) | `Cassini-Huygens%20(A)/Cassini-Huygens%20(A).glb` | 1.7 MB | 26k tris, 6 tex (≤1K, some webp) | Nice gold-foil read at medium distance, soft up close | Proportion and colour reference; mid/far shots |
| Voyager Probe (B) | `Voyager%20Probe%20(B)/Voyager%20Probe%20(B).glb` | 1.7 MB | 20k tris, 4 tex (1K) | Clean, correct silhouette (dish, bus, magnetometer boom, RTG boom) | Far/medium stand-in; silhouette reference |
| Voyager Probe (B) antenna | `Voyager%20Probe%20(B)/Voyager%20Probe%20(B)%20(antenna).glb` | 0.2 MB | 15k tris, 73 meshes | Separate HGA with feed and struts | **Kitbash**: 3.7 m dish (add subdivision and a panel-seam normal map) |
| Voyager Probe (A) | `Voyager%20Probe%20(A)/Voyager%20Probe%20(A).glb` | 0.3 MB | 30k tris, 16 mats, untextured | Decent modelling, flat materials | Alternate Voyager parts |
| Juno (A) | `Juno%20(A)/Juno%20(A).glb` | 9.0 MB | 17k tris, 14 tex (up to 2K) | Good textured arrays and vault | Solar-wing reference |
| Deep Space 1 | `Deep%20Space%201/Deep%20Space%201.glb` | 0.9 MB | 13.8k tris, 8 tex (≤1K) | Low detail | **Ion engine** (NSTAR) proportions for the blue-glow thruster |
| Dawn | `Dawn/Dawn.glb` | 0.9 MB | 32k tris, 6 tex | Medium | Ion engines ×3, gimbal; array reference |
| Mars Reconnaissance Orbiter (A) | `Mars%20Reconnaissance%20Orbiter%20(MRO)%20(A)/Mars%20Reconnaissance%20Orbiter%20(MRO)%20(A).glb` | 2.7 MB | 124k tris, 1.6K tex | **Crinkled gold MLI modelled as geometry**; big dish | Study or steal the foil geometry; 3 m dish |
| Parker Solar Probe | `Parker%20Solar%20Probe/Parker%20Solar%20Probe.glb` | 0.4 MB | 39k tris, 2K tex | Good heat-shield form | Heat-shield / sun-shade part |
| James Webb (A) | `James%20Webb%20Space%20Telescope%20(A)/James%20Webb%20Space%20Telescope%20(A).glb` (+ `.7z` 66 MB) | 4.7 MB | **494k tris**, 1,600 meshes, untextured | Very detailed struts and hinges | Truss, strut and hinge greebles |
| ISS (C) High Res | `International%20Space%20Station%20(ISS)%20(C)%20(High%20Res)/International%20Space%20Station%20(ISS)%20(C)%20(High%20Res).7z` | 24.8 MB | .7z (needs `py7zr`/`7z`) | High-res | **Truss segments, radiators**, handrails |
| DSN 34-meter | `Deep%20Space%20Network%2034-meter/Deep%20Space%20Network%2034-meter.glb` | 2.9 MB | 32k tris, 10 tex (1K) | Good backstructure truss | Dish backstructure / rib pattern |
| 70-meter Dish | `70-meter%20Dish/70%20meter%20dish.glb` | 2.2 MB | 15k tris, 1.6K tex | OK | Dish reference |
| Rosetta | `Rosetta/Rosetta.glb` | 2.3 MB | 17k tris, 10 tex | Medium | Array/bus reference |
| Galileo | `Galileo/Galileo.glb` | 0.2 MB | 13k tris, flat colours | **Poor** (toy-like) | Skip |
| MAVEN (A) | `Mars%20Atmosphere%20and%20Volatile%20EvolutioN%20(MAVEN)%20(A)/Mars%20Atmosphere%20and%20Volatile%20EvolutioN%20(MAVEN)%20(A).glb` | 10.5 MB | 1.75M tris, single mesh, untextured | 3D-print-style mesh | Skip |
| Satellite Kit (body/radio/wings 1–3) | `Satellite%20Kit/Satellite%20Kit%20radio%201.glb` etc. | <50 KB each | 200–750 tris | Far too low-poly | Skip |
| InSight Cruise Stage | `InSight%20Cruise%20Stage/InSight%20Cruise%20Stage.blend` | 6.1 MB | .blend | not inspected | Cruise-stage thrusters/arrays if needed |

**Honest verdict.** None of these models survives a macro close-up:

* texture budgets are 1–2K;
* the MLI is either a texture or coarse geometry;
* there are no bolt-level greebles;
* materials are often flat.

They are still correct and PD, so they are ideal as proportion references and part donors. Plan:

* Build the hero hull procedurally in Blender Python: bus, MLI blankets with displacement from `Foil002`, bevelled panels and seam lines.
* Import NASA parts for the dish, RTG, engine and truss, then retopologise or subdivide and re-shade them.
* Add a procedural greeble pass for the macro shots.

**Missing from the repo:** New Horizons (the best RTG-probe look). Use Cassini's RTGs instead.

Other NASA texture assets in the same repo (`Images and Textures/`, PD):

* Phobos and Deimos maps: albedo for asteroid debris.
* Hipparcos, Tycho and Yale bright-star maps (older equivalents of the SVS maps).

---

## 2. PBR textures (CC0)

### 2a. ambientCG

* **Licence:** CC0 1.0: "All ambientCG assets are provided under the Creative Commons CC0 1.0 Universal License." (https://docs.ambientcg.com/license/)
* **API:** `https://ambientcg.com/api/v2/full_json?id=<ID>&include=downloadData` (no key).
* **Direct 2K download pattern:** `https://ambientcg.com/get?file=<ID>_2K-JPG.zip`. This returns a 302 to `acg-download.struffelproductions.com/...` and then 200 `application/zip`. Swap `2K-JPG` for `2K-PNG` to get 16-bit PNG maps.
* **Zip contents (verified for Foil002):** `_Color`, `_NormalGL`, `_NormalDX`, `_Roughness`, `_Metalness`, `_Displacement`, `_AmbientOcclusion` (JPG), plus `.blend`, `.mtlx` and `.usdc`.
* **Transient failures:** this container saw two connection resets to ambientcg.com during the session, so the fetch script should retry.

| ID | what it is (checked on preview renders) | 2K-JPG zip | 2K-PNG | verdict / use |
|---|---|---|---|---|
| **Foil002** | Crinkled **gold** foil | [Foil002_2K-JPG.zip](https://ambientcg.com/get?file=Foil002_2K-JPG.zip), 22.8 MB | 56.7 MB | **Best MLI.** Kapton/gold blankets |
| **Foil001** | Crinkled silver/aluminium foil, bold creases | [Foil001_2K-JPG.zip](https://ambientcg.com/get?file=Foil001_2K-JPG.zip), 20.1 MB | 54.8 MB | Silver MLI (Voyager-style bus) |
| Foil003 | Silver foil, softer creases | [Foil003_2K-JPG.zip](https://ambientcg.com/get?file=Foil003_2K-JPG.zip), 16.9 MB | 51.6 MB | Variation / tight blanket areas |
| Metal009 | Brushed steel, scratches | [Metal009_2K-JPG.zip](https://ambientcg.com/get?file=Metal009_2K-JPG.zip), 16.7 MB | 50.1 MB | Brushed aluminium (tint) |
| Metal011 / Metal012 | Brushed metal (012 is near-mirror) | [Metal011](https://ambientcg.com/get?file=Metal011_2K-JPG.zip) 15.0 MB, [Metal012](https://ambientcg.com/get?file=Metal012_2K-JPG.zip) 12.9 MB | 49.2 / 45.6 MB | Machined parts, dish feed |
| Metal048B | Gold, fingerprints / dirt | [Metal048B_2K-JPG.zip](https://ambientcg.com/get?file=Metal048B_2K-JPG.zip), 8.9 MB | 38.4 MB | Gold-plated fittings |
| Metal048A / Metal042A / Metal034 | Clean gold variants | [048A](https://ambientcg.com/get?file=Metal048A_2K-JPG.zip) 6.4 MB · [042A](https://ambientcg.com/get?file=Metal042A_2K-JPG.zip) 9.4 MB · [034](https://ambientcg.com/get?file=Metal034_2K-JPG.zip) 8.8 MB | | Anodised-gold look (no true "anodized" set exists; tint these) |
| **PaintedMetal002** | Blue paint, chipped and scratched | [PaintedMetal002_2K-JPG.zip](https://ambientcg.com/get?file=PaintedMetal002_2K-JPG.zip), 28.5 MB | 59.5 MB | Worn painted hull (re-tint to white/grey) |
| PaintedMetal001 | Yellow paint, scratched | [PaintedMetal001_2K-JPG.zip](https://ambientcg.com/get?file=PaintedMetal001_2K-JPG.zip), 29.0 MB | 61.6 MB | Warning-stripe parts |
| PaintedMetal004 / 009 | Red paint / rusted paint | [004](https://ambientcg.com/get?file=PaintedMetal004_2K-JPG.zip) 25.7 MB · [009](https://ambientcg.com/get?file=PaintedMetal009_2K-JPG.zip) 35.2 MB | | 009 is too terrestrial (rust), avoid |
| **Scratches001–005** | Scratch masks | [001](https://ambientcg.com/get?file=Scratches001_2K-JPG.zip) 19.6 · [002](https://ambientcg.com/get?file=Scratches002_2K-JPG.zip) 13.4 · [003](https://ambientcg.com/get?file=Scratches003_2K-JPG.zip) 18.6 · [004](https://ambientcg.com/get?file=Scratches004_2K-JPG.zip) 22.1 · [005](https://ambientcg.com/get?file=Scratches005_2K-JPG.zip) 22.9 MB | | Roughness breakup, micro-scratch anisotropy |
| SurfaceImperfections003 (also 001–020) | Smudges / smears | [SurfaceImperfections003_2K-JPG.zip](https://ambientcg.com/get?file=SurfaceImperfections003_2K-JPG.zip), 18.9 MB | 48.2 MB | Roughness grime; macro-shot realism |
| Fingerprints001–009, Smear001–008 | Decal masks | same pattern | | Lens-side grime / macro realism (use sparingly) |
| **Fabric004** | Black **carbon-fibre** weave | [Fabric004_2K-JPG.zip](https://ambientcg.com/get?file=Fabric004_2K-JPG.zip), 6.3 MB | 5.2 MB | Booms, struts, dish back |
| SolarPanel001–004 | Mono-Si solar cells with busbars | [001](https://ambientcg.com/get?file=SolarPanel001_2K-JPG.zip) 15.4 · [002](https://ambientcg.com/get?file=SolarPanel002_2K-JPG.zip) 15.7 · [003](https://ambientcg.com/get?file=SolarPanel003_2K-JPG.zip) 12.4 · [004](https://ambientcg.com/get?file=SolarPanel004_2K-JPG.zip) 14.9 MB | ~30 MB | Usable, but the terrestrial busbar grid is wrong for spacecraft GaAs cells. Use as a base and add a procedural cell grid. |
| MetalPlates006 | Overlapping metal tiles | [MetalPlates006_2K-JPG.zip](https://ambientcg.com/get?file=MetalPlates006_2K-JPG.zip), 13.1 MB | | Probably too stylised; optional |
| SheetMetal001 | Perforated sheet | [SheetMetal001_2K-JPG.zip](https://ambientcg.com/get?file=SheetMetal001_2K-JPG.zip), 15.7 MB | | Radiator / vent grilles |
| DiamondPlate001–009 | Tread plate | same pattern | | Not spacecraft-like; skip |
| Rock035 | Dark grey-black cave rock | [Rock035_2K-JPG.zip](https://ambientcg.com/get?file=Rock035_2K-JPG.zip), 33.0 MB | 67.7 MB | **Carbonaceous asteroid** look |
| Rock058 | Grey fractured rock | [Rock058_2K-JPG.zip](https://ambientcg.com/get?file=Rock058_2K-JPG.zip), 27.1 MB | 63.0 MB | Stony asteroid debris |
| Rock030 / Rock051 | Grey cliff rock | [030](https://ambientcg.com/get?file=Rock030_2K-JPG.zip) 33.5 · [051](https://ambientcg.com/get?file=Rock051_2K-JPG.zip) 30.4 MB | | Debris variation |

### 2b. Poly Haven

* **Licence:** CC0: "You do not need to give credit or attribution when using them" (https://polyhaven.com/license).
* **API terms** (https://github.com/Poly-Haven/Public-API/blob/master/ToS.md): free for any use, but "all API calls must be made with a unique Referer header or user-agent that matches your software name". Set `User-Agent: TheLastSignal-fetch/1.0`.
* **The API is only needed for discovery.** File URLs are static on the CDN:
  * Texture maps: `https://dl.polyhaven.org/file/ph-assets/Textures/{jpg|png|exr}/2k/<id>/<id>_<map>_2k.<ext>`
    * `<map>` is one of `diff`, `nor_gl`, `rough`, `disp`, `arm` (AO/rough/metal packed), `metal` where present.
  * Blender materials: `https://dl.polyhaven.org/file/ph-assets/Textures/blend/2k/<id>/<id>_2k.blend`
  * Models: `https://dl.polyhaven.org/file/ph-assets/Models/gltf/2k/<id>/<id>_2k.gltf`, plus the `.bin` and `textures/*` files listed under `include` in `https://api.polyhaven.com/files/<id>`.
  * Models as .blend: `.../Models/blend/2k/<id>/<id>_2k.blend`.
* Verified: `blue_metal_plate_diff_2k.jpg` returns HTTP/2 200 with 1,518,621 bytes.
* **Poly Haven has no foil, aluminium, carbon or solar textures.** For those, use ambientCG.

| ID | type | 2K sizes (from API) | verdict / use |
|---|---|---|---|
| `blue_metal_plate` | Painted steel, scratched and scuffed (Rob Tuytel, 2024) | diff 1.5 MB jpg / 3.2 MB exr; nor_gl 0.9 MB; rough 1.6 MB; arm 1.6 MB | **Good painted-hull base**; re-tint |
| `metal_plate` | Bare/painted steel plate with rust, with a metal map | diff 2.7 MB; nor_gl 2.5 MB; rough 3.0 MB; metal 3.4 MB | Worn structural plates (tone down the rust) |
| `painted_metal_shutter` | Scratched painted corrugated metal | – | Optional |
| `moon_meteor_01`, `moon_meteor_02` | Lunar regolith with craters, 16K max | diff 1.2 MB jpg; nor_gl 4.7 MB; disp 0.76 MB | **Asteroid surface** |
| `moon_01…04`, `moon_dusted_01…05`, `moon_macro_01`, `moon_flat_macro_01/02` | Regolith | similar | Dusty debris |
| `rock_face`, `rock_surface`, `dark_rock_02`, `rock_boulder_cracked` | Rock | similar | Debris variation |
| **Model** `moon_rock_01` … `moon_rock_07` | Scanned lunar rocks, **≈18.5k tris**, 2K diff/nor/rough | gltf set ≈4.7 MB (01), blend ≈13.9 MB | **Best debris/asteroid meshes.** Instance and scale them |
| Model `boulder_01`, `namaqualand_boulder_02…06`, `rock_07`, `rock_09`, `stone_01` | Scanned rocks | – | More debris variety (check each for moss or lichen) |

---

## 3. Star catalogues and sky maps

### 3a. NASA SVS "Deep Star Maps 2020" (svs.gsfc.nasa.gov/4851)

* **Licence:** SVS FAQ (https://svs.gsfc.nasa.gov/help/): "All of our content is in the public domain (unless otherwise noted)."
* **Required credit (from the page):** "NASA/Goddard Space Flight Center Scientific Visualization Studio. Gaia DR2: ESA/Gaia/DPAC."
* **How the maps were built:** plotted from **1.7 billion stars** in Hipparcos-2, Tycho-2 and Gaia DR2 (plus BSC, UCAC3 and XHIP).
  * Hipparcos covers V<8, Tycho-2 covers V 8–11.5, and Gaia covers the rest.
  * Colours come from B−V through Ballesteros T_eff and Charity's blackbody RGB.
  * The Gaia DR2 holes were filled with UCAC3.
* **Format:** OpenEXR half-float, linear, plate carrée. `_gal` files are galactic coordinates (re-issued 2021-01-04 with the correct transform); files without it are ICRF/J2000.
* **Base URL:** `https://svs.gsfc.nasa.gov/vis/a000000/a004800/a004851/<file>`. All 30 files return 200.

| variant | contents | 4k (4096×2048) | 8k | 16k | 32k | 64k |
|---|---|---|---|---|---|---|
| `starmap_2020_<res>.exr` | everything | 36.0 MB | 130.5 MB | 443.5 MB | 1,535 MB | 4,035 MB |
| `starmap_2020_<res>_gal.exr` | everything, galactic | 40.6 MB | 160.7 MB | 384.2 MB | 1,279 MB | 3,287 MB |
| **`milkyway_2020_<res>.exr`** | **Milky Way background; Hipparcos + Tycho stars omitted** | 36.4 MB | 137.3 MB | 434.0 MB | 1,510 MB | 3,952 MB |
| **`milkyway_2020_<res>_gal.exr`** | same, galactic | 34.8 MB | **125.1 MB** | **373.8 MB** | 1,252 MB | 3,206 MB |
| `hiptyc_2020_<res>.exr` | **bright stars only** (Hipparcos + Tycho foreground) | 21.3 MB | 50.6 MB | 71.3 MB | 138.5 MB | 248.0 MB |
| `hiptyc_2020_<res>_gal.exr` | same, galactic | 19.0 MB | 45.3 MB | 64.1 MB | 125.8 MB | 225.7 MB |

The page also has constellation bounds/figures and a celestial grid as TIFFs, plus 4k print JPGs and a tour MP4. Sizes above are bytes/10⁶ from `Content-Length`.

**Recommendation.** Replace the current `starmap_2020_8k_gal` + point-source-removal step with **`milkyway_2020_16k_gal.exr`** (373.8 MB), or the 8k file (125 MB) for drafts.

* NASA already removed every Hipparcos/Tycho star (≈ V<11.5), so the analytic catalogue stars below slot in with no double counting.
* A 1080p frame at 40–60° FOV needs roughly 11–17k px around 360°, so 16k is the right resolution for the final.
* `hiptyc_2020_*` is a good ground-truth image to check our analytic star colours and brightness against.

Related: SVS 4856 "An Elsewhere Starfield" (not evaluated).

### 3b. Catalogues

| catalogue | direct URL(s) | size | stars / depth | columns needed | licence (exact) | verdict |
|---|---|---|---|---|---|---|
| **AT-HYG v4.0** (Augmented Tycho-HYG) | Full: `https://codeberg.org/astronexus/athyg/media/branch/main/data/athyg_40.csv.gz` · m11 subset: `…/data/subsets/athyg_40_reduced_m11.csv.gz` · m10: `…/athyg_40_reduced_m10.csv.gz` (use `/media/`: `/raw/` returns the 134-byte LFS pointer) | **199.7 MB** gz · m11 **70.1 MB** · m10 27.6 MB | **~2.55 M** (Tycho-2 complete to V≈11, mostly to 11.5) · m11 = 875,292 · m10 = 332,178 | `ra` (HYG convention: hours; verify), `dec` (deg), `mag` (V or VT), `ci` (B−V), `dist`, `proper`, `hip` | "This work is licensed under a Creative Commons Attribution-ShareAlike 4.0 International License" (v3.0+), [LICENSE](https://codeberg.org/astronexus/athyg/src/branch/main/LICENSE). ⚠ SA; underlying ESA data NC | **Primary pick.** One file, colours included, Gaia distances as a bonus. Header verified via ranged GET. |
| **Tycho-2** (CDS I/259) | `https://cdsarc.cds.unistra.fr/ftp/I/259/tyc2.dat.00.gz` … `tyc2.dat.19.gz` (20 parts) + `suppl_1.dat.gz` (0.67 MB, the bright stars Tycho-2 lacks) + [ReadMe](https://cdsarc.cds.unistra.fr/ftp/I/259/ReadMe) | 166.6 MB total gz | 2,539,913 stars, VT ≲ 12 | fixed-width: `RAmdeg` 16–27, `DEmdeg` 29–40, `BTmag` 111–116, `VTmag` 124–129. V = VT − 0.090(BT−VT); B−V = 0.850(BT−VT) | ReadMe: **`License: CC-BY-NC-3.0 IGO`** ⚠ | Catalogue of record; use if we want to own the build. Some brightest stars are missing, so merge with Hipparcos. |
| **Hipparcos** (CDS I/239, original) | `https://cdsarc.cds.unistra.fr/ftp/I/239/hip_main.dat` (no .gz on the server) | 53.3 MB | 118,218 stars | `Vmag` 42–46, `RAdeg` 52–63, `DEdeg` 65–76, `B-V` 246–251 | ReadMe: **`License: CC-BY-NC-3.0 IGO`** ⚠ | Bright-star layer (V<~7) for merging with Tycho-2 or Gaia |
| Hipparcos-2 (CDS I/311, van Leeuwen 2007) | `https://cdsarc.cds.unistra.fr/ftp/I/311/hip2.dat.gz` | 9.0 MB | 117,955 | `RArad`, `DErad` (radians), `Hpmag`, `B-V`, `V-I` (**no V**) | No licence line in ReadMe; ESA mission data, so treat as NC | Better astrometry, but Hp, not V |
| **Yale Bright Star Catalogue 5** (CDS V/50) | `https://cdsarc.cds.unistra.fr/ftp/V/50/catalog.gz` | 0.57 MB | 9,110 entries, V ≤ 6.5 | `RAh/RAm/RAs` 76–83, `DE-/DEd/DEm/DEs` 84–90 (J2000), `Vmag` 103–107, `B-V` 110–114 | No licence statement in the ReadMe (Hoffleit & Warren 1991, NASA ADC). Factual data; cite it. **Lowest-risk option** | Naked-eye stars only; the licence-clean route when paired with SVS maps |
| **Gaia DR3** via ESA TAP (anonymous) | `https://gea.esac.esa.int/tap-server/tap/sync` with `REQUEST=doQuery&LANG=ADQL&FORMAT=csv&QUERY=SELECT source_id,ra,dec,phot_g_mean_mag,bp_rp FROM gaiadr3.gaia_source WHERE phot_g_mean_mag<12 AND ra>=0 AND ra<10` (loop ra in 10° chunks) | ~4.1 MB CSV per 10° chunk (54k rows, **~15 s**); ~250 MB total | **3,087,821** with G<12 (3,083,983 with BP−RP); 1,247,240 with G<11 | `ra`, `dec`, `phot_g_mean_mag`, `bp_rp` | "Gaia data are distributed under the CC BY-NC 3.0 IGO license" ([cosmos.esa.int/web/gaia-users/license](https://www.cosmos.esa.int/web/gaia-users/license)); commercial use requires contacting data.licences@esa.int ⚠ | Best photometry and colours, but saturates for G ≲ 6: merge with Hipparcos or BSC for bright stars. A live service, so cache the result and don't query in every CI run. |

**Recommended starfield build (1–3 M stars to mag ~11.5–12, real colours):**

1. **Default: AT-HYG v4.0 full** (2.55 M stars, `mag` + `ci`=B−V).
   * `production/tools/` fetches the 199.7 MB gzip once.
   * It converts to a packed float32 array `(ra_rad, dec_rad, V, B−V)` of about 40 MB, cached with `actions/cache` or a release asset.
   * B−V maps to T_eff (Ballesteros) and then to a blackbody RGB through the existing CIE LUT.
   * The m11 subset (70 MB, 875k stars) is the draft/CI-fast option.
2. **Background:** SVS `milkyway_2020_16k_gal.exr`. It has no Hip/Tycho stars, so it complements (1) exactly.
3. **Licence-clean alternative** if the film is to be monetised without asking ESA: BSC5 (9,110 analytic stars ≤ V6.5) + SVS `milkyway_2020` + SVS `hiptyc_2020` (both PD NASA imagery) for everything fainter.
4. **Deeper or more precise colours:** Gaia DR3 TAP G<12 (3.09 M, BP−RP), merged with Hipparcos for G<6. Same NC licence as (1).

HEASARC and CDS also mirror these. UCAC4 (USNO, I/322A) is a US-government catalogue with APASS B/V, but it is ~10 GB and weak for bright stars, so I did not pursue it.

---

## 4. Title-card fonts

* **Source:** github.com/google/fonts. Raw URL pattern: `https://raw.githubusercontent.com/google/fonts/main/ofl/<family>/<file>`; encode `[`/`]` as `%5B`/`%5D`.
* **Licence check:** each family's `METADATA.pb` says `license: "OFL"`, and its `OFL.txt` begins "This Font Software is licensed under the SIL Open Font License, Version 1.1."
* **Title cards are fine under OFL.** It permits any use, including commercial video. Only modified fonts can't reuse Reserved Font Names, and rendering text into frames is not font redistribution.

### Recommended 3

| # | family | direct download (verified 200) | size | OFL | why |
|---|---|---|---|---|---|
| 1 | **Jost** (variable wght 100–900; Owen Earl / indestructible type*) | `https://raw.githubusercontent.com/google/fonts/main/ofl/jost/Jost%5Bwght%5D.ttf` · [OFL.txt](https://raw.githubusercontent.com/google/fonts/main/ofl/jost/OFL.txt) | 135 KB | "Copyright 2020 The Jost Project Authors… licensed under the SIL Open Font License, Version 1.1." | Futura lineage. Wide-tracked ExtraLight/Light caps are the *Interstellar* / *Ad Astra* / *Arrival* trailer vocabulary: restrained and expensive-looking. Already in the repo, so the remake keeps continuity. **Main title + cards.** |
| 2 | **Michroma** (single weight; Vernon Adams) | `https://raw.githubusercontent.com/google/fonts/main/ofl/michroma/Michroma-Regular.ttf` · [OFL.txt](https://raw.githubusercontent.com/google/fonts/main/ofl/michroma/OFL.txt) | 64 KB | "Copyright 2011 The Michroma Project Authors… SIL Open Font License, Version 1.1." | Eurostile-Extended-style wide caps: the *Blade Runner 2049* / *Dune* register. Use small and heavily tracked, never glowing; the single weight keeps it disciplined. **Alternative title treatment.** (Syncopate is similar but Apache-2.0, at `apache/syncopate/Syncopate-Regular.ttf`, 174 KB.) |
| 3 | **Cormorant Garamond** (variable wght 300–700; Christian Thalmann) | `https://raw.githubusercontent.com/google/fonts/main/ofl/cormorantgaramond/CormorantGaramond%5Bwght%5D.ttf` · [OFL.txt](https://raw.githubusercontent.com/google/fonts/main/ofl/cormorantgaramond/OFL.txt) | 1.2 MB | "Copyright 2015 the Cormorant Project Authors… SIL Open Font License, Version 1.1." | High-contrast display Garamond in Light, a literary serif counterpoint for tagline cards ("FROM WHERE NOTHING ESCAPES") and end credits. Avoids sci-fi cliché. **Taglines/credits** paired with Jost. |

Runners-up (all verified 200, OFL):

* **Tenor Sans** (`ofl/tenorsans/TenorSans-Regular.ttf`, 132 KB). Optima-like humanist. Its OFL.txt declares Reserved Font Names "Tenor" and "Tenor Sans", which only matters if we modify and redistribute the font.
* **Josefin Sans** (`ofl/josefinsans/JosefinSans%5Bwght%5D.ttf`, 119 KB). 1920s geometric.
* **Manrope** (165 KB) and **Inter Tight** (582 KB). Good for small credits.

Rejected:

* Orbitron, Oxanium, Exo 2, Bai Jamjuree, Chakra Petch, Saira: gamer/"tech" cliché.
* Cinzel, Marcellus: Roman/fantasy.
* Montserrat, Raleway: over-used web faces.
* Space Grotesk, Sora: UI faces.
* Big Shoulders, Unica One: condensed poster faces, off-tone.

---

## 5. Audio

### 5a. Space recordings

**Licences:**

* **U. Iowa / space-audio.org:** "The audio files found at this site are available under a Creative Commons Attribution 4.0 International License" (https://space-audio.org/citation.html). The preferred credit is "Original space audio recordings provided courtesy of NASA and The University of Iowa. https://space-audio.org/". Commercial and artistic use are explicitly permitted.
* **NASA.gov files:** NASA media guidelines (PD, credit NASA and the listed partners).
* **Perseverance SuperCam clips:** credited to NASA/JPL-Caltech/LANL/CNES/CNRS/ISAE-Supaero, which includes non-US-government partners, so keep the full credit.

| recording | direct URL | format / size | licence | quality verdict | use |
|---|---|---|---|---|---|
| **Voyager 1 PWS: interstellar plasma oscillations** (Oct–Nov 2012, Apr–May 2013) | `https://space.physics.uiowa.edu/plasma-wave/plasma-wave/voyager/v1pws_interstellar_epo.mp4` | MP4 (extract audio with ffmpeg), 2.7 MB | CC BY 4.0 under space-audio.org's citation terms. This EPO page has no licence line of its own; the 2014 interstellar page (`…/voyager/v1pws_interstellar_2014.html`, YouTube-only) links the licence. Credit NASA/Univ. of Iowa | The iconic rising tone. Short, and the audio has been through video compression | **"The signal"** motif source; pitch/granular processing |
| Voyager 1: complete Jupiter encounter day (1979-03-05) | `https://space.physics.uiowa.edu/plasma-wave/voyager/V1PWS_Jupiter_1979-03-05T0000-2359.mp3` (the `space.physics.uiowa.edu/voyager/…` URL 301-redirects here) | MP3, **127.9 MB** | CC BY 4.0 | Long; rich textures | Bed textures, ambience layers |
| **Juno Waves: Ganymede flyby** (2021-06-07) | `https://www.nasa.gov/wp-content/uploads/2024/05/e2-wave-ganymede-flyby-compressed.wav` | **WAV 48 kHz / 16-bit / stereo**, 9.4 MB | PD (NASA/JPL-Caltech/SwRI/Univ. of Iowa) | Best-quality file found; eerie sweep with a mid-point jump | **Hero sound for approaching the anomaly** |
| Juno Waves: Europa flyby (2022-09-29) | `https://space.physics.uiowa.edu/plasma-wave/juno/audio/202209/jno-E45-LFRH-22-272-0836-1006-1st-try-Matlab-modified.wav` (+ `.mp3`) | WAV, 147 KB | CC BY 4.0 | Short | Accent |
| Juno Waves: bKOM Jupiter radio | `https://space.physics.uiowa.edu/plasma-wave/juno/audio/201608/jno-bkom-16-240.wav` | WAV, 302 KB | CC BY 4.0 | Short, tonal | Signal texture |
| Juno Waves: PJ4 plasma frequency (slow) | `https://space.physics.uiowa.edu/plasma-wave/juno/audio/201702/jno-PJ4-Elo-17-033-1248-1250-slow.wav` | WAV, 1.48 MB | CC BY 4.0 | Good | Drone layer |
| Juno Waves: crossing Jupiter's bow shock | `https://space.physics.uiowa.edu/plasma-wave/juno/audio/201606/jno-bshock-16-176-0700-0900-blk.mp3` | MP3, 264 KB | CC BY 4.0 | Noisy / turbulent | Transition whoosh |
| **Cassini RPWS: Saturn kilometric radiation** | `https://space-audio.org/cassini/SKR1/SKR-03-324.wav` · `https://space-audio.org/cassini/SKR2/casskrtrig04207a.wav` | WAV, 735 KB · 130 KB | CC BY 4.0 | Classic chirps/whistles | Signal interference |
| Selected sounds (D. Gurnett): chorus | `https://space.physics.uiowa.edu/~dag/chorus.wav` · `https://space.physics.uiowa.edu/~dag/8402916.wav` | WAV, 2.74 MB · 1.51 MB | CC BY 4.0 (space-audio.org) | Dawn chorus ("birdsong"); one connection reset seen, retry | Organic texture |
| **InSight SEIS: Martian wind** (pitched up 2 octaves) | `https://www.nasa.gov/wp-content/uploads/2015/01/08-Brian-Cook_raw_velocity_0.6_normalisedx1_2octavesUp_03.wav` | WAV, 647 KB | PD (NASA/JPL-Caltech/CNES/IPGP) | Low rumble | Sub-bass wind bed |
| InSight: pressure-sensor wind ×100 | `https://www.nasa.gov/wp-content/uploads/2015/01/07-Mars_sound1a_20s_x100.wav` | WAV, **8 KB** | PD | ⚠ Only 8 KB: probably truncated. Don't rely on it | – |
| InSight raw SEIS (48 kHz resample) | `https://www.nasa.gov/wp-content/uploads/2015/01/06-MASTERRESAMPLED-48Kraw_velocity_0.6_normalisedx1.wav` | WAV, **269.9 MB** (over our 200 MB probe limit, not downloaded) | PD | Long raw take | Optional |
| InSight marsquake sonification (Sol 173) | `https://www.nasa.gov/wp-content/uploads/2015/01/Quake-Sol-173.wav` | WAV, 13.7 MB | PD | Deep thud/rumble | Impact / low-end hits |
| Perseverance: Jezero ambience, rover noise filtered | `https://www.nasa.gov/wp-content/uploads/2024/05/sounds-from-mars-filters-out-rover-self-noise.wav` | WAV, 3.5 MB | PD (NASA/JPL-Caltech) | Real air sound; not "space" | Probably unused |
| Parker Solar Probe FIELDS "Sounds of the Solar Wind" (whistler, Langmuir, dust) | Only on JHU APL SoundCloud (`soundcloud.com/jhu-apl/…`) | – | NASA/JHU APL | ⚠ **No login-free direct file** (SoundCloud download needs an account) | Not usable in CI |
| Chandra black-hole sonification, Perseus cluster (2022) | `https://chandra.harvard.edu/photo/2022/sonify5/sonify5_perseus.mp4` | MP4, 24.8 MB | ⚠ SAO "no claim to copyright… may be used in accordance with NASA guidelines", **but** credited to "NASA/CXC/SAO/K.Arcand, SYSTEM Sounds (M. Russo, A. Santaguida)". Policy says third parties "may claim copyright" | Famous, but it's an artistic composition | **Avoid**; reference only |

More NASA WAVs (all PD, verified present on https://www.nasa.gov/sounds-from-beyond/ under `https://www.nasa.gov/wp-content/uploads/2024/05/…` and `…/2015/01/…`):

* Ingenuity flight (`jpl-20210506-listen-to-nasas-ingenuity-helicopter-as-it-flies-on-mars.wav`)
* dust devil (`em-0346-edlc-mic-gdrt-session-34.wav`)
* SuperCam mic (`scam-mic-sol001/004/012-run001.wav`)
* InSight "dinks and donks" (`Cropped-Dinks-and-Donks-sample.wav`)
* quakes (`Quake-Sol-235.wav`, `20190819-Sol-98-SEIS-Spatialized-reflective.wav`)

### 5b. Impulse responses for convolution reverb

| source | URL | format / size | licence | verdict |
|---|---|---|---|---|
| **Synthesized IR (recommended)** | generate in `production/audio` (e.g., stereo decorrelated noise × exp decay, RT60 3–12 s, frequency-dependent damping, pre-delay) | – | ours (MIT) | Licence-free, tunable, reproducible. The existing audio pipeline already synthesises everything |
| OpenAIR (U. York): original WAVs | `openair.hosted.york.ac.uk`: **HTTP 403 "suspendedpage"** as of 2026-09-28. York Pure "OpenAirLib" dataset (`pure.york.ac.uk/portal/files/70013459/OpenAirLib_master.zip`, 61 MB, "Licence: CC BY") returns 403 to scripts | – | per-IR: PD / CC BY / BY-SA / **BY-NC-SA / BY-NC-ND** | ⚠ Currently not script-downloadable |
| Reverb.js IR library (OpenAIR-derived) | `http://reverbjs.org/Library/<Name>.m4a` (**http only**; https timed out) | AAC .m4a, tiny | reverb.js code is CC0; each IR keeps its OpenAIR licence | Lossy and short: sketch quality only |
| ↳ **PurnodesRailroadTunnel** (80 m railway tunnel) | `http://reverbjs.org/Library/PurnodesRailroadTunnel.m4a` | 12 KB | **Public Domain** (per reverbjs.org) | Usable, low fidelity |
| ↳ **SaintLawrenceChurchMolenbeekWersbeekBelgium** | `http://reverbjs.org/Library/SaintLawrenceChurchMolenbeekWersbeekBelgium.m4a` | 18 KB | **Public Domain** | Usable, low fidelity |
| ↳ SpokaneWomansClub (reflective hall) | `http://reverbjs.org/Library/SpokaneWomansClub.m4a` | 25 KB | **CC BY** | Usable with credit |
| ↳ YorkMinster · HamiltonMausoleum (very long tail) · R1NuclearReactorHall · TerrysFactoryWarehouse | `http://reverbjs.org/Library/{YorkMinster,HamiltonMausoleum,R1NuclearReactorHall,TerrysFactoryWarehouse}.m4a` | 133 / 214 / 219 / 312 KB | ⚠ **CC BY-SA** | Great spaces, but SA. Whether a convolved mix is a derivative of the IR is legally unclear. Flagged |
| ↳ Abernyte Grain Silo, Arbroath Abbey, Kinoull Aisle, Perth City Hall, Errol Brickworks; Elveden Hall | same pattern | – | ⚠ **BY-NC-SA**; ⚠ **BY-NC-ND** | Do not use |
| EchoThief (Chris Warren) | `https://www.echothief.com/wp-content/uploads/2024/07/EchoThiefImpulseResponseLibrary.zip` | zip (size not checked) | "copyright 2013-2026 Dr. Chris Warren"; no open licence stated on the downloads page | ⚠ Avoid unless the licence is confirmed |
| MIT IR Survey (Traer & McDermott) | `https://mcdermottlab.mit.edu/Reverb/IRMAudio/Audio.zip` | 11.7 MB | No licence stated on the page | ⚠ Avoid; small everyday spaces anyway |

### 5c. General CC0 SFX sources (no login)

* **Freesound:** confirmed **login required**. `/people/<user>/sounds/<id>/download/` returns 302 to `/home/login/`, and the APIv2 returns 401 without a token (downloads need OAuth2). Not usable from CI.
* **NASA** audio (above): PD.
* **space-audio.org:** CC BY 4.0.
* OpenGameArt (CC0 subset) and Kenney.nl (CC0): login-free but game-flavoured; not recommended for the film's tone.
* Avoid BBC Sound Effects (RemArc, non-commercial) and Sonniss GDC bundles (royalty-free but custom licence with no redistribution, and no stable direct links).

---

## Notes for `production/tools/fetch_assets.py`

* **Retries and checksums:** use exponential backoff. This container saw transient resets to ambientcg.com, docs.ambientcg.com and one space.physics.uiowa.edu host. Verify `Content-Length`, and record SHA-256 in `ASSETS.md`.
* **Poly Haven:** send a descriptive `User-Agent` (their API terms require it); the CDN `dl.polyhaven.org` URLs are static.
* **ambientCG:** `get?file=` returns a 302, so follow redirects.
* **Codeberg LFS files:** use `/media/branch/main/…`, not `/raw/…`.
* **NASA GitHub files:** fetch individually from `raw.githubusercontent.com`; don't clone.
* **Gaia TAP:** one sync query per 10° RA chunk (~15 s each). Cache the merged result; don't re-query per run.
* **Large files:** SVS 16k EXRs (374–443 MB) and the Voyager Jupiter MP3 (128 MB) should be cached with `actions/cache` or a release asset, not fetched on every run.

# External assets used by the hero ship

All geometry is procedural (`ship_build.py`). The only downloaded assets are CC0 texture sets. They
are fetched by `fetch_textures.py` into `production/cache/textures/<ID>/` (gitignored), and each set
gets a `SOURCE.txt` with its URL and zip SHA-256.

| asset | used for | URL | licence | zip SHA-256 |
|---|---|---|---|---|
| ambientCG **Foil002** (Color, NormalGL, Roughness, Displacement) | gold kapton MLI crinkle, tape | https://ambientcg.com/get?file=Foil002_2K-JPG.zip | CC0 1.0 | `5c5c9f814908d97e8d55bc555908a4eafffb9d748b70c8615fb9fb2e55a2e4d2` |
| ambientCG **Foil001** (Color, NormalGL, Roughness, Displacement) | silver MLI, aluminised tape | https://ambientcg.com/get?file=Foil001_2K-JPG.zip | CC0 1.0 | `ad0d4f06f310fb48ec729ced1df16d2f2429b61be728f6a2d401460b097fd5ad` |
| ambientCG **Metal009** (Color, NormalGL, Roughness) | brushed aluminium (truss longerons, louvers) | https://ambientcg.com/get?file=Metal009_2K-JPG.zip | CC0 1.0 | `6f79f53d5073e65707c5765316fa9257f4604e1790093be5a51ed8226761a7f0` |
| ambientCG **SurfaceImperfections003** (Color, NormalGL, Opacity) | smudge / handling grime masks | https://ambientcg.com/get?file=SurfaceImperfections003_2K-JPG.zip | CC0 1.0 | `11675d43dcc2ae0c2c886ae1c67ae5bd29fa704ab81a45cfb8918133745835c0` |
| ambientCG **Scratches002** (Color, NormalGL, Opacity) | paint / stencil scratch masks | https://ambientcg.com/get?file=Scratches002_2K-JPG.zip | CC0 1.0 | `fa9585eb54600a3f8fb4924abf795ccd69211a18f625347a215d54e78ce755ec` |

Licence: "All ambientCG assets are provided under the Creative Commons CC0 1.0 Universal License"
(https://docs.ambientcg.com/license/). Credit is optional: "Textures: ambientCG.com (CC0)".

Fonts for the stencils come from the repo (`assets/fonts/`), with no download needed:

| font | used for | licence |
|---|---|---|
| Jost (variable) | LSV-7 registration, large markings | SIL OFL 1.1 (`assets/fonts/Jost-OFL.txt`) |
| IBM Plex Mono Light | small technical/warning stencils | SIL OFL 1.1 (`assets/fonts/IBMPlexMono-OFL.txt`) |

No NASA 3D models are imported. The NASA 3D Resources models listed in `docs/assets_research.md`
(Cassini, Voyager HGA, Dawn/DS1 ion engines, MRO foil) served only as proportion and detail
references.

The lookdev env probes (`production/cache/ship_lookdev/*.exr`) are generated at run time by
`ship_api.make_test_probe`. They are not external assets.

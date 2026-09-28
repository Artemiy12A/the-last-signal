# Credits & licences

## Assets

| asset | source | licence |
|---|---|---|
| `assets/sky/milkyway_diffuse.jpg` | Derived from **NASA/Goddard Space Flight Center Scientific Visualization Studio, "Deep Star Maps 2020"**, `starmap_2020_8k_gal.exr`, <https://svs.gsfc.nasa.gov/4851>. Point sources removed, downsampled and gamma-encoded by `tools/prepare_sky.py`. | NASA imagery is generally not subject to copyright in the United States ([NASA media usage guidelines](https://www.nasa.gov/nasa-brand-center/images-and-media/)). Credit: NASA/Goddard Space Flight Center Scientific Visualization Studio. The map incorporates data from the Hipparcos-2, Tycho-2 and Gaia DR2 catalogues (ESA). |
| `assets/fonts/Jost-Variable.ttf` | Jost by indestructible type\*, via Google Fonts (<https://github.com/google/fonts/tree/main/ofl/jost>) | SIL Open Font License 1.1 (`assets/fonts/Jost-OFL.txt`) |
| `assets/fonts/IBMPlexMono-Light.ttf` | IBM Plex Mono, via Google Fonts | SIL Open Font License 1.1 (`assets/fonts/IBMPlexMono-OFL.txt`); used only for the contact-sheet labels |

## Generated in code (no external assets)

* Black hole, accretion disk, star field, the probe model: `lastsignal/shaders/scene.frag`
* Every sound in the soundtrack: `lastsignal/audio.py`
* Blackbody colours: CIE 1931 colour-matching function fit from Wyman, Sloan & Shirley,
  *Simple Analytic Approximations to the CIE XYZ Color Matching Functions*, JCGT 2(2), 2013.

## Libraries

moderngl, glcontext (MIT), NumPy, SciPy (BSD), Pillow (MIT-CMU), FFmpeg/x264 (GPL, used as
an external program), Mesa llvmpipe (MIT). Optional: OpenEXR (BSD) to rebuild the sky map.
Code: MIT (see LICENSE). Assets: see CREDITS.md.

# PROGRESS — THE LAST SIGNAL (90 s)

## Current phase

**Phase 1 → 2 (core tech done, previs starting). Paused by the user on 2026-09-28 ~10:30 UTC.**

## Done

- Reference: original fetched and analysed (`docs/reference_analysis.md`, stills in `docs/reference/`).
- Research: `docs/physics.md` (spin 0.8, 80–86° inclination, Page–Thorne 6500 K disk, beaming ∝ g²,
  infall time dilation), `docs/research_sota.md` (trailer craft, finishing, farm), `docs/assets_research.md`.
- Shot plan: `docs/shot_plan.md` (16 shots + black/title/button, the "ship becomes the signal" twist).
- EDL: `production/tls/edl.py` — single timing source (shots, motif, signal pulses, beacon flashes,
  interference, sound cues, silence 82.5–84.5).
- Kerr tracer (`production/tracer`, C++/OpenMP): Kerr–Schild Hamiltonian RK4, validated shadow edges
  (a = 0, 0.9, 0.99); volumetric turbulent disk (per-radius flow reset, filaments, lanes, hot spots),
  haze, plunging gas; Tycho-2 stars with flux-conserving lensing footprints; NASA SVS Milky Way;
  boosted camera tetrads; relativistic beacon emitter on a timelike worldline; EXR layers
  (disk, haze, sky, stars, beacon, A, hole) or single beauty (env probes). ~76 µs/ray-core after
  a 3× optimisation pass; estimated ~300 core-hours for the whole film at final.
- Compositor (`production/comp`): per-layer gains, oval-bokeh DOF, bloom, glare, streaks, halation,
  distortion + edge CA, vignette, AgX, grain, signal interference, titles.
- Camera language (`production/tls/camera.py`), world/sky continuity (`tls/world.py`),
  timelike geodesics for the fall (`tls/geodesic.py`), frame runner (`tls/render.py`).
- Render farm: `.github/workflows/tls90-render.yml` + `tls/farm.py` (plan → build → 20× render →
  assemble → release). Triggered by editing `production/render-request.json` or dispatch.
  Smoke test 1 failed on 16-bit PNG writing (fixed: 16-bit PPM); retry (attempt 2) was launched,
  result not yet checked.

## In progress when paused

- Hero ship (Blender, `production/blender/ship/`): agent interrupted by a rate limit mid-build
  (geometry + materials scripts exist, no API/renders yet). Resume or rebuild from its brief.
- Soundtrack (`production/audio/`): agent interrupted mid-build (dsp, motif, elements,
  make_soundtrack exist, not yet rendered/verified).
- S15 (the fall): beacon now reads; next is framing/exposure polish and a light-curve export for audio.

## Next

1. Check farm smoke test (attempt 2); fix until an MP4 artifact comes out.
2. Resume ship + audio agents (or redo inline).
3. Write the remaining shot modules (S01–S06, S08, S09, S11–S14, BLK/TITLE/BTN), Blender frame
   renderer (`tls/blender.py` + `production/blender/render_frame.py`), env probes.
4. Full 90 s draft previs cut → pacing review (frame strips, camera velocity plots) → first
   pre-release.

## Known problems

- Disk lookdev not approved: colour reads beige under AgX, front band heavy at 86°; needs a grade
  and reviewer passes.
- Tycho-2 is CC BY-NC 3.0 IGO (fine for this non-commercial film; credit in ASSETS.md — to write).
- ASSETS.md not written yet.

## Shot status

| id | beat | status |
|---|---|---|
| BLK0 | black open | placeholder |
| S01–S06 | Act I–II | placeholder |
| S07 | glimpse: edge | preview (tracer-only draft) |
| S08, S09 | debris, breath | placeholder |
| S10 | the reveal | preview (tracer-only draft, no ship fg yet) |
| S11–S14 | scale → time | placeholder |
| S15 | the fall | preview (draft, beacon works) |
| BLK1, TITLE, BTN | silence, title, button | placeholder |

## Pipeline commands

```bash
make -C production/tracer                         # build the tracer (native)
python production/tools/build_sky.py all          # Tycho-2 stars + Milky Way map -> production/cache/sky
cd production && python -m tls.render still S10 57.0 --q draft|preview|final
cd production && python -m tls.render shot S15 --q draft --every 12
cd production && python -m tls.farm plan --quality final --jobs 20
python production/tools/lookdev.py /tmp/ld --dist 80 --incl 86 --var disk.h_over_r=0.012,0.02
```

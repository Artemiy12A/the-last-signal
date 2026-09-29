# PROGRESS — THE LAST SIGNAL (90 s)

## Current phase

**Phase 2 → 3: all 19 shots exist and render; first full-quality-ish preview cut (960 px, every
frame, with the soundtrack) goes to the farm as `tls90-preview-1`. Next: reviewer passes.**

Previews published so far:
- `tls90-previs-1` (draft, every 2nd frame, no final ship/sound): https://github.com/Artemiy12A/the-last-signal/releases/tag/tls90-previs-1

## Done

- Reference analysis, research (`docs/physics.md`, `docs/research_sota.md`, `docs/assets_research.md`),
  shot plan (`docs/shot_plan.md`), EDL (`production/tls/edl.py`).
- Kerr tracer, compositor, camera language, geodesics, frame runner, review tools
  (`tls/review.py`: camera motion curves, cut strips, contact sheets), S15 light-curve tool.
- Render farm: plan → build → 20× render → assemble (ProRes master + H.264) → release. Works end
  to end (previs-1: 18 min, 0 missing frames).
- Hero ship LSV-7 (`production/blender/ship/`, README + ASSETS_SHIP.md): procedural hull, MLI,
  lattice spine, HGA gimbal, lamps, light groups; cached .blend keyed by source hash.
- Soundtrack (`production/audio/`, README + ASSETS_AUDIO.md): FM tritone motif (beacon tick ↔
  slowed signal are one voice), braam reveal, Shepard fall, true digital silence 82.5–84.5,
  −14 LUFS, rendered from the EDL and the S15 light curve.
- 2026-09-29 shot pass:
  - S05 disk dimmed to an ember (reveal stays the payoff).
  - S06 rebuilt as an eclipse behind the dish.
  - S08 rebuilt as a sparse long-lens debris stream with dust streamers.
  - S12 as a grazing skim under the arch.
  - S13 as a dutch-angled, blue-shifted forward view.
  - S14 rebuilt as "last look", a beacon macro against the shadow.
  - S15 moved to a high vantage (18° above the disk) so it no longer repeats S10.
  - Time dilation made continuous S14→S15 (physics P15).

## Next

1. Watch `tls90-preview-1` (contact sheet, cut strips, camera curves, audio plots).
2. Independent reviewer agents on preview stills vs `docs/reference/` — most iterations on S10
   reveal, S11 scale, S15 climax, TITLE.
3. Known look issue: disk texture reads as brushed/"vinyl" streaks in close views (S12, S15) —
   more clumps/lanes, less azimuthal coherence.
4. Final render (2 waves if needed), final release, README link, Claude Docs bible, Canva poster +
   vertical cover.

## Known problems

- Disk striation (above). S14 is a strong image but the lamp's scale is ambiguous.
- Nobody has listened to the mix yet (built from plots and numbers).

## Shot status

| id | beat | status |
|---|---|---|
| BLK0 | black open | preview |
| S01 | the deep | preview |
| S02 | hull macro | preview |
| S03 | listening | preview |
| S04 | wrong stars | preview |
| S05 | the pull | preview |
| S06 | glimpse: light (eclipse) | preview |
| S07 | glimpse: edge | preview |
| S08 | debris | preview |
| S09 | breath | preview |
| S10 | the reveal | preview |
| S11 | scale | preview |
| S12 | under the arch | preview |
| S13 | interference | preview |
| S14 | last look | preview |
| S15 | the fall | preview |
| BLK1, TITLE, BTN | silence, title, button | preview |

## Pipeline commands

```bash
make -C production/tracer                         # build the tracer (native)
python production/tools/build_sky.py all          # Tycho-2 stars + Milky Way map -> production/cache/sky
cd production && python -m tls.render still S10 57.0 --q draft|preview|final
cd production && python -m tls.render shot S15 --q draft --every 12
cd production && python -m tls.lightcurve         # after any S15 change (feeds edl.ship_rate + sound)
python production/audio/make_soundtrack.py        # -> production/cache/audio/soundtrack.wav
python production/audio/analyze.py                # spectrogram, loudness, sub-bass plots
cd production && python -m tls.review camera      # camera motion curves
cd production && python -m tls.farm plan --quality preview --jobs 20
# farm: edit production/render-request.json (quality/frames/every/tag), commit, push
```

# PROGRESS — THE LAST SIGNAL (90 s)

## Current phase

**Phase 4: final render on the farm (`tls90-final`, 1920x804, 60 shards, ~8.5 h). Review round 2 done.**

Previews published so far:
- `tls90-preview-2` (preview 960 px, every frame, sound; after review round 1): https://github.com/Artemiy12A/the-last-signal/releases/tag/tls90-preview-2
  — run 37151490629, 2 h 08 min on 20 runners, 90.000 s, H.264 + AAC, −14.1 LUFS.
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

- Review round 1 (independent picture + sequence reviewers, 2026-09-29), acted on:
  - EDL retimed: reveal at 46 s, S11 a 2.5 s speck, S12 5 s, S13 4 s, S14 4.5 s, S15 9 s.
  - The twist made readable: steered ship clock (physics P21), the fall ends on one complete motif at
    the signal's x4.5; the title restates it; the long pulse lands in the black with a red point.
  - S15 beacon = a 6000 K point that reddens and dims inside the dimmed disk; S14→S15 match cut.
  - Reveal protected (S04/S05 lensed stars only, S07 an edge glimpse).
  - House grade desaturated (0.94 → ~0.65 median saturation of bright pixels) with white-hot highlights.
  - Streaks soft-kneed and shortened; frame-edge smear fixed; ship relit (hard keys, rims).
  - S11 true speck; S12 black shadow; S13 blue shift; title heavier + ring echo + grain.
  - Sound: S15 onsets from the EDL, reveal hit + riser from the motif (no braam/Shepard), Act I
    +8 dB, LRA 12.4 LU.

- Review round 2 (independent reviewer on the preview-2 MP4, 2026-10-03), acted on:
  - S15 beacon blackouts fixed (sub-pixel emitter aliasing): emitter >= 2.2 px, flux-conserving;
    acceptance test = beacon-only render of all 204 S15 frames at 960 px, no zero-flux frame; flashes
    on/off (first short 594 vs ember 0.4), colour G/R 0.40 -> 0.02 (deep red), front-loaded fall.
  - The mix ducks 9 dB under the last motif (beacon ~11 dB above everything else).
  - S14 rebuilt (flush xenon dome on the hull edge, shadow + arch behind); S14/S15 cut on the long flash.
  - S10 reveal lands on the hit; S09 hole dissolved in 220 px bokeh; S07 arc only; S06 crescent.
  - S11 from below the disk plane, ship on the bright band; S12 disk floor, no star swirl.
  - Title larger, the motif blinking as a red point under it; wide interference tears; S05 disk off.
  - Farm costs fitted to preview-2 shard times; per-shot budgets (S14, S08, S09); master <= 2 GB guard.

## Next

1. preview-2 checked: sheet and cut strips clean, S14→S15 match cut within ~8% of frame width
   (tune), refresh the bible's stills from its release stills.
2. Review round 2 on the preview-2 frames (most passes on S10 reveal, S11 scale, S15 fall, TITLE).
3. Final render: `render-request.json` quality final, jobs 40 (20 run at once; ~3 h per shard by the
   measured S10 frame, inside the 350 min limit), then the final release + README link at the top.
4. Canva 2:3 poster + 9:16 cover from real final stills; bible updated.

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

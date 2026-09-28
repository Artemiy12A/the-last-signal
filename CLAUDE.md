# CLAUDE.md — THE LAST SIGNAL (90 s remake)

Read `PROGRESS.md` first: it has the current phase, shot status, known problems and next steps.
When the user says "continue": read `PROGRESS.md` and `git log --oneline | head -30`, then resume.

## Project rules

- The original 20 s film and its code are the reference. **Never delete or modify** `lastsignal/`,
  `assets/`, `tools/`, `scripts/setup.sh`, `.github/workflows/render.yml` or the
  `trailer-final-5` release. The new production lives in `production/`.
- Everything must be reproducible from scripts in this repo. No hand-edited binaries.
  Downloaded assets are fetched by `production/tools/fetch_assets.py` and logged in `ASSETS.md`
  (CC0 preferred, CC-BY credited, NASA PD credited).
- One edit decision list drives picture and sound: `production/tls/edl.py`. Shot timings,
  signal pulses and sound cues come from there only.
- Only the orchestrator edits `PROGRESS.md`, `CLAUDE.md` and shared pipeline code
  (`production/tls/`, `production/tracer/`, `production/comp/`). Shot agents stay inside
  `production/shots/<shot>/`.
- Commit before and after every big step. Push to the working branch only.
- Develop on branch `claude/last-signal-90sec-remake-qz9hs1`.
- Look at every render you make (Read the PNG). A shot isn't done because it rendered.
- Cinema wins when physics and cinema conflict — but write the departure down in `docs/physics.md`.

## Look rules (quality bar)

Deep blacks, controlled highlights, bloom never takes over. No neon, no HUD, no game lighting,
no repeated framings. Anamorphic 2.39:1 feel: oval bokeh, restrained horizontal streaks only from
the brightest highlights, edge-only chromatic aberration, halation, fine grain.

## Layout

```
production/
  tracer/      C++ Kerr geodesic ray tracer (black hole, disk, volumes, lensed sky) -> EXR layers
  blender/     Blender Python: hero ship, debris, dust; renders layers lit by tracer env probes
  comp/        numpy compositor: merge layers, lens FX, grade, grain, titles
  audio/       sound design + mix (synth + NASA PD recordings)
  tls/         pipeline package: EDL, cameras, shot runner, encode, review tools
  shots/<id>/  per-shot config + notes
  tools/       asset fetchers, catalog builders
docs/          reference analysis, physics, research, shot plan, reviews
reference/     (gitignored) the original MP4, fetched from the trailer-final-5 release
```

## Commands

Filled in as the pipeline is built — see PROGRESS.md "Pipeline commands" for the current list.

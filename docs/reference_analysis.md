# Reference analysis — THE LAST SIGNAL (original, 20 s)

Source: release `trailer-final-5` (`THE_LAST_SIGNAL_final.mp4`, commit 8b31105).
Stills from it live in `docs/reference/` (`orig_t*.jpg`, `orig_contact_sheet.jpg`,
`orig_spectrogram.png`). The original code is untouched in `lastsignal/`.

## Specs

| | |
|---|---|
| Length | 20.00 s, 24 fps, 480 frames |
| Picture | 1920×1080 H.264 High yuv420p, 14.2 Mb/s, 2.39:1 letterbox inside 16:9 |
| Sound | AAC-LC 48 kHz stereo 304 kb/s, −13.2 LUFS integrated, LRA 7.5 LU |
| Renderer | one GLSL fragment shader on Mesa llvmpipe (CPU): Schwarzschild geodesics, thin disk, analytic stars, SDF probe; ACES tonemap; NumPy synth audio |

## Shot breakdown (measured from the file)

| time | shot | what's on screen | verdict |
|---|---|---|---|
| 0.00–0.75 | black | drone fades up | fine |
| 0.75–4.00 | S1 the void | Milky Way, a Voyager-like probe drifting, red beacon | too dark and murky; probe is a flat black silhouette; Milky Way is a blurry brown smear, not a starfield |
| 4.00–5.25 | card | ONE SIGNAL | generic trailer copy, spends 6 % of the film on text |
| 5.25–8.25 | S2 something is wrong | probe in foreground, huge starless lens region behind it with Milky Way bent into rings | best idea in the film (lensing felt before seen), but the lens is already huge and fisheye-looking; no build |
| 8.25–9.40 | card | FROM WHERE NOTHING ESCAPES | as above |
| 9.40–14.10 | S3 reveal | disk "ignites" outward from the ISCO; photon ring, lensed far side, secondary image | the money shot and genuinely pretty; clean composition, correct topology |
| 14.10–16.70 | S4 scale | wider, disk sweeping across frame, the probe a dark dot on the arch | the probe doesn't read as a ship; scale is asserted, not felt |
| 16.70–17.60 | S5 signal peaks | push into photon ring, horizontal RGB glitch bars, probe silhouette | glitches look like a digital effect preset; climax is 0.9 s long |
| 17.60–18.10 | black | digital silence | 0.5 s — too short to register as silence |
| 18.10–20.00 | title | THE LAST SIGNAL (Jost, wide tracking, glow) over faint ring | clean but plain; the glow reads as a bloom filter |

Contact sheet: ![](reference/orig_contact_sheet.jpg)

## What it does well (keep)

1. **The idea and the order of events.** Lone probe → a signal → space itself looks wrong → the
   reveal → tiny against it → overwhelmed → silence → title. The arc is right.
2. **Topology of the black hole image.** Primary disk image, the lensed far side arching over the
   shadow, the secondary image under it, a thin photon ring. It reads as "Interstellar-correct".
3. **Warm monochrome restraint.** Deep blacks, amber/gold disk, no neon. The grade never goes
   teal-and-orange.
4. **Real sky.** NASA SVS Milky Way (galactic coordinates) lensed around the hole.
5. **Picture and sound share one timeline.** Pings drive the beacon; the soundtrack reads the
   same event list. Keep this architecture (single EDL → picture + sound).
6. **Hard cut to digital silence before the title.**

## What's weak (must beat)

1. **Disk texture looks like vinyl grooves.** Concentric high-frequency rings from noise sampled in
   log r; no turbulence, no clumps, no volume, no flow. Everything is the same thin streak.
2. **Monochrome to a fault.** Doppler asymmetry is only a brightness change; no gravitational or
   Doppler colour shift (no blue-white approaching side, no deep-amber receding side). The frame is
   one hue.
3. **No volume, no atmosphere.** No haze, dust, debris, infalling streams or light shafts. Space
   is empty rather than vast.
4. **The ship is a placeholder.** An SDF Voyager with flat, nearly black shading; no materials,
   no rim light, no running lights that light anything, no engine. At scale it becomes a dot with
   a ring around it (probe dish), which reads as a UI marker.
5. **Stars are noisy.** Every star carries RGB chromatic-aberration fringes, so the starfield
   looks like sensor noise. Density and colours are procedural, not a real sky.
6. **Only two real camera setups for the hole** (front-on reveal, slightly wider scale shot); both
   are symmetric, centred, near-static. No low angles, no over-the-shoulder, no parallax.
7. **Escalation is edited, not rendered.** Intensity comes from cards and a glitch preset instead
   of the world changing: no starfield compression, no time dilation, no interference in the ship's
   own lights.
8. **Text cards eat the runtime** (2.4 s of 20 s) and use stock trailer phrasing.
9. **Sound is loud and flat.** The spectrogram is dense low end almost wall to wall
   (−13 LUFS, LRA 7.5 LU); pings are plain FM beeps; the silence is 0.5 s; there is no real
   sub-bass arc and no spatial movement.
10. **Bloom/glow on text and highlights** reads as a filter.
11. **Low sampling**: shimmering fine disk filaments, aliasing on the photon ring.

## What the new version must keep

- The logline and the order of beats; the title THE LAST SIGNAL; ominous ending.
- Black hole topology (shadow, photon ring, lensed far side over and under) and warm restraint.
- Real sky (NASA SVS Milky Way + a real star catalogue).
- One EDL driving picture and sound; hard cut to real silence before the title.

## What it must beat (targets for 90 s)

| area | original | new version |
|---|---|---|
| Black hole | Schwarzschild, thin textured disk | Kerr (spinning) geodesics, volumetric turbulent disk with flow, Doppler + gravitational colour and brightness, nested photon ring, infalling streamers, haze |
| Stars | procedural, fringed | real catalogue (colour from B−V), flux-conserving lensing filter, no fringes except restrained edge CA |
| Ship | SDF probe | hero spacecraft with MLI foil, panel lines, greebles, running lights, engine, lit by the black hole itself (image-based light from the ray tracer) |
| Space | empty | dust, debris, light shafts through particulates, disk haze |
| Camera | centred and static | operated moves, parallax, over-the-shoulder, low grazing angles, focus pulls, oval bokeh |
| Escalation | cards and glitch preset | starfield compression/aberration, lensing drift, time dilation, the signal leaking into the ship's lights and the image |
| Finish | ACES + bloom + CA on everything | filmic HDR pipeline, halation, restrained highlight-only streaks, edge-only CA, grain |
| Sound | wall of low end | designed arc with a recurring signal motif, radio interference, sub-bass arc, rises, impacts, 2–3 s of true silence, title sting |
| Length | 20 s, 5 shots | ~90 s, ~16 shots, each earning its time |

## Story upgrade

The original never says what the signal is. The new version makes the ending pay it off without
words: the signal we hear from the start is a slow, deep, redshifted pulse pattern. Our ship's
own beacon blinks the same pattern — fast and bright. At the climax, as our ship falls toward the
hole, a distant camera sees its beacon slow down and redden (gravitational time dilation) until it
*becomes* the signal we heard at the start. The signal was the last message of the ship before
it. Ours is now the last signal. Hard cut, silence, title, and one final slow pulse.

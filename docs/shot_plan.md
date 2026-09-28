# Shot plan — THE LAST SIGNAL (90 s)

24 fps · 2160 frames · 2.39:1 (1920×804 active) · timings are authoritative in `production/tls/edl.py`.

**Logline.** A lone deep-space vessel follows a slow, deep signal to a supermassive black hole — and
learns, too late, whose signal it was.

**The idea the picture carries without words.** The signal we hear from the first second is a slow,
reverberant three-and-one pulse. Our ship's own beacon strobes the same three-and-one pattern — fast
and bright. At the end, seen from far away, our ship falls toward the shadow; gravitational time
dilation stretches its beacon until it slows, reddens and fades into exactly the signal we heard at
the start. Hard cut. Silence. Title. One last slow pulse in the dark.

**Scale ladder.** hull detail (cm) → ship (60 m) → debris & dust (km) → disk (10⁴ km+) → shadow.
Big things move slowly; the ship may move fast. Deep focus on the immense, oval bokeh only on
foreground motes and stars behind macro shots.

**Palette.** Act I: cold, near-monochrome starlight, the ship's own lights the only colour (xenon
white strobe, red/green nav). Act II: first warm light leaks in. Act III: white-gold disk, Doppler
blue-white on the approaching side, deep amber receding. Act IV: redshift — everything bleeds to red,
then black.

## Beat map

| # | id | time (s) | dur | shot | how | story job |
|---|---|---|---|---|---|---|
| — | BLK0 | 0.0–3.0 | 3.0 | black; sub rises; three slow signal pulses, radio hiss | audio | hook: something is calling |
| 1 | S01 | 3.0–10.0 | 7.0 | **The Deep.** Extreme wide starfield, Milky Way diagonal, total stillness. A single point of light crosses — the ship's beacon strobing the motif | tracer sky + tiny ship | isolation, scale of emptiness |
| 2 | S02 | 10.0–15.5 | 5.5 | **Hull.** Macro glide along the hull: crinkled gold MLI, panel seams, stencils, frost; the strobe fires and lights the foil; stars as oval bokeh; focus pulls to the dish rim | Blender + tracer bokeh plate | it's real, it's alone, it's been travelling a long time |
| 3 | S03 | 15.5–21.5 | 6.0 | **Listening.** 3/4 medium: the high-gain dish slews and locks; the signal arrives — running lights stutter in sync | Blender + tracer sky | the ship hears it; the signal touches the world |
| 4 | S04 | 21.5–28.0 | 6.5 | **Wrong stars.** Over the aft, looking ahead: stars ahead stream and arc around an empty centre as the ship moves (Einstein ring drift) | tracer (D≈400 M) + ship silhouette | something vast, felt before seen |
| 5 | S05 | 28.0–33.5 | 5.5 | **The pull.** Wide side view: ship small at left; behind, the Milky Way doubled into a ring, stars smeared into arcs; a hair-thin golden line at the centre | tracer (D≈150 M) + ship | it's real and we're heading into it |
| 6 | S06 | 33.5–37.0 | 3.5 | **Glimpse: light.** Static on the dish rim; warm gold light sweeps across the foil for the first time; hard shadows swing | Blender, lit by tracer env probe | first touch of its light |
| 7 | S07 | 37.0–41.0 | 4.0 | **Glimpse: edge.** Extreme telephoto: a razor-thin blazing arc on black, turbulent gas streaming across it. No scale reference | tracer (FOV 3–5°) | beauty and dread, partial |
| 8 | S08 | 41.0–46.0 | 5.0 | **Debris.** The ship passes through a stream of rock and dust; rocks tumble past lens, rim-lit gold; shafts of light through the dust; the signal cuts out | Blender (rocks, volume) + tracer env | danger, texture, parallax |
| 9 | S09 | 46.0–48.5 | 2.5 | **Breath.** Near-silence. Low behind the ship: its dish silhouetted against a glowing veil of dust | Blender + tracer plate | the inhale |
| 10 | S10 | 48.5–60.0 | 11.5 | **THE REVEAL.** Crane up over the ship (silhouette drops out of frame): the whole black hole — disk across the frame, lensed arch towering, photon ring — slow push, hold | tracer (i≈86°) + ship fg | the payoff |
| 11 | S11 | 60.0–65.5 | 5.5 | **Scale.** Long lens from far behind: the ship a speck silhouetted against the blazing arch; blue engine thread; beacon pulsing | tracer + ship (long lens) | tiny and fragile |
| 12 | S12 | 65.5–69.5 | 4.0 | **Under the arch.** Grazing skim just above the turbulent disk surface, the arch towering overhead, the ship ahead | tracer (i≈89.5°) + ship | immersion, speed |
| 13 | S13 | 69.5–72.5 | 3.0 | **Interference.** The ship's forward view: the shadow swelling, stars compressing and blue-shifting ahead (aberration); the image itself tears with the signal | tracer (boosted camera) + comp FX | reality warps |
| 14 | S14 | 72.5–76.0 | 3.5 | **Time.** Extreme close on the beacon: pulses slow, colour sinks from white to red; frost drifts in slow motion | Blender + comp | time dilation, felt |
| 15 | S15 | 76.0–82.5 | 6.5 | **The fall.** Wide, far away: the beacon — a point — falls to the shadow's edge; lensed into an arc along the photon ring; pulses stretch, redden, fade; the last flash echoes once around the ring | tracer with relativistic beacon | the ship becomes the signal |
| — | BLK1 | 82.5–84.5 | 2.0 | hard cut to black, **true digital silence** | — | the void |
| — | TITLE | 84.5–89.0 | 4.5 | THE LAST SIGNAL, over black, a deep sting | comp typography | title |
| — | BTN | 89.0–90.0 | 1.0 | black; one last slow pulse — the signal, as at the start | audio | the loop closes |

## Escalation plan (must be visible)

- Starfield: static (S01) → lensing drift (S04) → arcs and doubled Milky Way (S05) → aberration
  compression and blue-shift (S13).
- Light: none → the ship's own strobe → first warm leak (S06) → blinding (S10–S12) → red-shift (S14–S15).
- Signal: heard (BLK0) → touches the ship's lights (S03) → cuts out (S08–S09) → tears the image (S13)
  → becomes the ship (S15).
- Time: normal → slow motion (S14) → frozen at the horizon (S15).
- Cutting: 5–7 s holds → 3.5–5 s → 11.5 s reveal hold → 3–4 s → cut on the final flash.

## Rules

- No two consecutive shots share a framing family (macro / medium / wide / telephoto / POV).
- Every beacon flash, light flicker, interference burst and sound cue comes from `production/tls/edl.py`.
- The black hole never snaps: its angular speed on screen stays slow even when the ship moves fast.

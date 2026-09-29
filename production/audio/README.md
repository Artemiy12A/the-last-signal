# production/audio: THE LAST SIGNAL soundtrack

Deterministic sound design and mix for the 90 s teaser. It is rendered entirely from
`production/tls/edl.py`, so re-running after an EDL change follows it. Nearly all of it is
synthesised with numpy/scipy; three public-domain or CC BY space recordings add texture
(see `ASSETS_AUDIO.md`).

## Run

```bash
pip install numpy scipy soundfile pyloudnorm matplotlib   # pyloudnorm/matplotlib: analysis only
python production/audio/fetch_audio.py        # once: 3 recordings -> production/cache/audio/src/ (sha256-pinned)
python production/audio/make_soundtrack.py    # ~90 s on 4 vCPU
python production/audio/analyze.py            # ~30 s: review plots + report
```

`make_soundtrack.py --no-recordings` renders pure synthesis (the texture layers are skipped), and
`--out DIR` redirects the output. Two renders are bit-identical: every random source is seeded by
name, and every cue, pulse and flash comes from the EDL.

**Outputs** go to `production/cache/audio/` (gitignored):

| file | what |
|---|---|
| `soundtrack.wav` | the master. 48 kHz / 24-bit PCM / stereo / exactly 4 320 000 frames (90.000 s) |
| `stems/{drones,signal,beacon,interference,fx,music}.wav` | pre-master stems at the master gain × `stem_scale` (see `render_meta.json`). Divided by `stem_scale`, they sum to the mix before phone harmonics, bus compression and limiting |
| `render_meta.json` | loudness, true peak, LRA, master gain, gain reduction and render time |
| `cuesheet.json` | every event the render placed (cues, pulses, flashes with stretch/redshift/level, J-cut leads, ring echo, light curve use) |
| `master_gr.json` | compressor and limiter gain reduction at 20 Hz (plotted in `loudness.png`) |

**Review** files are in `production/audio/review/`:

| file | what |
|---|---|
| `spectrogram.png` | log-f, full 90 s, with shot boundaries, cue markers and signal/beacon ticks |
| `loudness.png` | momentary + short-term LUFS, phone simulation (HP 300 Hz), compressor/limiter GR |
| `sub_energy.png` | 20–80 Hz energy, plus the 150–1000 Hz band where phones hear the sub's harmonics |
| `stems.png` | per-stem momentary loudness |
| `motif.png` | zoomed views: one received motif, the beacon's morph (S13–S15), the last pulse |
| `report.txt` | integrated / true peak / LRA, silence and edge checks, hit and pulse alignment, per-shot levels |

## Code

| module | role |
|---|---|
| `dsp.py` | oscillators (polyBLEP saw, FM), filters (Butterworth, block-wise time-varying RBJ biquads, resonators), allpass decorrelation / M-S width / Haas, SSB frequency shift, bit-crush, granular, varispeed, synthetic stereo IRs (octave-band RT60, pre-delay, early reflections), sidechain-HP bus compressor, 4× true-peak look-ahead limiter |
| `loudness.py` | BS.1770-4 K-weighting, momentary, short-term, gated integrated, LRA. Matches pyloudnorm to 0.04 LU; a 997 Hz reference sine reads −3.01 LUFS |
| `motif.py` | **the signal and the beacon: one parametric voice + the radio channel** |
| `elements.py` | one handler per EDL cue kind (`cue_<kind>`), plus the continuous layers (signal, beacon, interference). Level curves are anchored to EDL shot starts and cue times |
| `make_soundtrack.py` | `Mix`: stem buses in three layers (`dry` film-time, `post` pre-slowed, `end` after the silence), reverb sends, the time-stretch warp, ducking / dips / dropouts, the hard cut and end fade, then mastering and writing |
| `analyze.py` | plots + report |
| `fetch_audio.py` | downloads with retry, checksums |

## The signal motif (the most important sound)

The EDL motif is three short pulses and one long one (`MOTIF`, `FLASH_SHORT`/`FLASH_LONG`).
`motif.voice(long, stretch, redshift)` renders one pulse. All of its times scale by `stretch`
(body, attack `1.5 ms·s^1.5`, release, chirp, FM index decay, click) and all of its frequencies
scale by `redshift`:

* **Timbre:** 2-operator FM with a **tritone modulator ratio (√2)**, index 1.8 decaying to 0.54.
  The spectrum is inharmonic and bell-like, with its strongest partials at 0.414 f, f and
  2.414 f: a minor tenth either side of the root. That symmetric, "wrong" interval is what makes
  the motif recognisable and unsettling. Each pulse starts with a quick downward chirp (+22 %
  settling in 4 ms·s) and sags, by a whole semitone on the long pulse.
* **Beacon** = `voice(s=1, g=1)`: root **660.7 Hz**. It is a crisp, slightly driven FM tick with
  a 2.5 kHz click, dry and near-mono (small "hull" IR). Its per-shot gain, pan and nearness live in
  `BEACON_SHOT`: loud and bright on the S02 hull macro and the S14 close-up, faint and dark in the
  wides, silent in S07.
* **Signal** = `voice(s=4.5, g=1/4.5)`, exactly as `edl.signal_pulses()` specifies: root
  **D3 (146.8 Hz)**, partials at 60.8 Hz and 354 Hz, and a D1 sub two octaves down. The morph
  weight `w(s) = smoothstep((s−1)/3.5)` blends in the deep partials. It then passes through
  `motif.radio()`:
  * band-limiting to 190–3300 Hz;
  * an SSB mistuning of 4–11 Hz, which beats against the clean copy (heterodyne);
  * drive and AM flutter;
  * 12–45 ms dropouts;
  * crackle riding the envelope;
  * a drifting 1.3–2.3 kHz carrier whistle;
  * squelch hiss that opens under each pulse.
  
  The clean copy is M/S-widened; the radio copy sits near the centre. A 60 % send into an
  8 s → 2.5 s RT60 "void" IR gives the long tail.
* **The morph (the story twist):** after 72.5 s every beacon flash carries the EDL's own
  `stretch` and `redshift` (x1.16, x3.1, x4.2, …). The tick is rendered *by the same function*,
  so it slows, sinks and gains the signal's deep partials, radio channel, width and tail. At x4.2
  it is practically the received signal. A continuous **ghost glissando** of the beacon's tone
  follows the ship's clock between flashes, so the change never jumps. The level interpolates
  from the small tick to the signal's level.
* **S15 light curve:** if `production/shots/S15/lightcurve.json` exists, S15's flashes come from
  it. It may be `[[film_time, intensity, redshift], …]` or `{"columns": [...], "rows": [...]}`.
  Each prominent log-intensity peak becomes a flash:
  * onset at the half-rise point;
  * `stretch = 1/g`;
  * long or short from the proper-time width;
  * gain = (peak/first)^0.3, applied as gain^0.5 for sound.
  
  The ghost glissando in S15 follows the measured redshift, and the synthetic ring echo is dropped
  because the curve carries the physical light. Otherwise `edl.beacon_flashes()` is used, with a
  synthetic ring echo 3 s after the last flash. Sound stretch is capped at x10.
* **Last pulse (89.05):** the pure signal voice, alone, with a cos² fade from 89.55 s. The final
  15 ms are exact zeros. The title's tail is faded to zero by 89.0 s.

## Section notes (all times from the EDL)

| time | cue(s) | design |
|---|---|---|
| 0–3 BLK0 | `room_tone_in` | receiver hiss at −62, a D1 sub rising out of nothing, the first three slow pulses (the hook) |
| 3–41 | `drone_deep` | cold and hollow: a breathing D1 sub, a thin D2/A2 pair with 0.1 Hz beats, faint air at 2.5–9 kHz. Act I is sparse: short-term −31…−26 LUFS, dipping to −40 between motifs |
| 10.0 S02 | `hull_creak` | stick-slip friction into 10 metal modes plus a low groan, small hull IR |
| 15.5 S03 | `dish_servo` | motor whine 55→175 Hz, 7× gear mesh, bearing noise, and a lock clunk at the end of `dur` |
| S03 | interference | the signal touches the ship: coupling is 1.0 here, so hiss, static, crackle (rate ∝ J²), heterodyne sweeps with moving pan plus Haas, a 96 Hz electrical stutter synced to the pulses, and Cassini SKR chirps |
| 21.5–33.5 | `lensing_swell` | detuned D2/A2 saw stacks whose beating widens from 4 to 28 cents and whose pitch **bends down 1.5 st**; the LP opens 140→700 Hz; the D1 sub bends too; the Juno Ganymede plasma sweep is reversed (it falls), granular, an octave down |
| 33.2→33.5 | `reverse_swell`, `low_hit` | reverse reverb of the hit, ending on the hit sample; a sub inhale from the cue time (**J-cut lead 7.2 frames**). The hit is transient + body (D2, ×2→×1 pitch envelope) + distorted 200–800 Hz band + sub + rumble tail, into a 6 s hall |
| 37 S07 | `shimmer` | sparse glassy sine grains on the D harmonic set, 70 % void |
| 41–46 S08 | `debris_rumble` | brown rumble plus Mars wind an octave down, 7 rock pass-bys (Doppler band sweep, pan, thump), dust on the hull; the signal drops out (EDL gain 0) |
| 46–48.5 S09 | `near_silence` | fx dips −40 dB (kills the debris tail), beds −14 dB. Only room tone and the ship's tick remain (momentary about −50 LUFS) |
| 48.2→48.5 | `reverse_swell` | reverse reverb of the braam attack plus hit, and a sub inhale: **J-cut lead 7.2 frames** |
| 48.5 S10 | `braam`, `sub_drop` | D1/D2/A2/D3/F3, 8 detuned saws each (±12 ct), tanh(4x), resonant LP blat 110→2900→220 Hz, 500–1200 Hz formant, −1.5 st bend over 2.6 s, 7 s tail, 6 s hall. Sub drop **60→28 Hz** with 2nd/3rd harmonics, plus an impact layer. Then an "awe" chord (D2 A2 D3 E3 A3) and the hole's D1/A1 hum hold the reveal; the signal pulses return at full level |
| 60 S11 | `low_hit`, `tension_pad` | a cluster (D2 A2 D3 E♭3 A3) with string-like tremolo accelerating 5→12 Hz, LP opening 300→2300 Hz, and a growing D1 pedal |
| 65.5 | `whoosh` | pink noise band sweep 300→4k→800 Hz with a pan sweep, peaking 80 ms after the cut |
| 66.5–76 | `shepard_riser` | 9 octave partials rising 1 oct / 5.5 s under a Gaussian spectral window, plus a noise riser |
| 69.5–72.5 S13 | `interference_burst` | tearing: bit-crushed noise, square squeals, SKR fragments, stutters of the signal, 9 criss-crossing heterodyne sweeps, rising static, torn low rumble, soft-clipped as a bus. **Digital dropouts** gate the whole mix. Hard stop at 72.5 |
| 72.5–82.5 | `time_stretch` | the world stems (drones, signal, interference, fx, music, including reverb tails) are **varispeed-read at (dτ/dt)^0.45** from `edl.ship_clock`, so everything slows and sinks: the riser turns over into a fall. There is an entry whump, and the beacon morph and ghost glissando run through it |
| 76–82.5 S15 | (fall, part of `time_stretch`) | an endless **descending** Shepard tone (window 420→140 Hz), a "redshift" noise wash sinking 2.6 k→320 Hz, a roar (brown noise plus Mars wind two octaves down, LP 600→140 Hz), and a sub sinking D1→A0. All of it grows into the cut |
| **82.5–84.5** | `hard_cut_silence` | **true digital silence**: 96 000 exact zeros, reached through a 3 ms fade (no click). The master is processed in two segments so no filter, compressor or limiter touches the silence |
| 84.5 | `title_sting` | deep hit plus a **tonal bloom in the signal's own FM timbre** (D2 D3 A3 D4 A4, random partial phases, gentle soft-clip) and a D1 sub. The 4.5 s tail is faded to zero by 89.0 |
| 89.05 | `last_signal` | the signal pulse, alone, fading into silence at 90.000 |

## Master

The chain runs per segment ([0, 82.5) and [84.5, 90)), with the gain found iteratively so the
full file measures −14 LUFS integrated:

1. Stems are summed with sidechain ducking under the hits (drones and interference by −3 to
   −9 dB, scaled by hit level; music at 40 % of that depth), plus the dips and dropouts.
2. **Phone-proof bass:** the sub band (LP 120 Hz, mono) is envelope-normalised and run through
   a Chebyshev mix of harmonics 2–8 (weights 0.5…0.04). The envelope is re-applied, the result is
   band-passed to 150–1000 Hz and mixed in parallel at −6 dB. The true fundamental is kept.
3. Bus compressor: 1.6:1 at −15 dBFS, 10 dB knee, 30 ms / 350 ms, with a 120 Hz sidechain HP so
   the sub does not pump the mix.
4. Look-ahead true-peak limiter: 4× oversampled detection, 4 ms, ceiling −1.3 dBTP.
5. The silence is forced to zero, and the file is written as 24-bit with no dither (so the
   zeros stay zeros).

## Verified numbers (current render; see `review/report.txt`)

| check | target | result |
|---|---|---|
| duration / format | 90.000 s, 48 k / 24-bit / stereo | 4 320 000 frames, PCM_24, 2 ch |
| integrated loudness | −14 ±1 LUFS | **−14.05 LUFS** (pyloudnorm −14.09) |
| true peak | ≤ −1 dBTP | **−1.30 dBTP** |
| short-term peaks | ≈ −9 | reveal **−8.6**, title **−9.8**, S13 −11.1, S15 −11.0 into the cut |
| Act I | quiet, sparse | BLK0 −28.8, S01 −30.3, S02 −26.8, S03 −27.6 (short-term means) |
| silence 82.5–84.5 | exact zero | 0 non-zero samples; last sound 82.49998 s; sting starts at 84.500000 s |
| hits vs EDL | on the frame | onsets +1.0 to +1.3 ms (33.5, 48.5, 60.0, 84.5) |
| signal pulses | on the EDL | 30/30, onset 0 to +8 ms (the 14 ms attack) |
| dynamics processing | gentle | compressor ≤ 3.9 dB; limiter > 3 dB for 2.6 s of 90 s, max 6.5 dB (title bloom attack) |
| LRA | research doc: 10–15 LU | **17.8 LU**: deliberately wide, because Act I is quiet (−30) against a −14 file |
| sub arc (20–80 Hz, dBFS rms) | builds to the reveal and again to the climax | Act I −41…−30, S05 swell →−19, hit −12, S09 −78, reveal −11, S11 hit −11, S13 −22→−16, S15 −27→−13 into the cut, title −10.5 |
| render time | – | about 90 s (4 vCPU); analysis about 30 s |
| determinism | – | two renders are bit-identical (same SHA-256) |

## Cinema departures (to record in `docs/physics.md`)

* **Sound time dilation** uses (dτ/dt)^0.45 instead of dτ/dt for the world varispeed. At the
  physical rate everything would be sub-audible by 78 s.
* The **ring echo** of the last flash comes 3 s later (the physical value is about 16 M ≈ 6.6 s,
  which would land in the silence). It is used only without a measured S15 light curve.
* Sound stretch per flash is capped at x10 (the physical x25 would put the root at 26 Hz).
* The measured flash fade (about g⁴) is compressed: gain^0.3 in detection, applied as ^0.5.
* Sound in space: every sound is editorial.

## Open issue for the orchestrator

**S14/S15 redshift discontinuity.** `edl.ship_clock` has g ≈ 0.24 (x4.2) at 75.7 s, and S14's
flashes are already deep. The tracer's `shots/S15/lightcurve.json` starts at g = 0.83 (x1.2) at
76.0 s and only reaches g = 0.18 by 82.4 s. The sound follows each shot, so at the S14→S15 cut the
beacon's voice resets from nearly-the-signal back to nearly-the-tick, then morphs again through
S15 (x1.2→x3.7). The picture presumably resets colour the same way. There are two fixes:

* start S15's worldline later (T_CAM0), so g(76.0) ≈ 0.25;
* or retime `ship_clock`, so S14 ends near g ≈ 0.8.

Re-render once either changes: the sound follows automatically.

## Limits

This mix was built analytically; nobody has listened to it yet. A listening pass on speakers,
headphones and a phone should confirm three things:

* the motif's identity;
* the braam and title weight;
* the S13 tearing density.

The per-shot tables in `elements.py` (`BEACON_SHOT`, `SHIP_COUPLING`, `SIGNAL_ACT`) are the mix
faders to adjust.

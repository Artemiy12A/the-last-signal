# Audio assets: sources, licences, credits

Almost everything in the soundtrack is **synthesised** in `production/audio/` (numpy/scipy):
the signal motif, the beacon, drones, braam, hits, risers, radio interference, and all three
convolution-reverb impulse responses (`dsp.make_ir`, research_sota.md §3.3). We wrote all of it,
it ships under the repo licence, and it has no third-party terms.

Three real space recordings are used as **texture layers only**. `production/audio/fetch_audio.py`
fetches them into `production/cache/audio/src/` (gitignored) and pins their SHA-256 below. The
soundtrack still renders without them (`make_soundtrack.py --no-recordings`); those layers are then
skipped.

| file (cache/audio/src) | recording | source URL | licence | credit line | SHA-256 | used for |
|---|---|---|---|---|---|---|
| `juno_ganymede.wav` (48 kHz/16-bit stereo, 49.0 s) | Juno Waves instrument, Ganymede flyby 2021-06-07 (NASA "Sounds from Beyond") | https://www.nasa.gov/wp-content/uploads/2024/05/e2-wave-ganymede-flyby-compressed.wav | Public domain (NASA media guidelines; no endorsement implied, no insignia) | NASA/JPL-Caltech/SwRI/Univ of Iowa | `8cb5393b9faa6cde859a6164a635bcbecb4cf8b6cfe70acc20e6ad3da7711919` | `lensing_swell` 21.5–33.5 s: reversed (the band falls instead of rising), granular, an octave down, band-passed, low in the drone stem |
| `cassini_skr.wav` (5 kHz/16-bit mono, 73.5 s) | Cassini RPWS, Saturn kilometric radiation (SKR-03-324) | https://space-audio.org/cassini/SKR1/SKR-03-324.wav | **CC BY 4.0** (https://space-audio.org/citation.html). Adapted: resampled, band-passed, bit-crushed, sliced | **Original space audio recordings provided courtesy of NASA and The University of Iowa. https://space-audio.org/** | `54b2e2a15edf1e65e5771c7d74422e9c158d0aa87b11fc5730c7a085d49ebdfb` | radio-interference chirps where the signal couples into the ship (S03 and later pulses); bit-crushed fragments in the S13 burst |
| `insight_wind.wav` (8 kHz/16-bit stereo, 20.0 s) | InSight SEIS, Martian wind (the published version is pitched up 2 octaves) | https://www.nasa.gov/wp-content/uploads/2015/01/08-Brian-Cook_raw_velocity_0.6_normalisedx1_2octavesUp_03.wav | Public domain (NASA media guidelines) | NASA/JPL-Caltech/CNES/IPGP | `9f0fa7d6ef14298dc942091d2c083a7809dc96bfaacdac901e7c3ffef4274710` | `debris_rumble` S08 (an octave down) and the S15 fall roar (two octaves down) |

## Credit lines for CREDITS.md / ASSETS.md (for the orchestrator to copy)

```
Sound: original space audio recordings provided courtesy of NASA and The University of Iowa.
https://space-audio.org/ (Cassini RPWS Saturn kilometric radiation, CC BY 4.0; adapted)
Juno Waves Ganymede flyby audio: NASA/JPL-Caltech/SwRI/Univ of Iowa (public domain)
InSight SEIS Martian wind: NASA/JPL-Caltech/CNES/IPGP (public domain)
```

Use of NASA material does not imply endorsement by NASA, and no NASA insignia are used.

## Considered and not used

* The Voyager 1 interstellar plasma MP4 (CC BY 4.0) was not used. The signal motif has to be
  parametric (stretch/redshift) for the beacon morph, so it is synthesised.
* Chandra sonifications: avoided. They are co-credited to SYSTEM Sounds, so there is a
  third-party claim (assets_research.md §5a).
* OpenAIR, Voxengo and EchoThief IRs: not used. All IRs are synthesised (licence-free and
  tunable).
* Freesound, BBC and Sonniss: not used (login walls or non-commercial / no-redistribution terms).

## Software (shipped pipeline)

numpy (BSD-3), scipy (BSD-3), soundfile (BSD-3; wraps libsndfile, LGPL-2.1, dynamically
linked). Analysis only: matplotlib (PSF-style), pyloudnorm (MIT; used as a loudness cross-check).
No GPL code (pedalboard is deliberately not used).

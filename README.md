# THE LAST SIGNAL

A 20-second cinematic sci-fi teaser. A tiny deep-space probe answers a faint
signal and drifts toward a supermassive black hole, and the black hole is the
centrepiece. Everything is generated from code in this repository and rendered in
the cloud: a physically based black hole (ray-traced null geodesics), an
accretion disk with relativistic Doppler beaming, gravitational lensing of the
real Milky Way, a signed-distance-field spacecraft, film-style post, and a
fully synthesised soundtrack locked to the picture.

| | |
|---|---|
| Length | 20.0 s, 24 fps |
| Picture | 1920×1080 H.264 High (2.39:1 scope inside 16:9), Rec.709 |
| Sound | 48 kHz stereo, AAC 320 kbps |
| Output | `THE_LAST_SIGNAL_final.mp4` + contact sheet + verification report |

---

## Render it from your iPhone

You only need Safari (or the GitHub app) and this repository.

> **One-time setup:** the workflow must live on the default branch before GitHub
> shows the **Run workflow** button. If this work is still on a branch, open the
> repo → **Pull requests** → open the PR for the branch → **Merge**. (Or render straight from the
> branch with the commit trigger below.)

### Option A — the Run workflow button (recommended)

1. In Safari open `https://github.com/Artemiy12A/the-last-signal/actions`
   (tap **aA → Request Desktop Website** if the button is hidden on the mobile layout).
2. Tap **Render THE LAST SIGNAL** in the workflow list.
3. Tap **Run workflow** → keep **quality: final** and **publish: ✓** → **Run workflow**.
4. Wait about 20–30 minutes. The run shows 10 parallel *render* jobs, then *assemble*.
   You can lock the phone; GitHub e-mails or notifies you if it fails.

### Option B — a commit message

Edit any file on GitHub (e.g. this README, pencil icon), and commit with a message containing:

* `[render final]`: full 1080p master, published as a Release
* `[render preview]`: 720p, artifacts only
* `[render]`: 540p draft, about 5 minutes, artifacts only

### Download the MP4 to your phone

* **Releases (easiest):** repo main page → **Releases** → newest
  `THE LAST SIGNAL — final` → tap **`THE_LAST_SIGNAL_final.mp4`**. It opens in
  the player → **Share → Save Video** puts it in Photos.
* **Artifacts:** open the finished run (Actions tab) → scroll to **Artifacts** →
  tap `THE_LAST_SIGNAL_final.mp4`. It downloads unzipped (Files app → Downloads).
  The contact sheet `contact_sheet_final.jpg` is right next to it.

Release downloads work for as long as the release exists; artifacts expire after 30 days.

### Render modes

| mode | resolution | AA passes | geodesic step | shards | wall time (2-vCPU runners) |
|---|---|---|---|---|---|
| `draft` | 960×540 | 1 | 0.07 r | 1 | ~5 min |
| `preview` | 1280×720 | 2 (+ motion blur) | 0.05 r | 4 | ~8 min |
| `final` | 1920×1080 | 6 (+ motion blur) | 0.035 r | 10 | ~15–25 min |

A final render uses roughly 100–130 runner-minutes of the free 2,000/month quota
for private repositories. A draft uses about 6.

---

## What's in the trailer

| time | shot | |
|---|---|---|
| 0.00 | black | a deep-space drone fades up, static |
| 0.75 | **S1 · The void** | the Milky Way; a lone probe drifts across it, its red beacon answering a faint signal |
| 4.00 | card | ONE SIGNAL |
| 5.25 | **S2 · Something is wrong** | the probe listens; behind it, the Milky Way bends around an empty circle. The pings sag in pitch (gravitational redshift) |
| 8.25 | card | FROM WHERE NOTHING ESCAPES |
| 9.40 | **S3 · The reveal** | a breath of silence, then the braam: the accretion disk ignites outward from the innermost stable orbit. Photon ring, lensed far side of the disk, Doppler-bright approaching side |
| 14.10 | **S4 · Scale** | skimming over the disk, the lensed arch towers over the probe, a speck with a blue ion engine |
| 16.70 | **S5 · The signal peaks** | push into the photon ring; the probe silhouetted and overwhelmed; interference, white-out |
| 17.60 | cut | hard cut to black and true digital silence |
| 18.10 | **Title** | THE LAST SIGNAL, over the faint photon ring; the last ping, alone, echoing out |

`lastsignal/timeline.py` is the edit decision list: every camera move, light,
card and sound cue is defined there, and the soundtrack reads the same event
list, so the beacon flashes land exactly on the pings.

---

## How it works

```
timeline.py ──► per-frame parameters ──► gl.py (moderngl, headless EGL / Mesa llvmpipe)
                                          │  scene.frag   geodesics, disk, lensed sky, probe (N jittered passes)
                                          │  bloom_down / bloom_up   7-level HDR bloom
                                          │  streak.frag  anamorphic streak
                                          └  composite.frag  ACES tone map, grade, type, grain, letterbox
            text.py (Pillow typography) ──┘
audio.py (NumPy/SciPy synthesis) ──► WAV ──┐
                                   ffmpeg/x264 segments ──► concat ──► mux ──► MP4 ──► contact sheet + verify
```

* **Black hole.** Schwarzschild metric in units of the Schwarzschild radius.
  Each pixel's ray is integrated backwards with a leapfrog integrator of the
  exact photon orbit equation `x'' = -1.5 h² x / r⁵` (step ∝ r). Crossings of
  the disk plane accumulate emission front-to-back, which naturally produces the
  secondary image and the photon ring. Rays that escape sample the sky in their
  bent direction.
* **Accretion disk.** Thin disk from the ISCO (3 r_s) outwards with a
  Novikov–Thorne-like temperature profile. Colour comes from a blackbody LUT
  computed from the CIE 1931 colour-matching functions. Relativistic Doppler plus
  gravitational shift change both colour (temperature) and brightness (g³).
  Keplerian differential rotation drives layered noise: filaments, lanes and
  hot knots.
* **Sky.** NASA SVS *Deep Star Maps 2020* (galactic coordinates) with the
  point stars removed, used for the diffuse Milky Way. Stars are analytic,
  razor sharp at any resolution, and flux-conserving under lensing, so
  magnified stars smear into arcs and demagnified ones dim.
* **Probe.** A Voyager-like signed distance field (3.7 m-class dish, gold-foil
  bus, RTG and science booms, magnetometer), GGX shading, soft shadows, and a
  beacon that is a real light.
* **Post.** HDR accumulation, bloom pyramid, anamorphic streak, chromatic
  aberration, ACES filmic tone mapping, split-tone grade, luma-weighted grain
  (none in true black), 2.39:1 letterbox.
* **Sound.** Synthesised: band-limited (polyBLEP) saw stacks through swept
  filters for the braam and pads, FM pings with ping-pong echo, a convolution
  reverb from a synthetic stereo impulse response, and a hard cut to true silence.

## Run it locally (Linux, or any machine with OpenGL 3.3)

```bash
./scripts/setup.sh                         # apt ffmpeg + Mesa EGL, pip requirements (Ubuntu)
python -m lastsignal render --quality draft    # full pipeline -> out/draft/THE_LAST_SIGNAL_draft.mp4
python -m lastsignal render --quality final    # the 1080p master (~40 min on 4 cores)

python -m lastsignal keyframes --quality preview   # key frames of every shot + contact sheet
python -m lastsignal still --t 12.8 --quality final    # one frame to PNG
python -m lastsignal audio                         # soundtrack only
python -m lastsignal sheet  out/final/THE_LAST_SIGNAL_final.mp4   # contact sheet from a video
python -m lastsignal frames out/final/THE_LAST_SIGNAL_final.mp4 --every 0.5   # PNG frames (or --times 9.5 12.8)
python -m lastsignal verify out/final/THE_LAST_SIGNAL_final.mp4 --quality final
python -m lastsignal selftest                      # timeline continuity, a frame per shot, soundtrack
python -m lastsignal segment --quality final --shard 3 --shards 10   # what each cloud job runs
python -m lastsignal assemble --quality final --segments segments   # what the final job runs
```

`verify` fails the build if the duration isn't 20 s, the audio stream is missing,
the resolution or pixel format is wrong, a picture shot is black, or a cut to
black isn't black.

## Repository

```
lastsignal/            the renderer package (python -m lastsignal)
  timeline.py          shots, cameras, lights, cards, sound events  ← edit the film here
  shaders/scene.frag   black hole, disk, sky, probe
  shaders/composite.frag  grade / tone map / type / grain
  gl.py  audio.py  text.py  encode.py  contact.py  colour.py  cli.py
assets/sky/            Milky Way diffuse map (derived from NASA SVS, see CREDITS.md)
assets/fonts/          Jost, IBM Plex Mono (SIL OFL)
tools/prepare_sky.py   regenerates the sky map from the NASA EXR
scripts/setup.sh       dependency installer (used by CI)
.github/workflows/render.yml   cloud render: plan → 10× render → assemble → release
```

See [CREDITS.md](CREDITS.md) for asset sources and licences.

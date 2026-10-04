**THE LAST SIGNAL** — the final film. 90 s, 1920×804 (2.39:1), 24 fps, stereo, −14 LUFS.

On iPhone: tap **THE_LAST_SIGNAL.mp4** below → it plays in the browser → Share → Save Video.

| File | What it is |
|---|---|
| `THE_LAST_SIGNAL.mp4` | the film: H.264 High, ~30 Mb/s, AAC 320 kb/s |
| `THE_LAST_SIGNAL_master_ProRes422HQ.mov` | the master: ProRes 422 HQ, 24-bit PCM |
| `S01.jpg` … `S15.jpg`, `contact_sheet.jpg` | one still per shot, one frame per second |
| `THE_LAST_SIGNAL_poster_2x3`, `THE_LAST_SIGNAL_cover_9x16` (`.png`, `.pdf`) | poster and vertical cover from the reveal frame (52.0 s) |

Rendered on GitHub Actions from this repository: run 37163704098 (every frame, commit 586b51c), then three patch runs that re-rendered only what it lost or got wrong — 37180446408 (S06 frames 774–798, runner lost), 37194883265 (S02 frames 281–283, shard deadline) and 37196682047 (S15 and its neighbours, frames 1775–2159, after the beacon sampling fix in commit fd71e9c). Frames missing: 0.

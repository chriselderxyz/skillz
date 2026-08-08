# Picture-in-picture

How a segment with both `<n>-cam` and `<n>-screen` becomes one `edit/<n>/base.mp4`. Reached from Produce, step 2.

The screen recording is the background and the cam is the **inset**. Compositing happens once, before cutting, so the cut list, the overlays, and the subtitles all see a single source.

The `overlays` entries in a cut list carry no position or scale, so an inset cannot be expressed there. It is a raw ffmpeg step.

## The cam timeline is canonical

Plan-phase cuts were chosen against the cam clip's transcript. Those timestamps stay valid only if `base.mp4` starts where the cam clip starts and runs its full length. Trim or pad the screen clip to fit the cam — never the other way around.

## Sync

Find the offset before compositing; a drifted inset reads as a dub.

```bash
python <skill_dir>/scripts/sync_pair.py <n>-cam.mp4 <n>-screen.mp4 -o edit/<n>/sync.json
```

It cross-correlates the two clips' loudness envelopes and writes `offset_seconds` — the screen clip's time minus the cam clip's time for the same instant. It exits non-zero and sets `"confident": false` when no single peak stands out, which means the two clips share no common room audio. In that case find a physical sync point by hand — a clap, a key press audible in both tracks — read its timestamp in each clip with `timeline_view.py`, and subtract.

Apply `-ss <offset>` to the screen input when the offset is positive, `tpad=start_duration=<-offset>` when negative, and `-t <cam_duration>` in both cases.

## Composite

Normalize both to the target resolution and fps first — a mismatch here shows up much later as a broken concat.

```bash
ffmpeg -ss <o> -i <n>-screen.mp4 -i <n>-cam.mp4 -t <cam_duration> -filter_complex "
  [0:v]scale=1920:1080:force_original_aspect_ratio=decrease,
       pad=1920:1080:(ow-iw)/2:(oh-ih)/2,fps=30,setsar=1[bg];
  [1:v]scale=-2:1080,crop=1080:1080,scale=440:440,fps=30,setsar=1[fg];
  [bg][fg]overlay=W-w-48:H-h-48[v]
" -map "[v]" -map 1:a -c:v libx264 -crf 18 -preset slow -pix_fmt yuv420p \
  -c:a aac -b:a 192k edit/<n>/base.mp4
```

- **Audio comes from the cam** (`-map 1:a`). The screen recording's audio is a fallback for when the cam has no usable mic, and system audio worth keeping gets mixed in with `amix` rather than swapped in.
- **Inset size** 20–28% of frame width. 440px on a 1920 frame is a starting point; go larger when the face is the point, smaller when the screen has dense detail.
- **Placement** in the corner the screen content leaves empty. Check a frame from the middle of the clip before committing — a terminal in the bottom-right rules out the default corner.
- **Margin** roughly the inset's own corner radius, 40–64px on 1080p.
- The square `crop` before the downscale gives a centered head-and-shoulders framing from a 16:9 cam. Drop it to keep the cam's full frame.

A rounded or circular inset needs an alpha mask: generate a mask PNG once, then `[fg][mask]alphamerge` before the overlay.

## When the inset is the wrong shape

Picture-in-picture is a per-moment call, not a per-segment one. When the speaker is the content — the open, the close, a point made straight to camera — the cam belongs full frame with no screen at all. When the demo is the content, the screen fills the frame.

A segment that swaps between the two mid-way is two bases: composite each span separately and list both as sources in that segment's cut list.

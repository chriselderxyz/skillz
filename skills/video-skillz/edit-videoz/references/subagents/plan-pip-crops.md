# Workflow

## Find The Segments That Need PIP
- Any segment that has a `head` clip needs a PIP crop planned for it
- Perform the next steps for each `head` clip

## Pick a Time in the Clip to Screenshot
- Read the transcription for the current clip
    - Try using `edit/clip_transcriptions/<clip-name>.json` first
    - Use `edit/takes_packed.md` otherwise, which has the transcript for EVERY clip - you'll need to locate the transcript for the clip you're working on
- Note which speaker the clip follows (ex. `speaker_0` or `S0`)
- Using the transcript, pick `--time` inside a spoken phrase, not silence, and not within ~1s of the clip start or end
- Prefer the middle of a multi-word phrase so the mouth is mid-speech

## Screenshot the Clip at the Selected Time
- Run `scripts/inspect/screenshot.py` with the following command

```bash
uv run --no-project <skill_dir>/scripts/inspect/screenshot.py <clip-path> --time <seconds> -o edit/<n>/head-frame.png
```

## Choosing the Crop
- If you have already planned a PIP crop for this speaker on another clip, start with the crop values previously used to stay consistent across the video
- Read `pip_style` from `edit/edl.json`, then merge any keys from `edit/<n>/edl.json` on top, and give the crop the same aspect as the inset. Render fills the box and trims overflow, so a mismatched crop loses the face you framed
  - circle or square: `w` = `h`
  - rect: `w:h` = `aspect` (`1:1` if `aspect` is omitted)
- Read the screenshot, and choose the values for the crop so the face will fill the inset
    - x: Left edge of the kept window (pixels from left of clip)
    - y: Top edge of the kept window (pixels from the top of the clip)
    - w: Width of the kept window
    - h: Height of the kept window

## Iterate on the Crop
- Create a preview of the crop with `scripts/inspect/pip_crop_preview.py`

```bash
uv run --no-project <skill_dir>/scripts/inspect/pip_crop_preview.py <clip-name> \
  --crop <x>,<y>,<w>,<h> \
  -o edit/<n>/pip-crop.png
```

- Read `edit/<n>/pip-crop.png`
- If this is the first crop for a speaker and the framing is wrong, adjust crop parameters and regenerate
- If this is not the first crop for a speaker, only adjust if the framing is very wrong, consistency over perfection
- Cap at 3 passes

## Write Final Crop Values
- Write the final crop values to `edit/<n>/pip-crop.json`

```json
{
    // The name of the clip the crop is for
    "source": "1-head",

    // The crop settings
    "crop": {
        "x": 420,
        "y": 80,
        "w": 1080,
        "h": 1080
    }
}
```

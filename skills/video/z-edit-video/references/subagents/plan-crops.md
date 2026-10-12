# Global Context

## Shared Context
- Read `references/shared-context/concepts.md`.
- Read `references/shared-context/edit-json.md`.

## Read Configs
- Read `edit/edit.json`.
- Read output orientation and aspect ratio from `video_settings`.
- Read `pip_style` for picture in picture settings.

## Initial Run vs. Edits
- On the initial run, plan every crop named below.
- On an edit pass, revisit only the sources whose base_crop or layer crop received feedback.
- When `pip_style` is none, skip inset crops.

# Phase 1: Find the Crops

## Phase Context

### Base Crop Types
- `full`.
  - Apply to sources on a **layer** whose `frame` is `full`.
  - Crop Aspect Ratio: Same as the video.
- `top` and `bottom`.
  - Apply to sources on a **layer** whose `frame` is `top` or `bottom`.
  - Crop Aspect Ratio.
    - 32:9 for a 16:9 video.
    - 9:8 for a 9:16 video.
- `pip`.
  - Apply to sources on a **layer** whose `frame` is `pip`.
  - Crop Aspect Ratio.
    - circle or square: `w` = `h`.
    - rect: `w:h` = `aspect`, or `1:1` when `aspect` is omitted.

## Action 1
- Identify unique sources that require each type of crop.
- Read each source resolution from `sources`.
  - For `pip` crops, always do the crop.
  - For other crops, do not add crops for sources where the aspect already matches the crop aspect within 1%.

# Phase 2: Choose Frames

## Action 1
- For `full`, `top`, and `bottom`, use the **cuts** on the **layers** that use that source and frame.
    - Pick the midpoint of the longest cut as the primary frame.
    - Inspect up to two more frames when the source has several cuts or the subject may move.
    - Keep the times away from the first and last 0.25 seconds of a cut when possible.
- For an inset crop, read the transcript for that source.
    - Try `edit/source-transcriptions/<source-name>.json` first.
    - Use `edit/takes-packed.md` otherwise.
    - Pick a time inside a spoken phrase, not silence, and not within about 1 second of the source start or end.
    - Prefer the middle of a multi-word phrase so the mouth is mid-speech.
- Extract each frame.

```bash
uv run --no-project scripts/inspect/screenshot.py <source-path> --time <seconds> \
  -o edit/<source-group>/<source-name>-frame-<n>.png
```

# Phase 3: Choose the Crop

## Action 1
- The crop is an editorial decision in source-pixel coordinates.
- Use integer `x`, `y`, `w`, and `h`.
- Keep the crop inside the source bounds.
- Give it the aspect from Phase 1.
- If a face is visible.
    - Frame the primary speaking face.
    - For an output crop or a half-frame crop, keep comfortable headroom and avoid cutting through the chin or forehead.
    - For a PIP crop, let the face fill the inset.
    - Keep the face inside the crop across every frame from Phase 2.
    - If several faces matter, include them when possible. Otherwise prioritize the speaker.
- If no face is visible, use a centered crop.
- A screen recording without a face starts centered. The user can request a focal override during review.
- One source gets one `base_crops` entry per frame.
- A **layer** `crop` overrides `base_crops` for that **layer**. Write it only when that **layer** should not use the source's `base_crops` entry.
- A `frame` of `{ "x", "y", "w", "h" }` has no `base_crops` entry. Write `crop` on that **layer**.
- For `pip` crops, when this speaker already has a `pip` crop on another source, start from those values.

# Phase 4: Preview and Iterate

## Action 1
- For each crop, write the crop into `edit/edit.json`, then render a preview from the primary frame.
- `base_crops.<frame>` and a **layer** `crop` are integer source pixels, `x`, `y`, `w`, `h`.

```bash
uv run --no-project scripts/inspect/pip_crop_preview.py \
  edit/<source-group>/<source-name>-frame-1.png \
  --crop <x>,<y>,<w>,<h> \
  -o edit/<source-group>/<source-name>-<frame>-crop.png
```

- `<frame>` is `full`, `top`, `bottom`, or `pip`.
- Read the preview and adjust the crop when the framing is wrong.
- Recheck the other frames after every adjustment.
- For a later PIP crop of the same speaker, adjust only when the framing is very wrong.
- Cap at 3 passes.
- Update the crop in `edit/edit.json` after the last adjustment.

# Phase 5: Verify

## Action 1
- Every required `base_crops` entry exists.
- A `frame` of `{ "x", "y", "w", "h" }` that needs a crop has `crop` on its **layer**.
- Every crop uses integer `x`, `y`, `w`, and `h` and stays inside its source.
- Every `full` crop has the output aspect.
- Every `top` and `bottom` crop has that half's aspect, 32:9 or 9:8.
- Every `pip` crop has the `pip` aspect.
- A **layer** `crop` matches that **layer**'s frame aspect.
- Every crop has its preview.

# Phase 6: Respond

## Action 1
- Return each source, which crop was written, the coordinates, and whether the crop was face-aware or centered.

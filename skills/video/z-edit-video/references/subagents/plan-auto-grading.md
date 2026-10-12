# Context

Read `references/shared-context/concepts.md`.

## Source Types
- Only apply color grading to `head` **sources**.

## `grading_style` JSON Shape
- All keys optional.

```json
{
  "eq": {
    "contrast": 1.0,
    "brightness": 0.0,
    "saturation": 1.0,
    "gamma": 1.0
  },
  "color_balance": {
    "red_shadows": 0.0,
    "green_shadows": 0.0,
    "blue_shadows": 0.0,
    "red_midtones": 0.0,
    "green_midtones": 0.0,
    "blue_midtones": 0.0,
    "red_highlights": 0.0,
    "green_highlights": 0.0,
    "blue_highlights": 0.0
  },
  "curves": {
    "master": [
      { "input": 0.0, "output": 0.0 },
      { "input": 0.25, "output": 0.25 },
      { "input": 0.75, "output": 0.75 },
      { "input": 1.0, "output": 1.0 }
    ]
  }
}
```

- `eq`: ffmpeg `eq` knobs, omit keys you are not changing.
- `color_balance`: ffmpeg `colorbalance` (shadows / midtones / highlights per channel), typical values stay near `±0.05`.
- `curves.master`: list of `{input, output}` points in `[0, 1]`, sorted by `input`, identity is a straight diagonal.

# Workflow

## Get Source Context
- `ffprobe` the **source** (resolution, `color_transfer` / range if present) and use that context when planning color grading.

## Create Grading Options
- Produce 3 graded looks you invent from what the footage needs.
- Use the `grading_style` json shape.
- Labels are yours; keep them short and stable for filenames.

## Create Grading Preview
- Read `references/create-artifacts/create-grade-preview.md`.
- Follow the steps within to create grading previews for each look.
- Each preview is the single `original.png` still, graded.
- Extra sample frames stay out of `edit/grading-previews/`.

## Iterate
- For each look.
  - Read the preview image.
  - Decide if one knob should move.
  - Update the `grading_style` json and create a new preview.
- Change one thing per iteration.
- Stop when it looks right.
- Do at most 3 iterations per look.

## Save grading_style
- Save the final `grading_style` json for each option under `edit/grading-previews/<grading-style-name>.json`.

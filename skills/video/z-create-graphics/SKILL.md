---
name: z-create-graphics
description: Create or edit an ordered set of graphics, each an animation or an image, for an existing video plan and render verified files
---

# Global Context

## Context Skills
- Run `/z-task-skill-structure`.

## Purpose
- Create formed graphics jobs for an existing video plan.

## HyperFrames Skills
- Load and follow these skills for their domains.
    - `/hyperframes-core` for the composition HTML contract.
    - `/hyperframes-animation` for motion using 2–4 rules and GSAP by default.
    - `/hyperframes-creative` for brand, house style, video composition and design adherence.
    - `/hyperframes-cli` for lint, check and render.
- Skip `/hyperframes-animation` when every graphic is an `image`.
- Do not run `/hyperframes`.
- Do not run an intent interview, route table, `BRIEF.md`, Studio preview or approval gate.
- Skip HyperFrames previews and approval gates.

## Project Structure
```text
<output_dir>/
├── frame.md
├── <graphic_number>-graphic-<graphic_name>/
│   ├── hyperframes.json
│   └── index.html
└── <graphic_number>-graphic-<graphic_name>.mp4, .webm, or .png
```

# Phase 1: Setup

## Action 1. Inputs
- Prompt the user for each input if it was not provided.
    - `mode` (required).
        - Options: `create` or `edit`.
    - `video_description` (required).
    - `graphics_style_guide`.
        - Required when `mode` is `create`.
        - Options: File names under `configs/*`, an explicit file path, or "create new".
    - `orientation` (required).
        - Options: `landscape` or `portrait`.
    - `resolution` (required).
        - Options: `HD` or `4K`.
    - `graphics` (required).
        - Ordered list of graphics.
        - Each graphic has.
            - `graphic_number`.
            - `graphic_name`.
            - `graphic_type`.
                - Options: `animation` or `image`.
            - `graphic_duration` (as an `HH:MM:SS.ss` string, seconds, or minutes).
                - Omitted for an `image`.
            - `graphic_description`.
            - `text_elements`.
                - Each piece of text the graphic shows, keyed by its role.
            - `frame`.
                - `full`, or `{ "x", "y", "w", "h" }` as fractions of the output frame.
        - Each graphic being edited also has `graphic_feedback`.
    - `output_dir`.
        - Default: `edit/graphics`.

## Action 2. Graphics Style Guide
- Skip this action when `mode` is `edit`.
- If `graphics_style_guide` is "create new".
    - Read `references/create-graphics-style-guide.md` for creation instructions.
    - Ask the user for a name for the new config, and for any reference files to model it on.
    - Ask clarifying questions until you can write the config.
    - Write the config following the creation instructions.
    - Show the user the new config, and revise it until they approve.
    - Use the new config name as `graphics_style_guide`.
- If `graphics_style_guide` is a file name, resolve it from `configs/<graphics_style_guide>.md`.
- If `graphics_style_guide` is an explicit path, use it as written.

## Action 3. Environment
- Verify Node.js 22+ is on `PATH`.
- Verify `ffprobe` is on `PATH`.

# Phase 2: Project Setup

## Action 1. Initialize
- Create a project for each graphic.
- Skip a graphic whose `<output_dir>/<graphic_number>-graphic-<graphic_name>/hyperframes.json` exists.

```bash
mkdir -p <output_dir>
npx --yes hyperframes init <output_dir>/<graphic_number>-graphic-<graphic_name> --example blank --non-interactive --skip-skills --resolution <orientation>
```

## Action 2. Apply Style Guide
- Skip when `mode` is `edit`.
- Skip if `<output_dir>/frame.md` exists.
- Copy `graphics_style_guide` to `<output_dir>/frame.md`.

# Phase 3: Create or Edit Graphics

## Phase Context
- Work on one graphic at a time in the order provided.
- Finish authoring, checking and rendering before starting the next graphic.
- Run HyperFrames commands from `<output_dir>`.

## Action 1. Author

### Action Context
- Author each graphic in its project's `index.html`.
- The output size is.
    - Landscape HD: 1920×1080.
    - Landscape 4K: 3840×2160.
    - Portrait HD: 1080×1920.
    - Portrait 4K: 2160×3840.
- A graphic fills its `frame`.
    - A `full` canvas is the HD output size.
    - A `{ "x", "y", "w", "h" }` canvas is that box in pixels: `w` times the output width by `h` times the output height, each rounded to an even number.
        - Ex. `w` 0.4 on a 3840 wide output is 1536 pixels wide.
- When other layers sit behind the graphic, it is an overlay graphic. Otherwise it is a full graphic.
- An overlay graphic leaves pixels that should show the layers under it transparent.
- Show each `text_elements` value word for word, as its own element styled for its role.
- When `resolution` is `4K`, render a `full` graphic with `--resolution landscape-4k` or `portrait-4k`.
- Treat `<output_dir>/frame.md` as the brand source.
- Use its colors and fonts verbatim.
- Do not select a frame preset or invent additional colors.
- Never use a gradient background.
    - Fill an opaque background with one solid color from `frame.md`.
- Set an `animation`'s duration to its `graphic_duration`.
- An `image` has no motion, a duration of one frame, and `data-no-timeline` on its root.
- Pass the graphic's project folder, `<graphic_number>-graphic-<graphic_name>`, to every HyperFrames command.
- Render an `animation` that is a full graphic to `<graphic_number>-graphic-<graphic_name>.mp4`.
- Render an `animation` that is an overlay graphic to `<graphic_number>-graphic-<graphic_name>.webm` with transparency.
- Render an `image` with `--format png-sequence` to a temporary folder, move its first frame to `<graphic_number>-graphic-<graphic_name>.png`, and delete the folder.

### A. Create
- When `mode` is `create`, write each graphic's `index.html` from its `graphic_description` and `text_elements`.
- Follow `/hyperframes-cli` for lint, check and render.

### B. Edit
- When `mode` is `edit`, update each graphic's `index.html` from its `graphic_feedback`.
- Follow `/hyperframes-cli` for lint, check and render.

# Phase 4: Respond

- Return each generated file path, and each `animation`'s duration, to the caller.

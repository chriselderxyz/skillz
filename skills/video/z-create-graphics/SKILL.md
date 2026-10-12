---
name: z-create-graphics
description: Create or edit an ordered set of motion graphics for an existing video plan and render verified video files
---

# Global Context

## Context Skills
- Run `/z-task-skill-structure`.

## Purpose
- Create formed motion-graphics jobs for an existing video plan.

## HyperFrames Skills
- Load and follow these skills for their domains.
    - `/hyperframes-core` for the composition HTML contract.
    - `/hyperframes-animation` for motion using 2–4 rules and GSAP by default.
    - `/hyperframes-creative` for brand, house style, video composition and design adherence.
    - `/hyperframes-cli` for lint, check and render.
- Do not run `/hyperframes`.
- Do not run an intent interview, route table, `BRIEF.md`, Studio preview or approval gate.
- Skip HyperFrames previews and approval gates.

## Project Structure
```text
<output_dir>/
├── hyperframes.json
├── frame.md
├── index.html
├── compositions/<graphic_number>-graphic-<graphic_name>.html
└── <graphic_number>-graphic-<graphic_name>.mp4 or .webm
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
            - `graphic_duration` (as an `HH:MM:SS.ss` string, seconds, or minutes).
            - `graphic_description`.
            - `frame`.
                - `full`, or `{ "x", "y", "w", "h" }` as fractions of the output frame.
        - Each graphic being edited also has `graphic_feedback`.
    - `output_dir`.
        - Default: `edit/graphics`.

## Action 2. Graphics Style Guide
- Skip this action when `mode` is `edit`.
- If `graphics_style_guide` is "create new".
    - Use the `/z-create-config` skill to create a new config for this skill.
    - Read `references/create-graphics-style-guide.md` for guidelines.
    - Use the new config name as `graphics_style_guide`.
- If `graphics_style_guide` is a file name, resolve it from `configs/<graphics_style_guide>.md`.
- If `graphics_style_guide` is an explicit path, use it as written.

## Action 3. Environment
- Verify Node.js 22+ is on `PATH`.
- Verify `ffprobe` is on `PATH`.

# Phase 2: Project Setup

## Action 1. Initialize
- Skip when `mode` is `edit`.
- Skip if `<output_dir>/hyperframes.json` exists.

```bash
mkdir -p <output_dir>
npx --yes hyperframes init <output_dir> --example blank --non-interactive --skip-skills --resolution <orientation>
```

## Action 2. Apply Style Guide
- Skip when `mode` is `edit`.
- Skip if `<output_dir>/frame.md` exists.
- Copy `graphics_style_guide` to `<output_dir>/frame.md`.

# Phase 3: Create or Edit Graphics

## Phase Context
- Work on one graphic at a time in the order provided.
- Finish authoring, checking, rendering and verification before starting the next graphic.
- Run HyperFrames commands from `<output_dir>`.

## Action 1. Author

### Action Context
- Each graphic is its own composition.
- Keep `index.html` as the unused blank scaffold.
- A graphic fills the frame. Author that canvas at 1920×1080 for landscape or 1080×1920 for portrait.
- When other layers sit behind the graphic, it is an overlay. An overlay is that same full frame, but leaves pixels that should show the layers under it transparent.
- When `resolution` is `4K`, author at the HD pixel size and render with `--resolution landscape-4k` or `portrait-4k`.
- Do not set composition dimensions to 4K.
- Treat `<output_dir>/frame.md` as the brand source.
- Use its colors and fonts verbatim.
- Do not select a frame preset or invent additional colors.
- Never use a gradient background.
    - Fill an opaque background with one solid color from `frame.md`.
- Set the duration to the graphic's `graphic_duration`.
- Pass `-c compositions/<graphic_number>-graphic-<graphic_name>.html` to every composition command.
- Render a graphic that is the picture to `<graphic_number>-graphic-<graphic_name>.mp4`.
- Render an overlay to `<graphic_number>-graphic-<graphic_name>.webm` with transparency.

### A. Create
- When `mode` is `create`, create each composition from its `graphic_description`.
- Follow `/hyperframes-cli` for lint, check and render.

### B. Edit
- When `mode` is `edit`, update each composition from its `graphic_feedback`.
- Follow `/hyperframes-cli` for lint, check and render.

## Action 2. Verify
- Run `ffprobe` on each rendered graphic before starting the next.
- Verify the rendered duration equals the graphic's `graphic_duration`.
- Verify the graphic matches `orientation` and `resolution`.
    - Landscape HD: 1920×1080.
    - Landscape 4K: 3840×2160.
    - Portrait HD: 1080×1920.
    - Portrait 4K: 2160×3840.
- Verify an overlay's pixel format is `yuva420p`.
- Fix and rerender any graphic that fails verification.

# Phase 4: Respond

## Action 1
- Return each generated file path and duration to the caller.

# Context

Read `references/shared-context/concepts.md`

## Purpose
This is a formed motion-graphics job inside an existing edit, not a new HyperFrames video

## Skills
- Do not run `/hyperframes` — no intent interview, no route table, no `BRIEF.md`, no Studio preview gate
- Load these skills and follow them for their domains:
    - `/hyperframes-core` — composition HTML contract (`data-*`, tracks, sized root)
    - `/hyperframes-animation` — motion (pick 2–4 rules; GSAP default)
    - `/hyperframes-creative` — `frame.md` is brand; read house-style and video-composition before writing HTML; run design-adherence after
    - `/hyperframes-cli` — `lint`, `check`, `render` (skip `preview` and the approval wait)
- Work on one graphic at a time. Finish author, check, render, and verify before starting the next. Serial builds keep each graphic consistent with the one before it

## Orientation and Resoulution
- Read `edit/edl.json` for orientation and resolution
    - `video_type.orientation`
    - `video_type.resolution`

## Hyperframes Project Structure
```
edit/graphics/
├── hyperframes.json
├── frame.md
├── index.html
├── compositions/<n>-graphic-<graphic-name>.html
└── <n>-graphic-<graphic-name>.mp4               or .webm when it needs alpha
```

# Phase 1: Project Setup

## Init Project
- All graphics share one HyperFrames project at `edit/graphics/`
- Init once into `edit/graphics`. Skip init if `edit/graphics/hyperframes.json` already exists (`init` refuses a non-empty directory)

```bash
mkdir -p edit/graphics
npx --yes hyperframes init edit/graphics --example blank --non-interactive --skip-skills --resolution <landscape|portrait>
```

## Copy Style Guide
- Copy the style guide from the path given to you to `edit/graphics/frame.md` so `/hyperframes-creative` sees this session's brand

# Phase 2: Create Each Graphic

## Hyperframes Guidelines
- Each graphic is its own composition file, rendered to its own **clip**
- `index.html` stays the unused blank scaffold — do not mount graphics as scenes on one timeline
- Author the composition canvas at HD (`data-width` / `data-height` 1920×1080 landscape or 1080×1920 portrait)
- When `video_type.resolution` is `4K`, render with `--resolution landscape-4k` or `portrait-4k` so Chrome captures the HD canvas at 2× (3840×2160 or 2160×3840)
- Do not set `data-width` / `data-height` to 4K — type sized for HD would look tiny
- Treat `edit/graphics/frame.md` as brand truth. Quote its hex and fonts verbatim. Do not pick a frame-preset or invent extra colors
- Duration of a graphic is the **edit clock** window (`end` - `start`)

## Create Graphics
For each graphic, in the order given by the caller:
- Author `compositions/<n>-graphic-<graphic-name>.html` using `/hyperframes-core`, `/hyperframes-animation`, and `/hyperframes-creative`
- Then follow `/hyperframes-cli` for lint → check → render, run from `edit/graphics` (cd once after Phase 1)
- Skip preview
- Do not wait for approval
- Always pass `-c compositions/<n>-graphic-<graphic-name>.html` so you do not render `index.html`
- Use `-o <n>-graphic-<graphic-name>.mp4`, or `--format webm -o <n>-graphic-<graphic-name>.webm` when the graphic sits over footage and needs transparency
- A full-frame cut-away that replaces the footage does not

## Verify
- `ffprobe` each render for duration and dimensions before starting the next graphic
    - render length should match the **edit clock** window exactly (`end` - `start`)
    - pixels must match the video type: landscape HD 1920×1080, landscape 4K 3840×2160, portrait HD 1080×1920, portrait 4K 2160×3840

# Phase 3: Respond
- Return a list of generated files + their durations to the caller

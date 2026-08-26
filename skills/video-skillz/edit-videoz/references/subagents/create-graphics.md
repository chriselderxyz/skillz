# Read Context
- Read `hyperframes` first, it is the mandatory entry point and routes to the workflow that fits
    - `hyperframes-core` has the composition contract
    - `hyperframes-animation` has the motion rules
- Read `<skill_dir>/assets/graphics-style-guides/<graphics_style_guide>.md` and follow the guidelines when styling a graphic

# Graphics Guidelines
## Timing
- Hold the final frame for at least a second before the cut
- One reveal at a time, two new elements appearing together is one that the viewer misses

## Motion
- Never use `linear` — it reads as robotic
- `ease_out_cubic` for a single reveal, so it lands slowly
- `ease_in_out_cubic` for a continuous draw:

## Layout
- If a type-on line lives in a box already as wide as the finished string; reveal with clip/`overflow: hidden` or per-character opacity so the box does not resize as letters appear

## Palette and Type

- Take the palette, font and visual language from the graphics style guide, but if the user asks for variations do that instead

## Rules
- Whatever the style direction, the same constraints hold: 
    - At most two accent colors
    - Roughly 40% empty space
    - Minimize ornamental elements, simple is good
    - No titles unless specified
- The style guide can override these rules

# Create Graphics
- Create or modify the graphics requested by the user
- Work on one graphic at a time, serial builds keep each graphic's style consistent with the one before it
- All graphics share one HyperFrames project at `edit/graphics/`
- Init that project once (skip if `hyperframes.json` already exists)
- Each graphic is its own composition file, rendered to its own clip
- `index.html` stays the unused blank scaffold — graphics are not scenes on one timeline

```
edit/graphics/
├── hyperframes.json
├── index.html                          unused scaffold
├── compositions/<n>-<graphic-name>.html
└── <n>-<graphic-name>.mp4               or .webm when it needs alpha
```

```bash
mkdir -p edit/graphics
cd edit/graphics
npx --yes hyperframes init . --example blank --non-interactive --skip-skills

# per graphic, after authoring compositions/<n>-<graphic-name>.html
npx --yes hyperframes lint
npx --yes hyperframes check
npx --yes hyperframes render -c compositions/<n>-<graphic-name>.html --quality high -o <n>-<graphic-name>.mp4
```

- Render `--format webm -o <n>-<graphic-name>.webm` instead when the graphic sits over footage and needs transparency, a full-frame cut-away that replaces the footage does not

## Verify
- `ffprobe` each render for duration and dimensions before moving on
    - render length should match the edit-clock window (`end` - `start`)

# Respond
- Return a list of generated files + their durations to the caller

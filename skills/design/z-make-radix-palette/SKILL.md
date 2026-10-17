---
name: z-make-radix-palette
description: Use to generate Radix-style light and dark brand and neutral color ramps from light and dark seed HEX colors
---

# Global Context

## Paths
- Resolve the skill directory as `<skill_dir>`.

# Phase 1: Setup

## Action 1. Inputs
- Collect the following inputs.
    - `light_seed` (required).
        - A six-digit HEX color for the light mode brand ramps.
    - `dark_seed`:
        - A six-digit HEX color for the dark mode brand ramps.
        - Default to `light_seed`.
    - `light_gray`.
        - An optional six-digit HEX color for the light mode neutral ramps.
        - Derive it from `light_seed` when omitted.
    - `dark_gray`.
        - An optional six-digit HEX color for the dark mode neutral ramps.
        - Derive it from `dark_seed` when omitted.
    - `light_background`.
        - A six-digit HEX color.
        - Default to `#FFFFFF`.
    - `dark_background`.
        - A six-digit HEX color.
        - Default to `#141414`.
- Reject any input that is not a valid six-digit HEX color.

## Action 2. Node.js
- Run `node --version`.
- Require Node.js 18 or newer.
- If Node.js is unavailable or older than version 18, stop and ask the user to update it.

## Action 3. Dependencies
- If `<skill_dir>/node_modules` does not exist, run `npm --prefix "<skill_dir>" install`.

# Phase 2: Pre-Generation

## Action 1. Select Grays
- Use each provided gray directly.
- If either gray was omitted.
    - Run `"<skill_dir>/node_modules/.bin/tsx" "<skill_dir>/scripts/makeGrays.ts" --light-seed "<light_seed>" --dark-seed "<dark_seed>"`.
    - Use `light_gray` or `dark_gray` from the script output for each omitted gray.
    - Keep the default knobs unless the resulting color does not read as a neutral tinted with the seed's hue.
    - Tune gray selection when required by passing any of.
        - `--chroma-ratio <0-to-1>`.
        - `--max-chroma <0-to-0.4>`.
        - `--lightness <0-to-1>`.

## Action 2. Select Brand Color Name
- Select a concise common name for the seeds' hue.
- Use lowercase letters, with hyphens when the name has more than one word.

# Phase 3: Generate

- Use the current working directory as `<output_directory>`.
- Run `"<skill_dir>/node_modules/.bin/tsx" "<skill_dir>/scripts/generate.ts" --light-seed "<light_seed>" --brand-color-name "<brand_color_name>" --light-gray "<light_gray>" --dark-gray "<dark_gray>" --light-background "<light_background>" --dark-background "<dark_background>" --output-directory "<output_directory>"`.
- When `dark_seed` is set, include `--dark-seed "<dark_seed>"` in that command.

# Phase 4: Verify and Respond

- Report the output name.
- Report the generated JSON path.

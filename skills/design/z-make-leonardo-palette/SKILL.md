---
name: z-make-leonardo-palette
description: Use to generate contrast-targeted light and dark brand and neutral color ramps with Adobe Leonardo
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
    - `secondary_color` (optional).
        - A six-digit HEX color.
        - A second source color for the brand ramp.
        - Leonardo interpolates between each seed and `secondary_color`, which shifts the hue along the ramp.
        - Explicitly ask for this when a single hue goes muddy in light or dark steps, such as yellow.
    - `light_gray` (optional).
        - A six-digit HEX color.
        - Tints the light mode neutral ramp.
        - When omitted, the script derives a muted mid gray from the light seed's hue.
    - `dark_gray` (optional).
        - A six-digit HEX color.
        - Tints the dark mode neutral ramp.
        - When omitted, the script derives a muted mid gray from the dark seed's hue.
    - `light_background`.
        - A six-digit HEX color.
        - Default to `#FFFFFF`.
    - `dark_background`.
        - A six-digit HEX color.
        - Default to `#141414`.
    - `vibrant`:
        - A boolean.
        - When true, each brand step gets the color strength of a Radix ramp for the seed's hue.
        - Default to false.
    - `contrast_targets`:
        - Options: File names under `configs/contrast-targets/*` or "create new".
        - Default to `default`.
- If `contrast_targets` is "create new".
    - Read `references/create-contrast-targets.md` for creation instructions.
    - Ask the user for a name for the new config, and for any reference files to model it on.
    - Ask clarifying questions until you can write the config.
    - Write the config to `configs/contrast-targets/<name>.json`.
    - Show the user the new config, and revise it until they approve.
    - Use the new config for `contrast_targets`.

## Action 2. Node.js
- Run `node --version`.
- Require Node.js 18 or newer.
- If Node.js is unavailable or older than version 18, stop and ask the user to update it.

## Action 3. Dependencies
- If `<skill_dir>/node_modules` does not exist, run `npm --prefix "<skill_dir>" install`.

# Phase 2: Pre-Generation

- Choose a concise common name for the seeds' hue.
- Use lowercase letters, with hyphens when the name has more than one word.

# Phase 3: Generate

- Use the current working directory as `<output_directory>`.
- Run `"<skill_dir>/node_modules/.bin/tsx" "<skill_dir>/scripts/generate.ts" --light-seed "<light_seed>" --brand-color-name "<brand_color_name>" --light-background "<light_background>" --dark-background "<dark_background>" --contrast-targets "<skill_dir>/configs/contrast-targets/<contrast_targets>.json" --output-directory "<output_directory>"`.
- When `dark_seed` is set, include `--dark-seed "<dark_seed>"` in that command.
- When `secondary_color` is set, include `--secondary-color "<secondary_color>"` in that command.
- When `light_gray` is set, include `--light-gray "<light_gray>"` in that command.
- When `dark_gray` is set, include `--dark-gray "<dark_gray>"` in that command.
- When `vibrant` is true, include `--vibrant` in that command.

# Phase 4: Respond

- Report the output name.
- Report the generated JSON path.

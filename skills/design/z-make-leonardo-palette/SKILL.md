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
    - `brand_color` (required).
        - A six-digit HEX color.
    - `secondary_color` (optional).
        - A six-digit HEX color.
        - A second source color for the brand ramp.
        - Leonardo interpolates between `brand_color` and `secondary_color`, which shifts the hue along the ramp.
        - Explicitly ask for this when a single hue goes muddy in light or dark steps, such as yellow.
    - `gray_color` (optional).
        - A six-digit HEX color.
        - Tints the neutral ramp.
        - When omitted, the script derives a muted mid gray from the brand hue.
    - `light_background`.
        - A six-digit HEX color.
        - Default to `#FFFFFF`.
    - `dark_background`.
        - A six-digit HEX color.
        - Default to `#111111`.

## Action 2. Node.js
- Run `node --version`.
- Require Node.js 18 or newer.
- If Node.js is unavailable or older than version 18, stop and ask the user to update it.

## Action 3. Dependencies
- If `<skill_dir>/node_modules` does not exist, run `npm --prefix "<skill_dir>" install`.

# Phase 2: Pre-Generation

- Choose a concise common name for the `brand_color` hue.
- Use lowercase letters, with hyphens when the name has more than one word.

# Phase 3: Generate

- Use the current working directory as `<output_directory>`.
- Run `"<skill_dir>/node_modules/.bin/tsx" "<skill_dir>/scripts/generate.ts" --brand-color "<brand_color>" --brand-color-name "<brand_color_name>" --light-background "<light_background>" --dark-background "<dark_background>" --output-directory "<output_directory>"`.
- When `secondary_color` is set, include `--secondary-color "<secondary_color>"` in that command.
- When `gray_color` is set, include `--gray-color "<gray_color>"` in that command.

# Phase 4: Respond

- Report the output name.
- Report the generated JSON path.

---
name: z-make-radix-palette
description: Use to generate Radix-style light and dark brand and neutral color ramps from a brand HEX color
---

# Global Context

## Paths
- Resolve the skill directory as `<skill_dir>`.

# Phase 1: Setup

## Action 1. Inputs
- Collect the following inputs.
    - `brand_color` (required).
        - A six-digit HEX color.
    - `gray_color`.
        - An optional six-digit HEX color.
        - Derive it from `brand_color` when omitted.
    - `light_background`.
        - A six-digit HEX color.
        - Default to `#FFFFFF`.
    - `dark_background`.
        - A six-digit HEX color.
        - Default to `#111111`.
- Reject any input that is not a valid six-digit HEX color.

## Action 2. Node.js
- Run `node --version`.
- Require Node.js 18 or newer.
- If Node.js is unavailable or older than version 18, stop and ask the user to update it.

## Action 3. Dependencies
- If `<skill_dir>/node_modules` does not exist, run `npm --prefix "<skill_dir>" install`.

# Phase 2: Pre-Generation

## Action 1. Select Gray
- If `gray_color` was provided, use it directly.
- If `gray_color` was omitted.
    - Run `"<skill_dir>/node_modules/.bin/tsx" "<skill_dir>/scripts/selectGray.ts" --brand-color "<brand_color>"`.
    - Use `gray_color` from the script output.
    - Keep the default knobs unless the resulting color does not read as a neutral tinted with the brand hue.
    - Tune gray selection when required by passing any of.
        - `--chroma-ratio <0-to-1>`.
        - `--max-chroma <0-to-0.4>`.
        - `--lightness <0-to-1>`.

## Action 2. Select Brand Color Name
- Select a concise common name for the `brand_color` hue.
- Use lowercase letters, with hyphens when the name has more than one word.

# Phase 3: Generate

- Use the current working directory as `<output_directory>`.
- Run `"<skill_dir>/node_modules/.bin/tsx" "<skill_dir>/scripts/generate.ts" --brand-color "<brand_color>" --brand-color-name "<brand_color_name>" --gray-color "<gray_color>" --light-background "<light_background>" --dark-background "<dark_background>" --output-directory "<output_directory>"`.

# Phase 4: Verify and Respond

- Report the output name.
- Report the generated JSON path.

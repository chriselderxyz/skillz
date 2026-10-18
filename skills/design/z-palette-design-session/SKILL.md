---
name: z-palette-design-session
description: Use for interactive design sessions with the user to come up with app palette variations
---

# Global Context

## Paths
- Resolve the skill directory as `<skill_dir>`.
- Resolve the **token mapping** path as `<token_mapping_path>`: `<skill_dir>/configs/token-mappings/<token_mapping>.json`.

## Definitions
- **Token Mapping**: The config selected by `token_mapping`.
- **Palette File**: `palettes.json` in the working directory.
- **Light Seed** and **Dark Seed**: A hue's seeds for light and dark mode, both the hue's one seed when `primary_text_contrast` is false.

# Phase 1: Setup

## Action 1. Inputs
- Collect the following inputs:
    - `generators`:
        - Options: `radix`, `leonardo`.
        - Default to `radix` and `leonardo`.
        - Use them for every palette unless the user asks for different generators on a palette.
    - `token_mapping`:
        - Options: File names under `configs/token-mappings/*` or "create new".
        - Default to `default`.
    - `primary_text_contrast`:
        - Options: true, false.
        - Default to false.
        - When true, each hue gets a light seed and a dark seed, so `primary` meets text contrast against the background in both modes.
- If `token_mapping` is "create new":
    - Read `references/create-configs/create-token-mapping.md` for creation instructions.
    - Ask the user for a name for the new **token mapping**, and for any reference files to model it on.
    - Ask clarifying questions until you can write it.
    - Write it to `<skill_dir>/configs/token-mappings/<name>.json`.
    - Use `<name>` as `token_mapping`.

## Action 2. Node.js
- Run `node --version`.
- Require Node.js 18 or newer.
- If Node.js is unavailable or older than version 18, stop and ask the user to update it.

## Action 3. Dependencies
- If `<skill_dir>/node_modules` does not exist, run `npm --prefix "<skill_dir>" install`.

# Phase 2: Generate Palettes

## Action 1. Select Brand Hue
- EVERY palette starts with a brand hue.
- Select an OKLCH hue according to the users input.
- When the user gives a color, use its `hue` from `"<skill_dir>/node_modules/.bin/tsx" "<skill_dir>/scripts/colors/oklch.ts" --color "<color>"`.

## Action 2. Select Signal Hues
- EVERY palette needs a hue for:
    - Destructive signal hue (typically red).
    - Warning signal hue (typically yellow, but can be orange if yellow clashes).
    - Success signal hue (typically green).
- Keep each signal hue distinct from the brand hue and the other signal hues.
- Also consider how the signal hues will look aesthetically against the brand hue.

## Action 3. Make Seeds
- When `primary_text_contrast` is true, make the seeds following Phase 1 of `references/two-seeds.md`.
- Otherwise, for the brand hue and each signal hue:
    - Select a relative chroma, from 0 to 1, the seed's chroma as a share of the most chroma sRGB holds.
    - Select a lightness for the seed:
        - Most brands: a deep color that carries white text.
        - Bright brands, such as sky blue, lime, or yellow: a light color that carries black text.
    - Make the seed with `"<skill_dir>/node_modules/.bin/tsx" "<skill_dir>/scripts/colors/makeSeeds.ts" --hue "<hue>" --relative-chroma "<relative_chroma>" --seed-lightness "<seed_lightness>"`.
        - For the user's color, pass `--seed "<color>"` in place of `--hue`, `--relative-chroma`, and `--seed-lightness`.
    - When the seed fails, select a new lightness, starting from its `suggestion`, and make it again.
    - Use `color` from the output.

## Action 4. Select Background Colors
- Select a background color for both light and dark modes.
- Options
    - Hue Match
        - Hue is the brand hue.
        - Chroma roughly 2-8% of the `chroma` of the mode's brand seed
            - Tint shows up quickly on near-white, so lower end for light mode.
            - Dark mode can tolerate higher chroma.
            - Blues and purples tolerate the high end.
            - Yellows oranges, and greens look muddy or dingy fast, so keep them lower.
        - Lightness.
            - Light mode 0.98-0.995 (typically start at 0.995).
            - Dark mode: 0.15 to 0.25, or 0.12 to 0.15 when `generators` includes `radix`.
    - The generator defaults: `#FFFFFF` for light mode and `#141414` for dark mode.

## Action 5. Check Seeds
- When `primary_text_contrast` is true, check the seeds following Phase 2 of `references/two-seeds.md`.

## Action 6. Select Grays
- Run `"<skill_dir>/node_modules/.bin/tsx" "<skill_dir>/scripts/colors/makeGrays.ts" --light-seed "<light_seed>" --dark-seed "<dark_seed>"` with the brand hue's **light seed** and **dark seed**.
- Use `light_gray` and `dark_gray` from the output as the palette's grays, or the grays the user gives.

## Action 7. Make Palettes
- Create as many palettes as the user requests.
- Make each palette with every generator in `generators`:
    - Give every generator the same inputs: the seeds, the light and dark backgrounds, and the grays.
    - Pass each ramp's **light seed** as `light_seed`, its **dark seed** as `dark_seed`, and the palette's grays as `light_gray` and `dark_gray`.
- Use a subagent to run each generator skill.
- For `radix`:
    - Use the `/z-make-radix-palette` skill.
- For `leonardo`:
    - Use the `/z-make-leonardo-palette` skill.
    - Pass `secondary_color` when the Leonardo skill calls for one.
    - Pass `vibrant` as true.
- Make each signal ramp with its palette's generator unless the user asks for a different one.

## Action 8. Check Neutrals
- Confirm the neutral ramp has no steps that are too strongly tinted:
- If they do, select new grays with a lower `--chroma-ratio` and make that palette again.

## Action 9. Palette File
- Add an entry to the **palette file** for each palette and generator, following this example.
- Use the same `name` for every generator's entry of a palette.

```json
{
  "palettes": [
    {
      "name": "Rose",
      "generator": "radix",
      "description": "<Seed, background, and signal choices>",
      "suggested_brand": "<light or dark>",
      "brand": "<brand ramp output path>",
      "destructive": "<destructive ramp output path>",
      "warning": "<warning ramp output path>",
      "success": "<success ramp output path>"
    }
  ]
}
```

# Phase 3: Check Token Mapping

- Run `"<skill_dir>/node_modules/.bin/tsx" "<skill_dir>/scripts/pages/checkTokenMapping.ts" --palettes palettes.json --token-mapping "<token_mapping_path>"`.
- Tell the user about every entry in `failures`.
- Change the **token mapping** only when the user asks.

# Phase 4: Results Page

- Write a short session summary with the generators used, the palettes compared, and the key findings.
- Run `"<skill_dir>/node_modules/.bin/tsx" "<skill_dir>/scripts/pages/buildPage.ts" --page design-session --palettes palettes.json --token-mapping "<token_mapping_path>" --summary "<summary>" --output design-session.html`.

# Phase 5: Interactive Session

- Open `design-session.html`.
- Tell the user to review the output.
- Start an interactive session with the user providing feedback and requests:
    - Make any requested changes.
    - Run phases 2-4 again for any additional palettes the user requests.
    - For **token mapping** changes:
        - Edit the **token mapping** following `references/create-configs/create-token-mapping.md`, or create a new one with the Phase 1 "create new" steps when the user asks.
        - Run phases 3-4 again.

# Phase 6: Final Results

## Action 1. Build the Page
- Write a short summary that names the selected palette, its generator, the **token mapping**, and the palette's `seed_foreground` contrast from the latest `checkTokenMapping.ts` output.
- Run `"<skill_dir>/node_modules/.bin/tsx" "<skill_dir>/scripts/pages/buildPage.ts" --page export --palettes palettes.json --palette "<palette name>" --generator "<generator>" --token-mapping "<token_mapping_path>" --summary "<summary>" --output export.html`.

## Action 2. Deliver
- Tell the user to review `export.html`.

---
name: z-palette-design-session
description: Use for interactive design sessions with the user to come up with app palette variations
---

# Global Context

## Paths
- Resolve the skill directory as `<skill_dir>`.

# Phase 1: Setup

## Action 1. Inputs
- Prompt the user for each input if it was not provided.
    - `generator` (required).
        - Options: `radix`, `leonardo`.
        - Use it for every palette unless the user asks for a different generator on a palette.

## Action 2. Node.js
- Run `node --version`.
- Require Node.js 18 or newer.
- If Node.js is unavailable or older than version 18, stop and ask the user to update it.

## Action 3. Dependencies
- If `<skill_dir>/node_modules` does not exist, run `npm --prefix "<skill_dir>" install`.

# Phase 2: Generate Palettes

## Phase Context
- The text color on each seed MUST pass WCAG 4.5:1 and APCA Lc 75, if it does not, then pick a new seed.
    -  Measure each pair with `"<skill_dir>/node_modules/.bin/tsx" "<skill_dir>/scripts/contrast.ts" --text "<text>" --background "<background>"`.
    - `--text` is the text color.
    - `--background` is the seed color.
    - Compare APCA using the absolute value of `apca`.

## Action 1. Select Brand Seed
- EVERY palette starts with a brand seed.
- Select a brand ramp seed color according to the users input.
- Use a deep seed with white text, or a light seed with dark text.
    - Avoid mid-tone seeds unless explicitly asked (they typically do not reach Lc 75 with either text color).
    - White text is `#FFFFFF`.
    - Dark text is step 12 of the light neutral ramp, used in both modes.

## Action 2. Select Signal Color Seeds
- EVERY palette needs a seed for.
    - Destructive signal color (typically red).
    - Warning signal color (typically yellow, but can be orange if yellow clashes).
    - Success signal color (typically green).
- Consider contrast against the brand seed color and other signal colors when selecting the seed color for the signal ramps.
- Also consider how the signal colors will look aesthetically against the brand seed.

## Action 3. Select Background Colors
- Select a background color for both light and dark modes.
- Options.
    - Hue Match.
        - Hue is the same as the brand seed.
        - Chroma roughly 3-8% of the brand seed.
            - Tint shows up quickly on near-white, so lower end for light mode.
            - Dark mode can tolerate higher chroma.
            - Blues and purples tolerate the high end.
            - Yellows oranges, and greens look muddy or dingy fast, so keep them lower.
        - Lightness.
            - Light mode 0.98-0.995 (typically start at 0.995).
            - Dark mode: 0.15 to 0.25.
    - The generator defaults: `#FFFFFF` for light mode and `#111111` for dark mode.

## Action 4. Make Palettes
- Create as many palettes as the user requests.
- Use a subagent to run the generator skill.
- Pass the selected light and dark backgrounds.
- Pass `gray_color` when a custom gray was chosen.
- When `generator` is `radix`.
    - Use the `/z-make-radix-palette` skill.
- When `generator` is `leonardo`.
    - Use the `/z-make-leonardo-palette` skill.
    - Pass `secondary_color` when the Leonardo skill calls for one.
    - Record the input brand color as `seed`.
- Use the same generator for each signal ramp unless the user asks for a different one.
- If the brand seed does not meet its contrast targets against white or step 12 of the light neutral ramp, then go back to step 1 and select a new seed.
- If a signal seed does not meet its contrast targets against white or step 12 of the light neutral ramp, then go back to step 2 and select a new seed.

## Action 5. Check Neutrals
- Confirm the neutral ramp has no steps that are too strongly tinted.
    - If they do, regenerate with a custom gray.

# Phase 3: Select Design Tokens

## Phase Context
- Read `references/color-design-tokens.md` to get a list of the required design tokens.

## Action 1
- A full set of token values is needed for both light and dark mode.
- Get token values for each **token schema**.
- DO NOT modify the prebuilt mappings unless asked, even if contrast targets fail.
- If token pairs do not meet the contrast targets in `references/color-design-tokens.md` let the user know.
- If the user asks for it, design custom **token schema's** for this run.
- Validate contrast with `"<skill_dir>/node_modules/.bin/tsx" "<skill_dir>/scripts/contrast.ts" --text "<text>" --background "<background>"`.
    - `wcag` is the WCAG 2 contrast ratio.
    - `apca` is the signed APCA Lc.
    - Compare APCA using the absolute value of `apca`.
- For `on-seed`, use the text color chosen in the brand ramp seed check.
- For `black-or-white`, measure `#000000` and `#FFFFFF` on that token's fill.
    - A pair passes when `wcag` is at least 4.5 and the absolute value of `apca` is at least 60.
    - When both pass, the larger absolute `apca` is the resolved text color.

# Phase 4: Results Page

## Action 1
- Use assets/palette-results.html.
    - Its marker blocks (@@SUMMARY, @@PALETTE_DATA, @@SCHEMES).
    - The data format in the template comments.
    - Build it with a script that injects the data, rather than hand-editing HTML.
- Each palette object has the seed, gray, generators, backgrounds, ramps, alpha ramps, and signals.
- Leave wide gamut ramps out of this page.

# Phase 5: Interactive Session

## Action 1
- Open the HTML doc.
- Tell the user to review the output.
- Start an interactive session with the user providing feedback and requests.
    - Make any requested changes.
    - Run phases 2-4 again for any additional palettes the user requests.

# Phase 6: Final Results

## Action 1. Build the Page
- Use assets/palette-selected.html.
    - Its marker blocks (@@SUMMARY, @@PALETTE, @@SCHEME).
    - The data format in the template comments.
    - Build it with a script that injects the data, rather than hand-editing HTML.
- @@PALETTE is the one selected palette object.
- Include wide gamut ramps when the generator produced them, and omit them when the generator did not produce them.
- @@SCHEME is the one selected scheme object.
- @@SUMMARY names the selected palette, the selected scheme, and the contrast result.
- Measure that contrast result with `"<skill_dir>/node_modules/.bin/tsx" "<skill_dir>/scripts/contrast.ts" --text "<text>" --background "<background>"`.
    - Report `wcag` and the absolute value of `apca` for the selected palette's on-seed text on the brand seed.

## Action 2. Deliver
- Tell the user to review the HTML output.

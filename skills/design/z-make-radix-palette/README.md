# What is This?

Generates Radix-style color ramps for both light and dark mode, from a brand seed.
Uses the [Radix Colors custom palette generator](https://www.radix-ui.com/colors/custom), with some changes so the ramps pass contrast minimums (see [Generator Changes](#generator-changes)).

Each mode gets:

- A 12-step brand ramp, built from the seed.
- A 12-step neutral ramp, tinted by the gray.
- Alpha, wide gamut, and wide gamut alpha versions of both ramps.

[z-palette-design-session](../z-palette-design-session) runs this skill to build its palettes. You can also run it on its own.

# Install the Skill

```sh
npx skills add chriselderxyz/skillz --skill z-make-radix-palette
```

# Inputs

| Input              | Options       | Default                   | Description                                                             |
| ------------------ | ------------- | ------------------------- | ----------------------------------------------------------------------- |
| `light_seed`       | Six-digit HEX | Required                  | The brand color for light mode. Becomes step 9 of the light brand ramp. |
| `dark_seed`        | Six-digit HEX | `light_seed`              | The brand color for dark mode. Becomes step 9 of the dark brand ramp.   |
| `light_gray`       | Six-digit HEX | Derived from `light_seed` | Tints the light mode neutral ramp.                                      |
| `dark_gray`        | Six-digit HEX | Derived from `dark_seed`  | Tints the dark mode neutral ramp.                                       |
| `light_background` | Six-digit HEX | `#FFFFFF`                 | The light mode page background.                                         |
| `dark_background`  | Six-digit HEX | `#141414`                 | The dark mode page background.                                          |

The agent also picks a brand color name for the seeds' hue, like `indigo`, for the output file name.

## Derived Grays

When a gray is omitted, `scripts/makeGrays.ts` makes one with the seed's hue and a share of its chroma.
The agent only changes these knobs when the gray doesn't read as a neutral tinted with the seed's hue.

| Knob             | Default | Description                                      |
| ---------------- | ------- | ------------------------------------------------ |
| `--chroma-ratio` | `0.12`  | Share of the seed's OKLCH chroma the gray keeps. |
| `--max-chroma`   | `0.025` | Cap on the gray's OKLCH chroma.                  |
| `--lightness`    | `0.55`  | The gray's OKLCH lightness.                      |

# Outputs

One JSON file in the working directory, named `<brand-color-name>-<seeds>-<grays>.json`.
The dark seed and dark gray are only in the name when they differ from the light ones.
For example: `indigo-3e63dd-868a94.json`.

| Key                                   | Contents                                                                                                   |
| ------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| `name`                                | The file name without `.json`.                                                                             |
| `inputs`                              | The seeds, grays, and backgrounds used.                                                                    |
| `light.background`, `dark.background` | The mode's page background.                                                                                |
| `<mode>.brand.radix_brand_foreground` | Text on the seed: white, or black when white falls below APCA Lc 40.                                       |
| `<mode>.<ramp>.base_ramp`             | 12 steps. Each has its `step`, `role`, `color` (HEX), and `contrast`.                                      |
| `<mode>.<ramp>.alpha_ramp`            | 12 eight-digit HEX colors. Each paints its base step when laid over the background.                        |
| `<mode>.<ramp>.wide_gamut_ramp`       | 12 `oklch()` colors, for Display P3 screens.                                                               |
| `<mode>.<ramp>.wide_gamut_alpha_ramp` | 12 `color(display-p3 …)` colors with alpha. Each paints its wide gamut step when laid over the background. |

`<mode>` is `light` or `dark`. `<ramp>` is `brand` or `neutral`.

## Step Roles

| Step | `role`                  | Use                                                             |
| ---- | ----------------------- | --------------------------------------------------------------- |
| 1    | `app-background`        | App background.                                                 |
| 2    | `subtle-background`     | Cards, sidebars, and popovers.                                  |
| 3    | `component-fill`        | Muted and selected fills.                                       |
| 4    | `component-fill-hover`  | Component fill on hover.                                        |
| 5    | `component-fill-active` | Component fill when pressed or active.                          |
| 6    | `subtle-border`         | Subtle borders and dividers.                                    |
| 7    | `border`                | Borders on cards and components.                                |
| 8    | `strong-border`         | Strong borders, focus rings, chart marks, and checked controls. |
| 9    | `solid-fill`            | Solid fill. The brand ramp's step 9 is the seed.                |
| 10   | `solid-fill-hover`      | Solid fill on hover.                                            |
| 11   | `low-contrast-text`     | Muted text and secondary labels.                                |
| 12   | `high-contrast-text`    | Body text and headings.                                         |

# Generator Changes

Changes in `scripts/generateRadixColors.ts` are marked `Local change` in the code.
The rest are in `scripts/generate.ts`.

| The Problem                                                                                                                                                                                                                            | Fix                                                                                                                                                                                                                                                                                                                       |
| -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| When the seed is close to step 1, step 9 is swapped for a generated color, so step 9 is no longer the seed that was picked and checked.                                                                                                | Step 9 is always the seed passed in.                                                                                                                                                                                                                                                                                      |
| Step 10, the hover for step 9, darkens whenever the seed's lightness is above 0.4. On a light seed with dark text, darkening takes the text below the minimum contrast for some hues.                                                  | Step 10 moves away from the page by up to Radix's amount, as far as the seed's text keeps 4.5:1 and Lc 75. With less than half that room, it moves away from the text.                                                                                                                                                    |
| A gray input that matches the untinted `gray` scale has its chroma scaled against zero, so every step hits the chroma cap and the "neutral" ramp gets way too tinted.                                                                  | In that case, the neutral ramp takes its chroma curve from the closest tinted gray scale.                                                                                                                                                                                                                                 |
| When white text on the seed falls below APCA Lc 40, the text is a dark tint of the seed, and the Lc is measured with the seed as text on white, so it can differ from the design session's text on the seed.                           | Text on the seed is white, or black when white text on the seed falls below Lc 40, the same choice as the design session.                                                                                                                                                                                                 |
| Alpha steps lighten or darken in one direction for all three channels, so a step lighter than the background in one channel and darker in another renders the wrong color.                                                             | Each channel sets the alpha it needs to reach the target from the background in its own direction.                                                                                                                                                                                                                        |
| Radix only guarantees contrast for steps 11 and 12 against step 1 and 2. Steps 3-5 are also used for surfaces, and contrast can fall below minimums. Radix also makes no guarantees between the brand color ramp and the neutral ramp. | Steps 11 and 12 move darker in light mode, or lighter in dark mode, until step 11 meets 4.5:1 and APCA Lc 60, and step 12 meets 7:1 and Lc 75, on the background and steps 1–5. Brand steps 11 and 12 also meet them on neutral steps 1–5. Their alpha, wide gamut, and wide gamut alpha versions meet the same minimums. |
| Step 8 is meant for strong borders and focus rings, but falls below the non-text minimums, so charts and focus rings have to use text steps.                                                                                           | Brand step 8 moves darker in light mode, or lighter in dark mode, until it meets 3:1 and APCA Lc 45 on the background, steps 1–3, and neutral steps 1–3. Their alpha, wide gamut, and wide gamut alpha versions meet the same minimums.                                                                                   |
| Radix uses one accent color to build both light and dark modes, so the brand color can't meet text contrast against both backgrounds.                                                                                                  | `light_seed` and `dark_seed`: each mode's brand ramps are built from their own seed. Passing the same seed for both keeps one brand color.                                                                                                                                                                                |

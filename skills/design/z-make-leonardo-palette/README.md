# What is This?

Generates contrast-targeted color ramps for light and dark mode from a brand seed with [Adobe Leonardo](https://leonardocolor.io).
Leonardo places each step at a target contrast ratio against the background, so you pick how far apart the steps are.
Some changes are made on top of Leonardo so the ramps pass contrast minimums (see [Generator Changes](#generator-changes)).

Each mode gets:

- A 12-step brand ramp, built from the seed.
- A 12-step neutral ramp, tinted by the gray.
- Alpha versions of both ramps (reuses the alpha math from Radix).

[z-palette-design-session](../z-palette-design-session) runs this skill to build its palettes. You can also run it on its own.

# Install the Skill

```sh
npx skills add chriselderxyz/skillz --skill z-make-leonardo-palette
```

# Inputs

| Input              | Options                                                    | Default                   | Description                                                                                                                                                                                                |
| ------------------ | ---------------------------------------------------------- | ------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `light_seed`       | Six-digit HEX                                              | Required                  | The brand color for light mode. Becomes step 9 of the light brand ramp.                                                                                                                                    |
| `dark_seed`        | Six-digit HEX                                              | `light_seed`              | The brand color for dark mode. Becomes step 9 of the dark brand ramp.                                                                                                                                      |
| `secondary_color`  | Six-digit HEX                                              | None                      | A second color key for both brand ramps. Leonardo blends between the seed and this color, which shifts the hue along the ramp. Ask for it when one hue goes muddy in the light or dark steps, like yellow. |
| `light_gray`       | Six-digit HEX                                              | Derived from `light_seed` | Tints the light mode neutral ramp. When omitted, a muted mid gray in the seed's hue (OKLCH lightness 0.55, chroma 0.012).                                                                                  |
| `dark_gray`        | Six-digit HEX                                              | Derived from `dark_seed`  | Tints the dark mode neutral ramp. Derived the same way as `light_gray`.                                                                                                                                    |
| `light_background` | Six-digit HEX                                              | `#FFFFFF`                 | The light mode page background.                                                                                                                                                                            |
| `dark_background`  | Six-digit HEX                                              | `#141414`                 | The dark mode page background.                                                                                                                                                                             |
| `vibrant`          | `true`, `false`                                            | `false`                   | Sets each brand step's chroma to a ratio of the seed's chroma, taken from Radix ramps for the seed's hue. Makes Leonardo ramps less flat.                                                                  |
| `contrast_targets` | File names in `configs/contrast-targets/`, or "create new" | `default`                 | The contrast ratio Leonardo places each step at. "create new" builds one with you.                                                                                                                         |

## Contrast Targets

- A contrast targets config has 12 WCAG 2 contrast ratios against the background, steps 1 to 12, for each ramp (`brand`, `neutral`) and mode (`light`, `dark`).
- `default` takes its step spacing from the median of Radix's scales, so the ramps share Radix's step roles and one token mapping works for both generators.
- `Ask the agent to create a new contrast config if you want to customize it.`

# Blend Mode

Leonardo builds each ramp by blending from white, through the color keys, to black. It then picks the color along that blend that hits each step's contrast target.
The color keys are the seed, plus `secondary_color` when set.

The blend mode is the color space the blend happens in (Leonardo's `colorSpace` option).
It changes how much color the light and dark steps keep, and how the hue moves between two color keys.

- **The skill uses** `CAM02p` **for all four ramps** (brand and neutral, light and dark).
- Leonardo's own default is `RGB`.
- It isn't an input. To change it, edit `colorSpace` in `scripts/generate.ts`.
- Leonardo's bezier smoothing (`smooth`) is off.

| Option   | Color Space                                               | How it Blends                                                                               |
| -------- | --------------------------------------------------------- | ------------------------------------------------------------------------------------------- |
| `CAM02p` | CIECAM02 as lightness, chroma, and hue (JCh)              | Lightness, chroma, and hue separately. Hue moves around the color wheel. **Skill default.** |
| `CAM02`  | CIECAM02 color appearance model (Jab)                     | A straight line through lightness and two color axes.                                       |
| `OKLCH`  | Oklab as lightness, chroma, and hue                       | Lightness, chroma, and hue separately. Hue moves around the color wheel.                    |
| `OKLAB`  | Oklab, a perceptual space with more even hues than CIELAB | A straight line through lightness and two color axes.                                       |
| `LCH`    | CIELAB as lightness, chroma, and hue                      | Lightness, chroma, and hue separately. Hue moves around the color wheel.                    |
| `LAB`    | CIELAB, a perceptual space                                | A straight line through lightness and two color axes.                                       |
| `HSLuv`  | HSL with perceptual lightness from CIELUV                 | Hue, saturation, and lightness separately.                                                  |
| `HSL`    | Hue, saturation, and lightness                            | Hue, saturation, and lightness separately. Lightness isn't perceptual.                      |
| `HSV`    | Hue, saturation, and value                                | Hue, saturation, and value separately. Value isn't perceptual.                              |
| `RGB`    | sRGB channels                                             | A straight line through red, green, and blue. **Leonardo default.**                         |

- Straight line spaces lose chroma part way between two different hues, because the line cuts across the color wheel.
- Lightness, chroma, and hue spaces keep chroma, and turn the hue around the wheel instead.

# Outputs

One JSON file in the working directory, named `<brand-color-name>-<seeds>-<grays>.json`.
The dark seed and dark gray are only in the name when they differ from the light ones.
For example: `indigo-3e63dd-6e7179.json`.

| Key                                   | Contents                                                                                               |
| ------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| `name`                                | The file name without `.json`.                                                                         |
| `inputs`                              | The seeds, grays, backgrounds, `vibrant`, and `contrast_targets` used, and `secondary_color` when set. |
| `light.background`, `dark.background` | The mode's page background.                                                                            |
| `<mode>.lightness`                    | Leonardo's lightness for the background, from 0 to 100.                                                |
| `<mode>.brand.brand_foreground`       | Text on the seed: white, or black when white falls below APCA Lc 40.                                   |
| `<mode>.<ramp>.base_ramp`             | 12 steps. Each has its `step`, `role`, `color` (HEX), and `contrast`.                                  |
| `<mode>.<ramp>.alpha_ramp`            | 12 eight-digit HEX colors. Each paints its base step when laid over the background.                    |

`<mode>` is `light` or `dark`. `<ramp>` is `brand` or `neutral`.

## Step Roles

Leonardo has no roles - these are derived from Radix

| Step | `role`                  | Use                                                                |
| ---- | ----------------------- | ------------------------------------------------------------------ |
| 1    | `app-background`        | App background.                                                    |
| 2    | `subtle-background`     | Cards, sidebars, and popovers.                                     |
| 3    | `component-fill`        | Muted and selected fills.                                          |
| 4    | `component-fill-hover`  | Component fill on hover.                                           |
| 5    | `component-fill-active` | Component fill when pressed or active.                             |
| 6    | `subtle-border`         | Subtle borders and dividers.                                       |
| 7    | `border`                | Borders on cards and components.                                   |
| 8    | `strong-border`         | Strong borders, focus rings, chart marks, and checked controls.    |
| 9    | `solid-fill`            | Solid fill. The brand ramp's step 9 is the seed.                   |
| 10   | `solid-fill-hover`      | Solid fill on hover. The brand ramp's step 10 is the seed's hover. |
| 11   | `low-contrast-text`     | Muted text and secondary labels.                                   |
| 12   | `high-contrast-text`    | Body text and headings.                                            |

# Generator Changes

Changes are in `scripts/generate.ts`. Adobe's Leonardo library is unchanged.

| The Problem                                                                                                                                                                                                     | Fix                                                                                                                                                                                                                                              |
| --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Steps 11 and 12 are placed by contrast against the background only, so they can fail contrast against steps 1-5.                                                                                                | Steps 11 and 12 are adjusted until step 11 meets 4.5:1 and APCA Lc 60, and step 12 meets 7:1 and Lc 75, on the background and steps 1–5. Brand steps 11 and 12 also meet them on neutral steps 1–5. Their alpha versions meet the same minimums. |
| With the default contrast targets, step 8 falls below the non-text minimums, so charts and focus rings have to use text steps.                                                                                  | Brand step 8 is adjusted until it meets 3:1 and APCA Lc 45 on the background, steps 1–3, and neutral steps 1–3. Their alpha versions meet the same minimums.                                                                                     |
| Every step is placed by its contrast ratio, so step 9 is a lighter or darker version of the seed, and no step is its hover.                                                                                     | Steps 9 and 10 are replaced with the seed and its hover, using the same hover rule as Radix.                                                                                                                                                     |
| Chroma fades evenly toward white and black along the curve, so pale steps and dark mode text steps come out close to gray with little tint.                                                                     | `vibrant`: each brand step's chroma is a ratio of the seed's chroma, from a table of 10 hue groups averaged from Radix generator ramps. Basically an adjustment to make Leonardo palettes less dingy. Can toggle this.                           |
| Leonardo has no alpha ramps.                                                                                                                                                                                    | Alpha ramps use a copy of Radix's alpha solve, where each channel sets the alpha it needs to reach the target from the background in its own direction.                                                                                          |
| Leonardo makes dark mode by re-rendering the same theme at a lower lightness, so one set of color keys builds both light and dark modes, and the brand color can't meet text contrast against both backgrounds. | `light_seed` and `dark_seed`: each mode's brand ramps are built from their own seed. Passing the same seed for both keeps one brand color.                                                                                                       |

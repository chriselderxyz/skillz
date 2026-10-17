# What is This?

An interactive session for designing app color palettes.
Gives you a full set of ramps and a default design token mapping.

Use this to get app colors that:

- You like.
- Don't look like shit.
- Pass all contrast requirements (for **BOTH** WCAG v2 & APAC).

# Setup

## Install the Skills

The session uses both generator skills. Install them together:

```sh
npx skills add chriselderxyz/skillz --skill z-palette-design-session --skill z-make-radix-palette --skill z-make-leonardo-palette
```

## Install Dependencies

### Auto

- Each skill installs its npm dependencies the first time it runs.
- Just ensure Node.js 18 or newer.

### Manual

- Run `npm install` in each of `z-palette-design-session`, `z-make-radix-palette`, and `z-make-leonardo-palette`.
- `npm run typecheck` to verify the TypeScript scripts.

# How it Works

- Tell the agent
  - What generators you want to use (radix, leonardo, or both).
  - What design token mapping to (AKA -> Ramps to CSS Variables).
  - What type of color palettes you want to try out.
- Agent picks 
  - An OKLCH hue for the brand.
  - A hue for destructive, warning, and success signals.
  - A seed for each hue, used to build both modes' ramps
  - A gray light and dark seed for neutral ramps (Derived from the the light and dark brand seeds)
  - The background color for each mode
- Agent generates all the palettes you asked for
- Results are put in `design-session.html` (use this to iterate).
- Final selection is exported to `export.html`

# Hot Tips

| Issue                                     | Ask the Agent To                                                                                                                                                                                                                                              |
| ----------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Dark mode primary color TOO DAMN COLORFUL | “Drop the chroma for the dark seed”.                                                                                                                                                                                                                          |
| Dark mode too dark                        | ”Increase the lightness of the dark background, keep it grayscale”                                                                                                                                                                                            |
| Light mode too light                      | “Decrease the lightness of the light background, keep it grayscale”                                                                                                                                                                                           |
| Dark mode primary color doesn’t match<br> | This is a tough one, if you want the contrast guarantees the saturation difference can make the hue look different.<br>Best option I’ve found is to ask to “rotate the hue of the dark seed”, checking manually is usually easiest if you want to dial it in. |
| Want more tinted neutral ramps            | “Bump the chroma up on the gray seeds to tint the neutral ramp”.<br>The default token mapping doesn’t use enough of the neutral ramp to notice much.                                                                                                          |
| Don’t like my tokens or mapping           | Ask the agent for a “new token mapping”, it will ask you about what steps draw on what other steps so it can’t hit contrast targets for you.<br>You can iterate as you go, and this will save a config you can reuse.                                         |

# Inputs

| Input                   | Options                                                  | Default                | Description                                                                                                                                                                                |
| ----------------------- | -------------------------------------------------------- | ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `generators`            | `radix`, `leonardo`                                      | `radix` and `leonardo` | Generators that make every palette, all from the same inputs. A palette can use different generators when the user asks.                                                                   |
| `token_mapping`         | File names in `configs/token-mappings/`, or "create new" | `default`              | Maps each token to a ramp step and lists the token's contrast checks. "Create new" builds one with you.                                                                                    |
| `primary_text_contrast` | `true`, `false`                                          | `false`                | Turns on guaranteed text contrast for `primary`. Each hue gets a separate light seed and a dark seed, so `primary` meets 4.5:1 and Lc 60 against the background in both modes. |

The request can also include:

- The brand, as a description, a hue, or a color.
- How many palettes to make.
- Grays to use in place of the selected ones.

# One Seed or Two

- By default, a single seed (primary/brand color) is used for both light and dark mode.
- This looks better, but means contrast on either light or dark mode will drop below 4.5:1, and can drop below 3:1, so the primary color can't be used for text.
- IF you want the primary color to be allowed for text (and controls), you need a different color for light and dark - still looks fine, but it's inconsistent.
- Set `primary_text_contrast` to true to switch to the two color version of the skill.

# Guarantees

These minimums hold in both modes, for the brand, neutral, and signal ramps from either generator. `makeSeeds.ts` checks the seeds, the generators keep step 10 within its text's minimums, and they move steps 8, 11, and 12 until they meet theirs.

| Color                                   | Against                                          | WCAG 2        | APCA          |
| --------------------------------------- | ------------------------------------------------ | ------------- | ------------- |
| `primary`, with `primary_text_contrast` | The background of its mode                       | 4.5:1         | Lc 60         |
| Text on a seed, white or black          | The seed and its hover (step 10)                 | 4.5:1         | Lc 75         |
| Brand step 8                            | The background, steps 1–3, and neutral steps 1–3 | 3:1           | Lc 45         |
| Step 11                                 | The background and steps 1–5 of its ramp         | 4.5:1         | Lc 60         |
| Step 12                                 | The background and steps 1–5 of its ramp         | 7:1           | Lc 75         |
| Brand steps 11 and 12                   | Neutral steps 1–5                                | Same as above | Same as above |

Token mapping checks use the minimums in `assets/contrast-thresholds.json`, and the design session reports any that fail.

# Generator Changes

The design session runs both generator skills with the same inputs. 
Both have some small changes from their published behaviour.

## Radix

Changes in `z-make-radix-palette/scripts/generateRadixColors.ts` are marked `Local change` in the code.
The rest are in `z-make-radix-palette/scripts/generate.ts`.

| The Problem                                                                                                                                                                                                                            | Fix                                                                                                                                                                                                                                        |
| -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| When the seed is close to step 1, step 9 is swapped for a generated color, so `primary` is no longer the seed that was picked and checked.                                                                                             | Step 9 is always the seed passed in.                                                                                                                                                                                                       |
| Step 10, the hover for step 9, darkens whenever the seed's lightness is above 0.4. On a light seed with dark text, darkening takes the text below the minimum contrast for some hues.                                                  | Step 10 moves away from the page by up to Radix's amount, as far as the seed's text keeps 4.5:1 and Lc 75. With less than half that room, it moves away from the text.                                                                     |
| A gray input that matches the untinted `gray` scale has its chroma scaled against zero, so every step hits the chroma cap and the "neutral" ramp gets way too tinted.                                                                  | In that case, the neutral ramp takes its chroma curve from the closest tinted gray scale.                                                                                                                                                  |
| When white text on the seed falls below APCA Lc 40, the text is a dark tint of the seed, and the Lc is measured with the seed as text on white, so it can differ from the design session's text on the seed.                           | Text on the seed is white, or black when white text on the seed falls below Lc 40, the same choice as the design session.                                                                                                                  |
| Alpha steps lighten or darken in one direction for all three channels, so a step lighter than the background in one channel and darker in another renders the wrong color.                                                             | Each channel sets the alpha it needs to reach the target from the background in its own direction.                                                                                                                                         |
| Radix only guarantees contrast for steps 11 and 12 against step 1 and 2. Steps 3-5 are also used for surfaces, and contrast can fall below minimums. Radix also makes no guarantees between the brand color ramp and the neutral ramp. | Steps 11 and 12 move darker in light mode, or lighter in dark mode, until step 11 meets 4.5:1 and APCA Lc 60, and step 12 meets 7:1 and Lc 75, on the background and steps 1–5. Brand steps 11 and 12 also meet them on neutral steps 1–5. |
| Step 8 is meant for strong borders and focus rings, but falls below the non-text minimums, so charts and focus rings have to use text steps.                                                                                           | Brand step 8 moves darker in light mode, or lighter in dark mode, until it meets 3:1 and APCA Lc 45 on the background, steps 1–3, and neutral steps 1–3.                                                                                   |
| Radix uses one accent color to build both light and dark modes, so the brand color can't meet text contrast against both backgrounds.                                                                                                  | `light_seed` and `dark_seed`: each mode's brand ramps are built from their own seed. Passing the same seed for both keeps one brand color.                                                                                                 |

## Leonardo

Changes are in `z-make-leonardo-palette/scripts/generate.ts`. Adobe's Leonardo library is unchanged.

| The Problem                                                                                                                                                                                                     | Fix                                                                                                                                                                                                                    |
| --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Steps 11 and 12 are placed by contrast against the background only, so they can fail contrast against steps 1-5.                                                                                                | Steps 11 and 12 are adjusted until step 11 meets 4.5:1 and APCA Lc 60, and step 12 meets 7:1 and Lc 75, on the background and steps 1–5. Brand steps 11 and 12 also meet them on neutral steps 1–5.                    |
| With the default contrast targets, step 8 falls below the non-text minimums, so charts and focus rings have to use text steps.                                                                                  | Brand step 8 is adjusted until it meets 3:1 and APCA Lc 45 on the background, steps 1–3, and neutral steps 1–3.                                                                                                        |
| Every step is placed by its contrast ratio, so step 9 is a lighter or darker version of the seed, and no step is its hover.                                                                                     | Steps 9 and 10 are replaced with the seed and its hover, using the same hover rule as Radix.                                                                                                                           |
| Chroma fades evenly toward white and black along the curve, so pale steps and dark mode text steps come out close to gray with little tint.                                                                     | `vibrant`: each brand step's chroma is a ratio of the seed's chroma, from a table of 10 hue groups averaged from Radix generator ramps. Basically an adjustment to make Leonardo palettes less dingy. Can toggle this. |
| Leonardo has no alpha ramps.                                                                                                                                                                                    | Alpha ramps use a copy of Radix's alpha solve, where each channel sets the alpha it needs to reach the target from the background in its own direction.                                                                |
| Leonardo makes dark mode by re-rendering the same theme at a lower lightness, so one set of color keys builds both light and dark modes, and the brand color can't meet text contrast against both backgrounds. | `light_seed` and `dark_seed`: each mode's brand ramps are built from their own seed. Passing the same seed for both keeps one brand color.                                                                             |

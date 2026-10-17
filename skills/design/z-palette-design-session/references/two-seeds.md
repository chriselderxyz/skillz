# Phase 1: Make Seeds

## Action 1. Select Seeds
- For the brand hue and each signal hue, select:
    - A relative chroma, from 0 to 1, the seeds' chroma as a share of the most chroma sRGB holds.
    - A lightness for the light seed, a deep color that carries white text.
    - A lightness for the dark seed, a light color that carries black text.
- When the user gives a color, use it as the light brand seed when it is deep, or the dark brand seed when it is light.

## Action 2. Make Seeds
- Make the seeds for each hue with `"<skill_dir>/node_modules/.bin/tsx" "<skill_dir>/scripts/colors/makeSeeds.ts" --hue "<hue>" --relative-chroma "<relative_chroma>" --light-seed-lightness "<light_seed_lightness>" --dark-seed-lightness "<dark_seed_lightness>"`.
    - For the user's color, pass `--light-seed "<color>"` or `--dark-seed "<color>"` in place of `--hue`, `--relative-chroma`, and that mode's seed lightness.
- For each seed that fails, select a new lightness, starting from its `suggestion`, and make it again.
- Use `color` from each seed in the output.

# Phase 2: Check Seeds

## Action 1. Check Seeds
- Run the Phase 1 command for each hue again, with `--light-background "<light_background>" --dark-background "<dark_background>"` added.
- For each seed that fails, select a new lightness, starting from its `suggestion`, and check again.
- When a brand seed changes, select that mode's background again.
- Use `color` from each seed in the output.

## Action 2. Select Suggested Brand
- Select which brand seed is the suggested brand color for marketing:
    - When the user gave a color to use as a seed, select that seed.
    - Otherwise, select the seed that better represents the brand:
        - The light seed suits deep, saturated brands that mostly appear on white or light surfaces.
        - The dark seed suits bright brands, such as sky blue, lime, or yellow, that mostly appear on dark or photographic surfaces.

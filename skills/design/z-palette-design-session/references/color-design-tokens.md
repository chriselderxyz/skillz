# Global Context

## Token Schema

- A set mapping of color steps to design tokens.

## Custom Schema Design

- Tokens don't need to be unique colors, for example, `sidebar` could match `card` or even `background`.
- Use the roles as guidelines, but not rules.
- Dark-mode elevation gets lighter.
- Muted and hover must never equal the surface they sit on.
- Labels on tinted fills use neutral N12, not same-hue B12.
- `primary` is always the brand seed color.
- You must satisfy all the contrast requirements

# Color Legend


| Value                 | Meaning                                                                                                                                                                                                              |
| --------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `B1`–`B12`            | Brand ramp, step 1–12. For Radix, step 9 equals the brand seed                                                                                                                                                       |
| `N1`–`N12`            | Neutral ramp, step 1–12                                                                                                                                                                                              |
| `SD1`–`SD12`          | Destructive ramp, step 1–12                                                                                                                                                                                          |
| `SW1`–`SW12`          | Warning ramp, step 1–12                                                                                                                                                                                              |
| `SS1`–`SS12`          | Success ramp, step 1–12                                                                                                                                                                                              |
| `BA1`–`BA12`          | Brand alpha ramp, step 1–12. The see-through version of the same step: it blends with the surface under it, and over the generator background it matches the solid step                                              |
| `NA1`–`NA12`          | Neutral alpha ramp, step 1–12                                                                                                                                                                                        |
| `SDA1`–`SDA12`        | Destructive alpha ramp, step 1–12                                                                                                                                                                                    |
| `SWA1`–`SWA12`        | Warning alpha ramp, step 1–12                                                                                                                                                                                        |
| `SSA1`–`SSA12`        | Success alpha ramp, step 1–12                                                                                                                                                                                        |
| `white` / `black`     | Pure `#FFFFFF` / `#000000` (not ramp steps)                                                                                                                                                                          |
| `selected-background` | The palette's selected page background for that mode (the generator's light / dark background input). Not a ramp step. The alpha ramps are built over it, so on it every alpha step matches its solid step           |
| `on-seed`             | Text on the brand seed. `#FFFFFF` for a deep seed, or light neutral step 12 (`N12`) for a light seed, used in both modes. The chosen text must pass WCAG 4.5:1 and APCA Lc 75 on the seed. Set once per palette          |


- Steps follow Radix semantics.
  - 1–2 backgrounds.
  - 3–5 component fills.
  - 6–8 borders.
  - 9–10 solid fills.
  - 11–12 text.
- Alpha steps (`BA`, `NA`, `SDA`, `SWA`, `SSA`) are for fills, hovers and borders that sit on a surface. Surfaces, `primary` and most text stay solid.
- `light / dark` both given when the modes differ.

# Contrast Targets

- Text passes 4.5:1 on the surface it sits on.
    - Placeholder, badge, and button text included.
    - Disabled text has no target.
- A border, fill, or glyph that identifies a control passes 3:1 against the adjacent color.
    - `input`.
    - Checkbox, radio, and switch box.
    - Focus `ring`.
    - Checked or selected state.
    - Icon-only button glyph.
    - `chart-primary`.
- Hover has no target.
- Decorative borders, card borders, dividers, table rules, and surface against surface have no target.
- A labelled button has no fill-against-page target.
- State uses a second cue besides color.
- Checkbox, radio, and switch use `input` for the box border in every state, `primary` for the checked fill, and `primary-foreground` for the glyph.
    - When `on-seed` is N12, the checked box keeps the `input` border.
- A selected nav or list row uses `accent` or `sidebar-accent` plus a second cue.
- An icon-only glyph uses `foreground` or `muted-foreground`.

# Design Tokens and Schemas


| Token                         | Description                                                                                         | Black & White     | BG - N1 Raised        | BG - N2 Raised        | N1              | N2              |
| ----------------------------- | --------------------------------------------------------------------------------------------------- | ----------------- | --------------------- | --------------------- | --------------- | --------------- |
| `background`                  | Background color                                                                                    | `white` / `black` | `selected-background` | `selected-background` | `N1`            | `N2`            |
| `foreground`                  | Text color contrasting `background`                                                                 | `N12`             | `N12`                 | `N12`                 | `N12`           | `N12`           |
| `primary`                     | High emphasis actions and brand surfaces                                                            | `seed`            | `seed`                | `seed`              | `seed`          | `seed`          |
| `primary-foreground`          | Text color contrasting `primary`                                                                    | `on-seed`         | `on-seed`             | `on-seed`             | `on-seed`       | `on-seed`       |
| `secondary`                   | Lower emphasis for lesser actions and supporting surfaces                                           | `BA4` / `BA6`     | `BA4` / `BA6`         | `BA4` / `BA6`         | `BA4` / `BA6`   | `BA4` / `BA6`   |
| `secondary-foreground`        | Text color contrasting `secondary`                                                                  | `BA12`            | `BA12`                | `BA12`                | `BA12`          | `BA12`          |
| `accent`                      | Interactive hover, focus, active surfaces                                                           | `BA3`             | `BA3`                 | `BA3`                 | `BA3`           | `BA3`           |
| `accent-foreground`           | Text color contrasting `accent`                                                                     | `N12`             | `N12`                 | `N12`                 | `N12`           | `N12`           |
| `muted`                       | Subtle, low-emphasis surfaces                                                                       | `NA3`             | `NA3`                 | `NA3`                 | `NA3`           | `NA3`           |
| `muted-foreground`            | Text color contrasting `muted`                                                                      | `N11`             | `N11`                 | `N11`                 | `N11`           | `N11`           |
| `border`                      | Default border color used for cards, menus, tables, separators and layout dividers                  | `NA6` / `NA7`     | `NA6` / `NA7`         | `NA6` / `NA7`         | `NA6` / `NA7`   | `NA6` / `NA7`   |
| `input`                       | Form control borders, including checkbox, radio and switch boxes, and input surface treatment       | `N10`             | `N10`                 | `N10`                 | `N10`           | `N10`           |
| `ring`                        | Focus rings and outlines                                                                            | `B11`             | `B11`                 | `B11`                 | `B11`           | `B11`           |
| `sidebar`                     | The base sidebar surface - can match other backgrounds if appropriate                               | `N1`              | `N1`                  | `N2`                  | `N2`            | `N1` / `N3`     |
| `sidebar-foreground`          | Sidebar text color - can match other text if appropriate                                            | `N12`             | `N12`                 | `N12`                 | `N12`           | `N12`           |
| `sidebar-primary`             | High emphasis actions in the sidebar                                                                | `seed`            | `seed`              | `seed`              | `seed`          | `seed`          |
| `sidebar-primary-foreground`  | Text color contrasting `sidebar-primary`                                                            | `on-seed`         | `on-seed`             | `on-seed`             | `on-seed`       | `on-seed`       |
| `sidebar-accent`              | Hover and selected states in the sidebar                                                            | `BA3`             | `BA3`                 | `BA3`                 | `BA3`           | `BA3`           |
| `sidebar-accent-foreground`   | Text color contrasting `sidebar-accent`                                                             | `N12`             | `N12`                 | `N12`                 | `N12`           | `N12`           |
| `sidebar-border`              | Sidebar specific borders and separators                                                             | `NA6` / `NA7`     | `NA6` / `NA7`         | `NA6` / `NA7`         | `NA6` / `NA7`   | `NA6` / `NA7`   |
| `sidebar-ring`                | Sidebar specific focus rings                                                                        | `B11`             | `B11`                 | `B11`                 | `B11`           | `B11`           |
| `card`                        | Elevated surfaces                                                                                   | `N1`              | `N1`                  | `N2`                  | `N2`            | `N1` / `N3`     |
| `card-foreground`             | Text color contrasting `card`                                                                       | `N12`             | `N12`                 | `N12`                 | `N12`           | `N12`           |
| `popover`                     | Floating surfaces                                                                                   | `white` / `N2`    | `N1`                  | `N2`                  | `N2`            | `N1` / `N4`     |
| `popover-foreground`          | Text color on popovers                                                                              | `N12`             | `N12`                 | `N12`                 | `N12`           | `N12`           |
| `chart-primary`               | Primary data series inside charts (bars, lines, rings, progress)                                    | `B11`             | `B11`                 | `B11`                 | `B11`           | `B11`           |
| `destructive`                 | Destructive and error text on the page: error messages, destructive menu items, error input borders | `SD11` / `SD12`   | `SD11` / `SD12`       | `SD11` / `SD12`       | `SD11` / `SD12` | `SD11` / `SD12` |
| `destructive-fill`            | Fill for destructive badges, buttons, banners and alerts                                            | `SDA4` / `SD12`   | `SDA4` / `SD12`       | `SDA4` / `SD12`       | `SDA4` / `SD12` | `SDA4` / `SD12` |
| `destructive-fill-foreground` | Text and icons on `destructive-fill`                                                                | `SD12` / `SD6`    | `SD12` / `SD6`        | `SD12` / `SD6`        | `SD12` / `SD6`  | `SD12` / `SD6`  |
| `warning`                     | Warning and caution text on the page                                                                | `SW12`            | `SW12`                | `SW12`                | `SW12`          | `SW12`          |
| `warning-fill`                | Fill for warning badges, banners and alerts                                                         | `SWA4` / `SW12`   | `SWA4` / `SW12`       | `SWA4` / `SW12`       | `SWA4` / `SW12` | `SWA4` / `SW12` |
| `warning-fill-foreground`     | Text and icons on `warning-fill`                                                                    | `SW12` / `SW6`    | `SW12` / `SW6`        | `SW12` / `SW6`        | `SW12` / `SW6`  | `SW12` / `SW6`  |
| `success`                     | Success and positive text on the page                                                               | `SS11` / `SS12`   | `SS11` / `SS12`       | `SS11` / `SS12`       | `SS11` / `SS12` | `SS11` / `SS12` |
| `success-fill`                | Fill for success badges, toasts and alerts                                                          | `SSA4` / `SS12`   | `SSA4` / `SS12`       | `SSA4` / `SS12`       | `SSA4` / `SS12` | `SSA4` / `SS12` |
| `success-fill-foreground`     | Text and icons on `success-fill`                                                                    | `SS12` / `SS6`    | `SS12` / `SS6`        | `SS12` / `SS6`        | `SS12` / `SS6`  | `SS12` / `SS6`  |

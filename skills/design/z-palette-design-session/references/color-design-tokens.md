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
- Surfaces use `selected-background` or neutral steps from N2 up.
- `accent` and `sidebar-accent` use neutral steps.
- Every token pair meets the minimum contrast thresholds in both modes for every palette in the run.
- A new token takes the minimum contrast thresholds of the element it draws.



# Color Legend


| Value                 | Meaning                                                                                                                                                                                                    |
| --------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `B1`–`B12`            | Brand ramp, step 1–12. For Radix, step 9 equals the brand seed                                                                                                                                             |
| `N1`–`N12`            | Neutral ramp, step 1–12                                                                                                                                                                                    |
| `SD1`–`SD12`          | Destructive ramp, step 1–12                                                                                                                                                                                |
| `SW1`–`SW12`          | Warning ramp, step 1–12                                                                                                                                                                                    |
| `SS1`–`SS12`          | Success ramp, step 1–12                                                                                                                                                                                    |
| `BA1`–`BA12`          | Brand alpha ramp, step 1–12. The see-through version of the same step: it blends with the surface under it, and over the generator background it matches the solid step                                    |
| `NA1`–`NA12`          | Neutral alpha ramp, step 1–12                                                                                                                                                                              |
| `SDA1`–`SDA12`        | Destructive alpha ramp, step 1–12                                                                                                                                                                          |
| `SWA1`–`SWA12`        | Warning alpha ramp, step 1–12                                                                                                                                                                              |
| `SSA1`–`SSA12`        | Success alpha ramp, step 1–12                                                                                                                                                                              |
| `white` / `black`     | Pure `#FFFFFF` / `#000000` (not ramp steps)                                                                                                                                                                |
| `selected-background` | The palette's selected page background for that mode (the generator's light / dark background input). Not a ramp step. The alpha ramps are built over it, so on it every alpha step matches its solid step |
| `seed-foreground`     | Text on the brand seed. `#FFFFFF` for a deep seed, or light neutral step 12 (`N12`) for a light seed, used in both modes. Set once per palette                                                             |


- Steps follow Radix semantics.
  - 1–2 backgrounds.
  - 3–5 component fills.
  - 6–8 borders.
  - 9–10 solid fills.
  - 11–12 text.
- Alpha steps (`BA`, `NA`, `SDA`, `SWA`, `SSA`) are for fills, hovers and borders that sit on a surface.
- Surfaces, `primary` and all text use solid colors.
- `light / dark` both given when the modes differ.



# Minimum Contrast Thresholds

- Contrast is measured on the rendered color, with alpha steps and opacity composited over the surface below.
- State uses a second cue besides color.


| Element                                                                                              | Drawn With                                                                                   | Measured Against                      | Minimum WCAG 2 | Minimum APCA |
| ---------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------- | ------------------------------------- | -------------- | ------------ |
| Body text                                                                                            | `foreground`, `card-foreground`, or `popover-foreground`                                     | The surface it sits on                | 4.5:1          | Lc 75        |
| Text on the brand seed                                                                               | `seed-foreground`                                                                            | `seed`                                | 4.5:1          | Lc 75        |
| Other text, including placeholder, badge, and button text                                            | Any other text token, such as a `*-foreground` token, `destructive`, `warning`, or `success` | The surface it sits on                | 4.5:1          | Lc 60        |
| Link in body text                                                                                    | A text token, underlined                                                                     | The surface it sits on                | 4.5:1          | Lc 75        |
| Disabled text                                                                                        | A text token                                                                                 | The surface it sits on                | None           | Lc 30        |
| Input, checkbox, radio, and switch border                                                            | `input`, in every state                                                                      | The adjacent color                    | 3:1            | Lc 45        |
| Checked checkbox, radio, and switch                                                                  | `primary` fill with a `primary-foreground` glyph                                             | Glyph against the fill                | 3:1            | Lc 45        |
| Focus indicator on every focused element, including rows that change to `accent` or `sidebar-accent` | `ring`, or `sidebar-ring` in the sidebar                                                     | The adjacent color                    | 3:1            | Lc 45        |
| Selected nav or list row                                                                             | `accent` or `sidebar-accent` fill with a bold label                                          | Label against the fill                | 4.5:1          | Lc 60        |
| Icon-only button glyph                                                                               | `foreground` or `muted-foreground`                                                           | The adjacent color                    | 3:1            | Lc 45        |
| Any other border, fill, or glyph that identifies a control                                           | Any                                                                                          | The adjacent color                    | 3:1            | Lc 45        |
| Chart data series                                                                                    | `chart-primary`                                                                              | The adjacent color                    | 3:1            | Lc 45        |
| Labelled button fill                                                                                 | Any                                                                                          | The page                              | None           | None         |
| Hover                                                                                                | Any                                                                                          | Any                                   | None           | None         |
| Decorative border, card border, divider, table rule, or surface against surface                      | Any                                                                                          | Any                                   | None           | None         |




# Design Tokens and Default Schema


| Token                         | Description                                                                                         | Default               |
| ----------------------------- | --------------------------------------------------------------------------------------------------- | --------------------- |
| `background`                  | Background color                                                                                    | `selected-background` |
| `foreground`                  | Text color contrasting `background`                                                                 | `N12`                 |
| `primary`                     | High emphasis actions and brand surfaces                                                            | `seed`                |
| `primary-foreground`          | Text color contrasting `primary`                                                                    | `seed-foreground`     |
| `secondary`                   | Lower emphasis for lesser actions and supporting surfaces                                           | `seed`                |
| `secondary-foreground`        | Text color contrasting `secondary`                                                                  | `seed-foreground`     |
| `accent`                      | Interactive hover, focus, active surfaces                                                           | `NA3`                 |
| `accent-foreground`           | Text color contrasting `accent`                                                                     | `N12`                 |
| `muted`                       | Subtle fill for low-emphasis elements on a surface: tab bars, shortcut keys, avatar fallbacks       | `NA3`                 |
| `muted-foreground`            | Text color contrasting `muted`                                                                      | `N11`                 |
| `border`                      | Default border color used for cards, menus, tables, separators and layout dividers                  | `NA6` / `NA7`         |
| `input`                       | Form control borders, including checkbox, radio and switch boxes, and input surface treatment       | `N10` / `N11`         |
| `ring`                        | Focus rings and outlines                                                                            | `B11`                 |
| `sidebar`                     | The base sidebar surface - can match other backgrounds if appropriate                               | `N2`                  |
| `sidebar-foreground`          | Sidebar text color - can match other text if appropriate                                            | `N12`                 |
| `sidebar-primary`             | High emphasis actions in the sidebar                                                                | `seed`                |
| `sidebar-primary-foreground`  | Text color contrasting `sidebar-primary`                                                            | `seed-foreground`     |
| `sidebar-accent`              | Hover and selected states in the sidebar                                                            | `NA3`                 |
| `sidebar-accent-foreground`   | Text color contrasting `sidebar-accent`                                                             | `N12`                 |
| `sidebar-border`              | Sidebar specific borders and separators                                                             | `NA6` / `NA7`         |
| `sidebar-ring`                | Sidebar specific focus rings                                                                        | `B11`                 |
| `card`                        | Elevated surfaces                                                                                   | `N2`                  |
| `card-foreground`             | Text color contrasting `card`                                                                       | `N12`                 |
| `popover`                     | Floating surfaces                                                                                   | `N2`                  |
| `popover-foreground`          | Text color on popovers                                                                              | `N12`                 |
| `chart-primary`               | Primary data series inside charts (bars, lines, rings, progress)                                    | `B11`                 |
| `destructive`                 | Destructive and error text on the page: error messages, destructive menu items, error input borders | `SD11` / `SD12`       |
| `destructive-fill`            | Fill for destructive badges, buttons, banners and alerts                                            | `SDA4` / `SD12`       |
| `destructive-fill-foreground` | Text and icons on `destructive-fill`                                                                | `SD12` / `SD6`        |
| `warning`                     | Warning and caution text on the page                                                                | `SW12`                |
| `warning-fill`                | Fill for warning badges, banners and alerts                                                         | `SWA4` / `SW12`       |
| `warning-fill-foreground`     | Text and icons on `warning-fill`                                                                    | `SW12` / `SW6`        |
| `success`                     | Success and positive text on the page                                                               | `SS11` / `SS12`       |
| `success-fill`                | Fill for success badges, toasts and alerts                                                          | `SSA4` / `SS12`       |
| `success-fill-foreground`     | Text and icons on `success-fill`                                                                    | `SS12` / `SS6`        |

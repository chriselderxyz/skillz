# Token Mapping Rules

- Tokens can share a step, for example, `sidebar` can match `card` or `background`.
- Pick each step by its role in Step Roles.
- Neutral non-text marks, such as input borders, use `N10` in light mode and `N11` in dark mode.
- Dark-mode elevation gets lighter.
- Muted and hover fills differ from the surface they sit on.
- Labels on tinted fills use `N12`.
- `primary` is `seed`.
- Surfaces use `selected-background` or neutral steps from `N2` up.
- `accent` and `sidebar-accent` use neutral steps.
- Surfaces, `primary`, and all text use solid steps.
- State uses a second cue besides color, such as a bold label on a selected row.

# Step Roles

| Step | Role                                                                                    | Guaranteed Contrast                                                                                    |
| ---- | --------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| 1    | App background.                                                                         |                                                                                                        |
| 2    | Subtle background: cards, sidebars, and popovers.                                       |                                                                                                        |
| 3    | Component fill: muted and selected fills.                                               |                                                                                                        |
| 4    | Component fill on hover.                                                                |                                                                                                        |
| 5    | Component fill when pressed or active.                                                  |                                                                                                        |
| 6    | Subtle borders and dividers.                                                            |                                                                                                        |
| 7    | Borders on cards and components.                                                        |                                                                                                        |
| 8    | Strong borders, focus rings, and chart marks. Can also use as a secondary button color. | Brand ramps: 3:1 and APCA Lc 45 on the background, steps 1–3, and neutral steps 1–3.                   |
| 9    | Solid fill. The brand ramp's step 9 is the mode's seed. Primary color for buttons.      | The seed: 3:1 and Lc 45 on the background, and `seed-foreground` meets the `seed-text` minimums on it. |
| 10   | Solid fill on hover.                                                                    |                                                                                                        |
| 11   | Low-contrast text: muted text and secondary labels.                                     | 4.5:1 and Lc 60 on the background and steps 1–5. Brand ramps also on neutral steps 1–5.                |
| 12   | High-contrast text: body text and headings.                                             | 7:1 and Lc 75 on the background and steps 1–5. Brand ramps also on neutral steps 1–5.                  |

# Refs

| Ref                                    | Meaning                                                                                                                                                                  |
| -------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `B1`–`B12`                             | Brand ramp step.                                                                                                                                                         |
| `N1`–`N12`                             | Neutral ramp step.                                                                                                                                                       |
| `D1`–`D12`                             | Destructive ramp step.                                                                                                                                                   |
| `W1`–`W12`                             | Warning ramp step.                                                                                                                                                       |
| `S1`–`S12`                             | Success ramp step.                                                                                                                                                       |
| `BA`, `NA`, `DA`, `WA`, or `SA` + 1–12 | Alpha step of that ramp. It blends with the surface under it. Use alpha steps for fills, hovers, and borders that sit on a surface.                                      |
| `white` / `black`                      | `#FFFFFF` / `#000000`.                                                                                                                                                   |
| `selected-background`                  | The palette's background for the mode.                                                                                                                                   |
| `seed`                                 | The brand seed for the mode.                                                                                                                                             |
| `seed-foreground`                      | Text on the mode's seed: `#FFFFFF`, unless white text falls below APCA Lc 40 on the seed, then `#000000`.                                                                |
| `black-or-white`                       | `#000000` or `#FFFFFF`, whichever meets more of the `other-text` minimums on the token's fill, the token name without `-foreground`, with the higher APCA breaking ties. |
| `{ "light": <ref>, "dark": <ref> }`    | A different ref for each mode.                                                                                                                                           |

# Checks

- Give a token a check for each surface or stack it draws text or a control mark on.
- `against` lists the tokens under the token, from the bottom up:
  - `["card", "muted"]` is `muted` on `card`.
- `element` is a key in `assets/contrast-thresholds.json`.

# File

- Copy `configs/token-mappings/default.json` and edit it.
- Keep every token in `default.json`.
- Put each new token in an existing group or a new group.

# Specific User Questions

- Ask which tokens to change, and the look the user wants.
- Ask what each new token draws and which surfaces it sits on.

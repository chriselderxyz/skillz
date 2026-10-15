# Contrast Targets
- Each ramp and mode has 12 WCAG 2 contrast ratios against the mode's background, for steps 1 to 12.
- Ratios rise from step 1 to step 12.
- Pick each step's ratio by its role in Step Roles.
- Dark mode ratios run higher than light mode ratios for the same role.

# Step Roles

| Step | Role                                                                    |
| ---- | ----------------------------------------------------------------------- |
| 1    | App background.                                                         |
| 2    | Subtle background: cards, sidebars, and popovers.                       |
| 3    | Component fill: muted and selected fills.                               |
| 4    | Component fill on hover.                                                |
| 5    | Component fill when pressed or active.                                  |
| 6    | Subtle borders and dividers.                                            |
| 7    | Borders on cards and components.                                        |
| 8    | Strong borders, focus rings, and chart marks.                           |
| 9    | Solid fill. The brand ramp's step 9 becomes the seed.                   |
| 10   | Solid fill on hover. The brand ramp's step 10 becomes the seed's hover. |
| 11   | Low-contrast text: muted text and secondary labels.                     |
| 12   | High-contrast text: body text and headings.                             |

# File
- Copy `configs/contrast-targets/default.json` and edit it.
- `description` says what the spacing is for.

# Specific User Questions
- Ask what the spacing should follow, such as another design system, or a softer or punchier ramp.
- Ask how distinct the fills, borders, and text should be from each other.

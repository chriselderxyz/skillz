# Skillz

Repo for my public AI skills.

Every skill name starts with `z-` so they're easier to find in a big ole project

# Install

Pick from every skill in the repo:

```sh
npx skills add chriselderxyz/skillz
```

Install specific skills:

```sh
npx skills add chriselderxyz/skillz --skill z-palette-design-session --skill z-make-radix-palette --skill z-make-leonardo-palette
```

Or just copy the folders into your project

# Skills

## Design

| Skill                                                              | Description                                                                                                                                                                            | Dependencies                                                                                                                |
| ------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| [z-palette-design-session](skills/design/z-palette-design-session) | Interactive session for designing app color palettes. Generates palette variations with Radix and Leonardo, maps them to design tokens, and checks every pair against WCAG 2 and APCA. | [z-make-radix-palette](skills/design/z-make-radix-palette) [z-make-leonardo-palette](skills/design/z-make-leonardo-palette) |
| [z-make-radix-palette](skills/design/z-make-radix-palette)         | Generates Radix-style light and dark brand and neutral color ramps from seed HEX colors, with contrast fixes for steps 8, 11, and 12.                                                  | None                                                                                                                        |
| [z-make-leonardo-palette](skills/design/z-make-leonardo-palette)   | Generates contrast-targeted light and dark brand and neutral color ramps with Adobe Leonardo, plus alpha ramps and a seed hover step.                                                  | None                                                                                                                        |

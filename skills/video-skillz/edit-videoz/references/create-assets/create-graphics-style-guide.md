# Context

## Purpose
- This is the process used to make a HyperFrames `frame.md` design spec that later gets copied to `edit/graphics/frame.md` when graphics are generated

# Phase 1: Inputs
Ask the user to give
- A name for the style
- A general description of the style they want for their graphics
- A description of the palette that should be used
- A description of the type/font to use

# Phase 2: Create Style
- Using the inputs, create `assets/graphics-style-guides/<name>.md`
    - The file **is** a HyperFrames `frame.md`: YAML frontmatter holds tokens; markdown body is judgment (tone, do's / don'ts)
    - Exact (quote verbatim, do not round or invent): hex, `fontFamily`, `weight`
    - Starting scale, not locked: `cqw` / `px` size, `lineHeight`, `tracking`. Adapt for video if a size would read as web-UI (too small); keep family and weight
    - Required frontmatter keys: `name`, `description`, `colors`, `typography`
    - Each typography role needs `fontFamily` and `weight`, plus a size: `cqw` (percent of frame width, use this for display and body) or `px` (small chrome only)
    - Optional per role when the user specified them: `lineHeight`, `tracking`, `upper`, `color`
    - Optional frontmatter keys when the user specified them: `radii`, `spacing`, `components`
    - Required body sections: `## Overview`, `## Colors`, `## Typography`, `## Don'ts`
    - Default don'ts unless the user overrides them: 
        - Roughly 40% empty space
        - Minimize ornamental elements
        - No titles unless specified
- Use the new file as the `graphics_style_guide` for the remainder of this session

```markdown
---
name: <name>
description: >
  <one-paragraph description of the look>
colors:
  bg: "#0b0f14"
  text: "#f5f5f0"
  primary: "#e85d04"
  accent: "#ffba08"
typography:
  display: { fontFamily: "Space Grotesk", cqw: 4.2, weight: 700, lineHeight: 1.08, tracking: "-0.02em" }
  body:    { fontFamily: "Inter", cqw: 0.85, weight: 400, lineHeight: 1.6 }
  tag:     { fontFamily: "Space Grotesk", px: 12, weight: 500, tracking: "0.05em", upper: true }
---

# <name>

## Overview

<tone, density, what this look is for>

## Colors

<which token is ground, which is the accent, what never gets a second hue>

## Typography

<display vs body roles, locked family/weight, starting cqw/px scale, tracking>

## Don'ts

- No extra accent colors beyond the frontmatter
- Roughly 40% empty space
- Minimize ornamental elements
- No titles unless specified
```

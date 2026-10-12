# Context

## Purpose
- This is a HyperFrames `frame.md` design specification used when graphics are generated.

## Required Inputs
- A general description of the style they want for their graphics.
- A description of the palette to use.
- A description of the type and fonts to use.

## File
- Write to `configs/<name>.md`.
- The file is a HyperFrames `frame.md`.
- Use YAML frontmatter for tokens.
- Use the Markdown body for judgment.
- Quote exact hex, `fontFamily` and `weight` values verbatim.
- Use `cqw` or `px` as a starting scale.
- Adapt sizes that would read as small web interface text.
- Keep the specified font family and weight.
- Required frontmatter keys: `name`, `description`, `colors`, `typography`.
- Each typography role requires `fontFamily`, `weight` and either `cqw` or `px`.
- Optional typography keys: `lineHeight`, `tracking`, `upper`, `color`.
- Optional frontmatter keys: `radii`, `spacing`, `components`.
- Required body sections: `## Overview`, `## Colors`, `## Typography`, `## Don'ts`.
- Use these default restrictions unless the user overrides them.
    - Roughly 40% empty space.
    - Minimize ornamental elements.
    - No titles unless specified.

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

- No extra accent colors beyond the frontmatter.
- Roughly 40% empty space.
- Minimize ornamental elements.
- No titles unless specified.
```

---
name: chriselderxyz
description: >
  Chris Elder personal branding style guide. Dark teal ground, seafoam accents, white type. One family (Inter) at extreme weight contrast.
colors:
  bg: "#193843"
  text: "#ffffff"
  primary: "#70C2AB"
  accent: "#5CD6B4"
typography:
  display: { fontFamily: "Inter", cqw: 4.2, weight: 900, lineHeight: 1.08, tracking: "-0.03em", color: "text" }
  body:    { fontFamily: "Inter", cqw: 0.9, weight: 400, lineHeight: 1.55, color: "text" }
  tag:     { fontFamily: "Inter", px: 14, weight: 700, tracking: "0.08em", upper: true, color: "primary" }
---

# chriselderxyz

## Overview

Personal brand for Chris Elder: a dark teal field with seafoam as the only color that moves. Quiet, a little coastal, not neon. Graphics should feel like a name card or a single stat on that field — not a dashboard and not a startup landing page.

One type family. Weight does the hierarchy. Display is Inter 900, body is Inter 400. The gap has to read at a glance in motion.

## Colors

`{colors.bg}` `#193843` is the ground on every opaque frame. Transparent overlays keep the teal out of the fill and use it only if a panel needs a solid.

`{colors.text}` `#ffffff` is all reading type — display and body. Do not color headlines in seafoam.

`{colors.primary}` `#70C2AB` is the working accent: rules, tags, key numerals, small chrome.

`{colors.accent}` `#5CD6B4` is the brighter hit for one focal moment per graphic (a count-up, a check, a hold on the last frame). Not a second palette. Do not mix both teals at equal strength.

No extra hues. No pure black. No gray ladder.

## Typography

Locked: Inter only. Display 900, body 400, tag 700.

Starting scale (adapt if it reads as web-UI small; keep family and weight):
- display `4.2cqw` tight tracking
- body `0.9cqw` at 1.55 line-height
- tag `14px` uppercase with open tracking in primary.

No italic. No second family. No seafoam on long body copy.

## Don'ts

- No extra accent colors beyond the frontmatter
- Roughly 40% empty space
- Minimize ornamental elements
- No titles unless specified
- No Inter 500/600 as a fake middle weight — 400 or 900

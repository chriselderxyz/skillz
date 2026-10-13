# Global Context

## Shared Context
- Read `references/shared-context/definitions.md`.
- Read `references/shared-context/higgsfield.md`.
- Read `references/shared-context/thumbnail-rules.md`.
- Read `references/shared-context/thumbnail-style.md`.
- Read `references/shared-context/font-style.md`.

## Thumbnail File
- `thumbnail.af` is `<project_folder>/thumbnails/thumbnail.af`.
- Edit only the Affinity document opened from `thumbnail.af`, with the Affinity MCP tools.
- Keep the template's layers unchanged.
- **Variation** layers are named `<variation_number>-<variation_name>`.

# Phase 1: Setup

## Action 1. Open
- Open `thumbnail.af` in Affinity.

```bash
open -a Affinity "<project_folder>/thumbnails/thumbnail.af"
```

## Action 2. Read
- Read the **thumbnail style**, **font style**, and **thumbnail guidelines**.
- Read the layers in `thumbnail.af`.

# Phase 2: Build

## Phase Context
- Run the actions in this phase for each **variation**, one at a time.
- Save the `thumbnail.af` between **variations**.

## Action 1. Plan
- Give a new **variation** the next `variation_number` after the highest in `thumbnail.af`, starting at 1.
- Plan a new **variation**'s composition, text, and **assets** from its description, `video_description`, the thumbnail rules, and the **thumbnail guidelines**:
    - Use its **concept** image as a starting point when it has one.
- Plan only the changes an existing **variation**'s feedback asks for.

## Action 2. Assets
- Use the **assets** in the **thumbnail guidelines** and local images named in the **variation** description.
- Modify **assets** however the plan needs, with the modifications in the **thumbnail guidelines** as examples.
- Generate every other **asset** as a text-free image with `gpt_image_2` at `quality` `high` and `resolution` `2k`.
- Use `aspect_ratio` `16:9` for full-frame **assets**.
- Reference the **variation**'s **concept** in `medias` when it has one.
- Cut out each **asset** that needs a transparent background with the Higgsfield MCP `remove_background` tool.
- Save each generated **asset** to `<project_folder>/thumbnails/assets/<asset_name>.png`, with a unique kebab-case `asset_name`.

## Action 3. Layout
- Create a new **variation**'s layer directly below the template's `Youtube Element Guides` layer.
- Show the **variation**'s layer and hide the other **variation** layers.
- Build a new **variation**'s plan in its layer, or apply an existing **variation**'s planned changes.
- Copy each **asset** to `~/Desktop/z-make-thumbnail/` (if it is not already there), then place it in Affinity from that copy.
- Draw the background by running `scripts/draw-background.js` with the Affinity MCP `execute_script` tool, with its inputs set:
    - `DOCUMENT_PATH`: The absolute path of `thumbnail.af`.
    - `LAYER_NAME`: The **variation**'s layer name.
    - `STYLE`: The **thumbnail style** JSON.
- Write all text as editable Affinity text in the **font style**.
- Color text and other elements with the **thumbnail style**'s `foreground_colors`, `outline_color`, and text box colors.

## Action 4. Verify
- Render `thumbnail.af` with the Affinity MCP `render_spread` tool.
- Fix where the render misses the **variation**'s plan, the thumbnail rules, the **thumbnail style**, the **font style**, or the **thumbnail guidelines**, then render again.
- Cap at 3 passes.

# Phase 3: Respond

- Return each **variation**'s layer name, a one-line summary of what was built or changed, and any remaining issues.

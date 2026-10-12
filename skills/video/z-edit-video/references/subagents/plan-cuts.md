# Global Context

## References
- Read `references/shared-context/concepts.md`.
- Read `references/shared-context/cutting.md`.
- Read `references/shared-context/edit-json.md`, you are responsible for writing or editing the `scenes` top level property.

## Read Assets
- Read `video_style` from `edit/edit.json`.

## Initial Run vs. Edit Runs
- Edit Runs are to incorporate user feedback into a plan that was already created during the Initial Run.
- For Edit Runs.
  - Read the existing `edit/edit.json` first.
  - Skip Phase 1 - scenes, lines and takes have already been grouped.
  - If no new takes were manually selected by the user, skip Phase 2.
    - If a new take was selected, only apply the silence cuts to that.
  - Edit `edit/edit.json` in place, keeping every existing identifier on the **scene**, **line**, and **take** it already names.
  - When changing **layers**, use Phase 3.
  - After take-only edits, update each footage **layer** so its `cuts` still match the kept take.
    - Follow the clock rules in `references/shared-context/edit-json.md`.

# Phase 1: Select Takes

## Action 1. Assemble
- Step through `takes-packed.md`.
- Find **takes**, group them into **lines**, and group **lines** into **scenes**.
- Select the **scene** order.
- For each **line**, select a **take** to keep, the others get cut.
- Write the **scenes**, **lines** and **takes** to `edit/edit.json` under `scenes`.
- Apply `cut_padding_ms` and `line_gap_ms` to kept takes.
- Follow the shape and rules in `references/shared-context/edit-json.md`.

# Phase 2: Cut Silences

## Phase Context
- Eleven labs can extend word ranges into silence, which can cause some mid **take** silences to appear.

## Action 1
- For each kept **take**, use only `edit/silences.json` `sources.<audio_source>`, where `<audio_source>` is that **take**'s `audio_source`.
- Those `start` and `end` times are on the **audio source clock**.
- A silence that falls inside the kept **take** splits it into separate **cuts** in the same **take**, same **line**, and same **scene**.
- Apply cutting guidelines.
- Update `edit.json` with any split **cuts**.

# Phase 3: Plan Layers

## Action 1. Search for Pages
- Skip when `video_style.browser_enabled` is not true.
- Skip on an edit run that does not add or change a browser recording.
- Run a subagent with the following prompt.
- Wait for it before you plan any browser recording.
- The agent only returns options, use your judgement and do not blindly suggest they should all be in the video.

```md
You are searching for supporting content online for this video

`references/` resolves from the skill directory
`edit/edit.json` and `edit/takes-packed.md` are in the working directory

Execute `references/subagents/search-browser-pages.md`
```

## Action 2. Build the Stack
- Step through each **scene** and **line**.
- For each **line**, read the kept **take** transcript.
- Choose every **layer** on that **line** from `video_style.allowed_layouts`, that transcript, and where the **line** sits in the planned video.
- Follow the Layers and Zoom Cuts sections in `references/shared-context/cutting.md`.
- Write the `layers` array on the **line** in `edit/edit.json`.
- Follow the layer shape in `references/shared-context/edit-json.md`.
- For a new `animation` or `image`, add `sources.<name>` with that `type` and `description`, and set the **layer** `source` to that name.
- To see what an **overlay graphic** covers, grab a still of the **source** under it.

```bash
uv run --no-project scripts/inspect/screenshot.py <source-path> --time <seconds> \
  -o edit/overlay-stills/<source-name>-<seconds>.png
```

- For a new browser recording, add `sources.<name>` with `type` `browser`, `description`, and `actions`, and set the **layer** `source` to that name.
- Use a page that search returned.
  - Put that page's `url` on an `open` action.
  - Put phrases from that page on `scroll` `to` and `highlight` `text`.
- Omit `path` on a new browser recording.
- Follow the Browser Recordings section in `references/shared-context/cutting.md`.
- Set `"zoom_cut": true` on each chosen full-frame `head` **layer**.

# Phase 4: Check

## Action 1
- Run the script to check `edit/edit.json`.

```bash
uv run --no-project scripts/production/build_plan_html.py --cuts-only
```

- Correct `edit/edit.json` and rerun until it reports no problems.

# Phase 5: Respond

## Action 1
- Return the **scenes**, **lines**, and **layers** you added, removed, or changed.

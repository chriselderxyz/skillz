# Global Context

## References
- Read `references/shared-context/concepts.md`.
- Read `references/shared-context/edit-json.md`, you are responsible for writing or editing the `scenes` top level property.

## Read Assets
- Read `video_style` and `pip_style` from `edit/edit.json`.
- Follow `video_style.other_instructions`.

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

## Cutting Guidelines
- Cut edges sit on word boundaries or in silence gaps.
  - Silence gaps are the cleanest edges.
- Every cut has to work on both audio and picture, with the video following the audio.
- Cut fluff, false starts, and sync claps (loud, standalone claps).
- Preserve the peaks (laughs, punchlines, emphasis).
  - Extend past a punchline to include the reaction.
- Pad both edges of every cut with `video_style.cut_padding_ms`.
- Leave `video_style.line_gap_ms` of air at a **line** change or a speaker handoff.
- When `video_style.cut_fillers` is true, cut filler words such as um, uh, and ah.
- When `video_style.cut_breaths` is true, cut breaths.
- When `video_style.cut_keyboard` is true, cut keyboard clacking.
  - When keyboard clacking stays, the user will review each keyboard only section themselves.

# Phase 1: Select Takes

## Phase Context

### Packed Transcript
- `edit/takes-packed.md` holds a phrase-level transcript of each **source group**'s **audio source**, each phrase prefixed by its `[start-end]` range.
- Phrases break on any silence ≥ 0.5s or a speaker change.
- Diarization arrives as `S0` / `S1`.
- Audio events arrive in parentheses: `(laughs)`, `(sighs)`, `(applause)`.

Example.
```
## Source Group 1 — 1-head  (duration: 43.0s, 8 phrases)
  [002.52-005.36] S0 Ninety percent of what a web agent does is completely wasted.
  [006.08-006.74] S0 We fixed this.
```

### Take Selection
- Where a **line** is repeated, `video_style.take_selection_mode` picks the kept **take**.
  - `best` keeps the best **take** (usually the last).
- Keep an unavoidable slip when no better **take** exists, and write why on the kept **take**'s `reason`.

### Lines
- **Takes** usually come from the same **source**, but may be in more than one.
- An `(applause)` or `(laughs)` token is a signal that a **line** landed.

### Scenes
- `video_style.opening_type` sets how the video opens.
  - `cold-open` starts on the claim or the action, with no greeting.
  - `greeting` allows a hello or intro line.
  - `text-card` opens on a text graphic.
- Keep the close that was filmed (a recap, a call to action, a sign-off, a hard stop, a loop, a callback, or a tease).
- When ordering **scenes**, consider both the **source** order AND how each **line** should fit together so the video flows and makes sense.
  - A **line** from a later **source group** may play first.

Example **Scene** types/flows.
- Tech launch / demo:   HOOK → PROBLEM → SOLUTION → BENEFIT → EXAMPLE → CTA.
- Tutorial:             INTRO → SETUP → STEPS → RECAP.
- Interview:            (QUESTION → ANSWER → FOLLOWUP) repeat.
- Travel / event:       ARRIVAL → HIGHLIGHTS → QUIET MOMENTS → DEPARTURE.
- Documentary:          THESIS → EVIDENCE → COUNTERPOINT → CONCLUSION.
- Music / performance:  INTRO → VERSE → CHORUS → BRIDGE → OUTRO.
- These are only examples, use your judgement or invent your own.

## Action 1. Assemble
- If you were given a `script` path, read it and use it as a guide to the intended shape of the video.
- Step through `edit/takes-packed.md`.
- Find **takes**, group them into **lines**, and group **lines** into **scenes**.
- Select the **scene** order.
- For each **line**, select a **take** to keep, the others get cut.
- Cut each kept **take** with the Cutting Guidelines.
- Write the **scenes**, **lines** and **takes** to `edit/edit.json` under `scenes`.

# Phase 2: Cut Silences

## Action 1
- For each kept **take**, use only `edit/silences.json` `sources.<audio_source>`, where `<audio_source>` is that **take**'s `audio_source`.
- Those `start` and `end` times are on the **audio source clock**.
- A silence that falls inside the kept **take** splits it into separate **cuts**.
- Apply the Cutting Guidelines to each new cut edge.
- Update `edit/edit.json` with any split **cuts**.

# Phase 3: Plan Layers

## Phase Context

### Layer Choice
- `video_style.allowed_layouts` maps to `frame` values.
  - `full` allows `frame` `full`.
  - `top-bottom-split` is `frame` `top` and `frame` `bottom` on the same **line**.
  - `pip` allows `frame` `pip` over the **layers** under it.
- A **line** has at most one full-frame footage **layer**.
  - To switch footage **sources** partway through, split the **line**.
- When the **line** explains something on screen, use the `screen` **source** when one is available.
- When the **line** explains a provided `animation` or `image`, use that **source**.
- When the **line** is about a webpage or a page can support its point, use a `screen` **source** that shows that page, or else a browser recording.
- Prefer a `head` **source** for a conclusion, a punchline, or a move to a new point.
- Avoid a flash of `head` between two shots of the same other **source**.
- Use a **B-Roll** **source type** on a **layer** to support a cut or add visual interest.
- Check **A-Roll** and **B-Roll** before adding a graphic or browser recording.
- Keep each full-frame **source** up for at most `video_style.max_continuous_shot_length_ms`.
- Keep each **full graphic**, **overlay graphic**, and browser recording inside its `video_style` `min_<type>_length_ms` and `max_<type>_length_ms` when those fields are set.
- A graphic or browser recording that explains a point must be readable at 1x.
  - A graphic at its minimum length only has to be recognizable at 1x.

### Graphics
- Use an `animation` when the content looks better with motion (ex. `npm install` typing on from left to right).
- Use an `image` when nothing on it needs to move.
- When an `animation` or `image` shows text, write each piece of text word for word in its `text_elements`.
- Only add a **full graphic** when `video_style.full_graphics_enabled` is true.
- Only add **overlay graphics** of a type listed in `video_style.overlay_graphic_types`.
  - `creator-credit`: credits a `clip` **source** each time it comes on screen.
    - Write its `text_elements` from the `credit` of its `credited_source`.
    - Only write `credit` values the user gave.
  - `hook-text`: the hook, as text, in the opening seconds.
  - `context`: anything that gives context to what is on screen.
  - `text-story`: **overlay graphics** that tell a story with text.
  - `cta`: a call to action.
- Place each **overlay graphic** with `frame` `{ "x", "y", "w", "h" }` sized to its content.
  - Use `frame` `full` only when the **overlay graphic** spans the frame.
- Keep **overlay graphics** off faces, captions, the `pip` **layer**, and what the **line** is about.

### Browser Recordings
- Use a page that search returned.
  - Put that page's `url` on an `open` action.
  - Put its phrases on `scroll` `to` and `highlight` `text`.
- The first action is `open` at `00:00:00.00`.
- Leave at least 0.8s after each action.

### Zoom Cuts
- Only add zoom cuts when `video_style.zoom_cut` is true.
- A zoom cut jumps a full-frame `head` **layer** tighter by `video_style.zoom_amount`, centered inside its crop. The next **line** without one is back at that crop.
- Only apply a zoom cut when the previous **line** is also a full-frame `head` shot.
- You can use a zoom cut for.
  - **lines** that land a point: a punchline, a number, a turn.
  - **lines** in a longer section: used as an effect to increase engagement instead of emphasis on a point, best when no other **layer** is already varying the shot.
- Consecutive **lines** with a zoom cut count as one zoom cut.
- Leave at least 2 **lines** without a zoom cut between zoom cuts.
  - Leave more than 2 unless both zoom cuts land an important point.

### Picture in Picture
- Add a `pip` **layer** only when `pip_style` is set.
- `pip` is only applied to `head` **sources**.
- ALWAYS add a `pip` **layer** when a `head` **source** is available and another **layer** on the **line** is a `screen` **source**, a **full graphic**, or a full frame browser recording.
  - A `pip` **layer** may also go over other **source types**.
- Skip the `pip` **layer** when a `head` **source** is already `frame` `full`.

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
- Build every **layer** on that **line** together, from `video_style.allowed_layouts`, that transcript, and where the **line** sits in the planned video.
- Write the `layers` array on the **line** in `edit/edit.json`.
- For a new `animation`, `image`, or browser recording, add `sources.<name>` and set the **layer** `source` to that name.
- To see what an **overlay graphic** covers, grab a still of the **source** under it.

```bash
uv run --no-project scripts/inspect/screenshot.py <source-path> --time <seconds> \
  -o edit/overlay-stills/<source-name>-<seconds>.png
```

- Set `"zoom_cut": true` on each full-frame `head` **layer** chosen for a zoom cut.

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

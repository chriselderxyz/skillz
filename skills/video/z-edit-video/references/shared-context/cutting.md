# Packed Transcript

- `edit/takes-packed.md` contains time-annotated (prefixed by its `[start-end]` range) phrase-level transcripts of all **takes**.
- Phrases break on any silence ≥ 0.5s or a speaker change.
- Each **take** is labeled with the **source group** it belongs to and the source name.
- Each **source group** comes from a single **source** used to compose the video.
- This **packed transcript** is what you read to do cuts.

Example.
```
## Source Group 1 — 1-head  (duration: 43.0s, 8 phrases)
  [002.52-005.36] S0 Ninety percent of what a web agent does is completely wasted.
  [006.08-006.74] S0 We fixed this.
```

- Diarization arrives as `S0` / `S1`.
- Audio events arrive in parentheses: `(laughs)`, `(sighs)`, `(applause)`.

# Cutting Guidelines

## Cut Location
- Every cut candidate comes from a word boundary or a silence gap.
- Cut fluff and false starts.
- Video follows the audio, never the reverse.
- Never reason about audio and picture separately, a cut has to work on both tracks or it is not a cut.

## Word Boundaries
- Do not cut mid-phrase or mid-word.
- Preserve the peaks (laughs, punchlines, emphasis).
- Extend past a punchline to include the reaction — keep the laugh, and cutting when the words end loses it.

## Sync Claps
- Loud, standalone claps are used for syncing audio, they get cut.

## Padding and Gaps
- Pad both edges of all cuts with `<video_style>.cut_padding_ms`.
- Leave air between **lines** — `<video_style>.line_gap_ms` at a **line** change or a speaker handoff.

## Silence
- Silence gaps are the cleanest edges.
  - Gaps at or above `<video_style>.silence_cut_threshold_ms` are cut.
  - Gaps below that threshold are not cut.

## Style Specific Cuts
- When `<video_style>.cut_fillers` is true, cut filler words such as um, uh, and ah.
- When `<video_style>.cut_breaths` is true, cut breaths.
- When `<video_style>.cut_keyboard` is true, cut keyboard clacking.
  - When keyboard clacking stays, the user will review each keyboard only section themselves.

## Image Reasoning
- Reach for `scripts/inspect/timeline_view.py` when the text alone cannot settle a question.
  - An ambiguous pause.
  - Two **takes** that read identically.
  - A cut edge you do not trust.
- It is a drill-down, not a scan: one image per decision, not one per utterance.

```bash
uv run --no-project --with numpy --with Pillow scripts/inspect/timeline_view.py <src>/<n>-head.mp4 <start> <end> \
  -o edit/verify/<n>-head_<start>-<end>.png
```

## Take Selection
- This is the bulk of the cutting work.
- An unavoidable slip is kept when no better **take** exists (write the reason down on the kept take's `reason` field so it is not "corrected" back).
- Where a line is repeated, `<video_style>.take_selection_mode` picks the kept **take**.
  - `best` keeps the best **take** (usually the last).
  - `last` keeps the last **take**.
  - `highest-energy` keeps the **take** with the most energy.
- Takes may be comprised of more than one cut range from a source (ex. cut out a bad middle).

# Zoom Cuts
- A zoom cut jumps the full-frame camera shot tighter inside its crop, then the next **line** without one is back at that crop.
- Apply these only when `<video_style>.zoom_cut` is true.
- `<video_style>.zoom_amount` is the scale. `1` is the crop. `1.15` is 15% tighter, centered inside the crop.
- Only apply zoom cuts to a `head` **source type**.
- Only apply zoom cuts to `full` **layers**.
- Do not apply zoom cuts to `pip` **layers**.
- Only apply a zoom cut when the previous **line** is also a full-frame `head` shot.
- You can use a zoom cut for.
  - **lines** that land a point: a punchline, a number, a turn.
  - **lines** in a longer section: used as an effect to increase engagement instead of emphasis on a point, best when no other **layer** is already varying the shot.
- You can apply a zoom cut to consecutive **lines**, they count as one zoom cut.
- Leave at least 2 **lines** without a zoom cut between zoom cuts.
  - Leave more than 2 unless both zoom cuts land an important point.

# Layers
- Build every **layer** on a **line** together.
- Choose the stack from `video_style.allowed_layouts`, that **line**'s transcript, and where that **line** sits in the planned video.
- `layers` is painted back to front.
- Use only layouts listed in `video_style.allowed_layouts`.
  - `full` allows `frame` `full`.
  - `top-bottom-split` is `frame` `top` and `frame` `bottom` on the same **line**.
  - `pip` allows `frame` `pip` over the **layers** under it.
- Each line can have at most one full-frame video layer (not including graphics which can have transparency).
  - Switching to a different video source partway through means splitting the line.
- When the **line** explains something on screen, use the `screen` **source** when one is available.
- When the **line** explains a provided `graphic`, use that `graphic` **source**.
- When the **line** explains a webpage that no `screen` **source** already shows, use a browser recording **source**.
- Prefer a `head` **source** for a conclusion, a punchline, or a move to a new point.
- Avoid a flash of `head` between two shots of the same other **source**.
- Use a **B-Roll** **source type** on a **layer** to support a cut or add visual interest.
- Do not leave the same full-frame **source** up longer than `video_style.max_continuous_shot_length_ms`.
- The same **source** can stay up across consecutive **lines**.
  - Each **line** still has its own `layers` entry, with that **line**'s `edit_start`, `edit_end`, and `cuts`.

## Graphics
- When `video_style.full_frame_graphics_enabled` is true, a graphic may be a `frame` `full` **layer**.
- When `video_style.graphic_overlays_enabled` is true, a graphic may sit over other **layers**.
  - An overlay is `frame` `full`. Transparent pixels show the **layers** under it.
- When both flags are false, do not add a graphic.
- Check **A-Roll** and **B-Roll** before adding a graphic.
- Keep each graphic between `video_style.min_graphic_length_ms` and `video_style.max_graphic_length_ms` when those fields are set.
- A graphic that explains a point must be readable at 1x.
- A graphic at `min_graphic_length_ms` only has to be recognizable at 1x.

## Browser Recordings
- A browser recording is a headless screen recording of one or more webpages.
- The **source** `type` is `browser`.
- When `video_style.browser_enabled` is false, do not add any browser recordings.
- Check **A-Roll** and **B-Roll** before adding a browser recording.
- Use a `screen` **source** when one already shows that page.
- Use a `graphic` for a designed motion graphic.
- Use a browser recording when the **line** is about a public webpage or the page can support a point.
- The page has to render without an account, and the words have to be on screen.
- A one-click banner is cleared before the page is on screen.
- A page that still covers the words is not used.
- A browser recording **layer** may use `frame` `full`, `top`, `bottom`, or `{ "x", "y", "w", "h" }`.
- A browser recording **layer** has no cuts.
- Do not apply a zoom cut to a browser recording.
- Add `description` and `actions` on the **source**.
- Omit `path` until the recording exists.
- `actions` run on the recording clock.
  - The recording clock starts at `00:00:00.00` when that browser recording starts.
  - That is not the **edit clock**.
  - Each page is already loaded when its `open` starts.
- The first action is `open` at `00:00:00.00`.
- Every `open` has `url` and shows that page.
- A recording can `scroll` more than once.
- `scroll` has `to`, the words to bring into view.
- `highlight` has `text`, the words to mark.
- A highlight marks the first match and stays up.
- `highlight` `text` has to be one specific phrase on the page.
- Leave at least 0.8s after `open` before the next action.
- Leave at least 0.8s after a `scroll` before the next action.
- Leave a highlight up for at least 0.8s.
- Keep each browser recording between `video_style.min_browser_length_ms` and `video_style.max_browser_length_ms` when those fields are set.
- A browser recording that explains a point must be readable at 1x.
- Record the page at that **layer**'s size.
  - `full` uses `video_settings` `resolution` and `orientation`.
  - `top` and `bottom` each use half of that.
  - `{ "x", "y", "w", "h" }` uses that window.

## Picture in Picture
- Add a `pip` **layer** only when `pip` is in `video_style.allowed_layouts` and `pip_style` is set.
- `pip` is only applied to `head` **sources**.
- Add a `pip` **layer** when a `head` **source** is available and another **layer** on the **line** is a `screen` **source**, a full frame graphic, or a full frame browser recording.
- Do not add a `pip` **layer** when a `head` **source** is already `frame` `full`.

# Line Guidelines
- Group **takes** into **lines** based on the transcript's meaning.
- **Takes** usually come from the same **source**, but may be in more than one.
- Slight wording differences between **takes** are still grouped in the same **Line**.
- Audio events mark **lines**: An `(applause)` or `(laughs)` token is a signal that something landed.

# Scene Guidelines
- Group **lines** into **scenes** based on story/video flow.
- `<video_style>.opening_type` sets how the video opens.
  - `cold-open` starts on the claim or the action, with no greeting.
  - `greeting` allows a hello or intro line.
  - `question` opens on a question.
  - `text-card` opens on a text graphic.
  - `mid-action` starts inside an action already underway.
- The ending comes from what was filmed.
  - Keep the close that is already in the takes.
  - A recap, a call to action, a sign-off, a hard stop, a loop, a callback, or a tease stays when that close was filmed.
- Follow `<video_style>.other_instructions`.
- If you were given a path to a `script.md` file, read it.
  - Use the script as a guide to the intended shape of the video.
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

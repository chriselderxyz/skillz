# Context

## Concepts
Read `<skill_dir>/references/shared-context/concepts.md`

## Packed Transcript

- `edit/takes_packed.md` contains time-annotated (prefixed by its `[start-end]` range) phrase-level transcripts of all takes
- Phrases break on any silence ≥ 0.5s or a speaker change
- Each take is labeled with the segment it belongs to and the source file name
- Each segment comes from a single clip used to compose the video
- This is what you read to do cuts

Example
```
## Segment 1 — 1-head  (duration: 43.0s, 8 phrases)
  [002.52-005.36] S0 Ninety percent of what a web agent does is completely wasted.
  [006.08-006.74] S0 We fixed this.
```

- Diarization arrives as `S0` / `S1`
- Audio events arrive in parentheses: `(laughs)`, `(sighs)`, `(applause)`

## Read Assets
- Read `<skill_dir>/assets/video-types/<video_type>.json` to get the values for `cut_padding_ms`, `beat_gap_ms`, and `silence_cut_threshold_ms`

# Cutting Guidelines

## Cut Location
- Every cut candidate comes from a word boundary or a silence gap
- Cut filler words, fluff, and false starts
- Video follows the audio, never the reverse
- Never reason about audio and picture separately, a cut has to work on both tracks or it is not a cut

## Word Boundaries
- Do not cut mid-phrase or mid-word
- Preserve the peaks (laughs, punchlines, emphasis)
- Extend past a punchline to include the reaction — the laugh is the beat, and cutting on the line loses it

## Padding and Gaps
- Pad both edges of a cut with `<video_type>.cut_padding_ms`
- Leave air between beats — `<video_type>.beat_gap_ms` at a beat change or a speaker handoff

## Silence
Silence gaps are the cleanest edges
- Gaps at or above `<video_type>.silence_cut_threshold_ms` are cut
- Gaps below that threshold are not cut

## Image Reasoning
- Reach for `scripts/inspect/timeline_view.py` when the text alone cannot settle a question
  - An ambiguous pause
  - Two takes that read identically
  - A cut edge you do not trust
- It is a drill-down, not a scan: one image per decision, not one per utterance

```bash
uv run --no-project --with numpy --with Pillow <skill_dir>/scripts/inspect/timeline_view.py <src>/<n>-head.mp4 <start> <end> \
  -o edit/verify/<n>-head_<start>-<end>.png
```

## Take Selection
- This is the bulk of the cutting work
- An unavoidable slip is kept when no better take exists (write the reason down in the cut list's `reason` field so it is not "corrected" back)
- Where a line is repeated, keep the best take, which is usually the last one

## Beat Guidelines
- Group takes into beats based on the transcript's meaning
- Slight wording differences between takes are still grouped in the same Beat
- Audio events mark beats: An `(applause)` or `(laughs)` token is a signal that something landed

## Scene Guidelines
- Group beats into scenes based on story/video flow
- If you were given a path to a `script.md` file, read it
  - Use the script as a guide to the intended shape of the video
- When ordering scenes, consider both the source clip order AND how each beat should fit together so the video flows and makes sense
  - A beat from a later segment may play first
- If the user asks for it, a single beat may be used in multiple scenes (ex. a teaser beat in the Intro scene)

Example Scene types/flows
- Tech launch / demo:   HOOK → PROBLEM → SOLUTION → BENEFIT → EXAMPLE → CTA
- Tutorial:             INTRO → SETUP → STEPS → GOTCHAS → RECAP
- Interview:            (QUESTION → ANSWER → FOLLOWUP) repeat
- Travel / event:       ARRIVAL → HIGHLIGHTS → QUIET MOMENTS → DEPARTURE
- Documentary:          THESIS → EVIDENCE → COUNTERPOINT → CONCLUSION
- Music / performance:  INTRO → VERSE → CHORUS → BRIDGE → OUTRO
- These are only examples, use your judgement or invent your own

# Workflow

## Select Takes
- Step through `takes_packed.md`
- Group takes into Beats, and group beats into scenes
- Select the Scene order
- For each beat, select a take to keep, the others get cut

## Write Results

- Write the results to `edit/plan.html` under the `Plan` heading
- Each scene should have its own `<Scene Name>` subheading
- Scenes are written in order
- Each Scene section should include
  - All beats in that scene
  - All takes in each beat
  - Markers to label which takes were cut, with reasoning as to why

Use the example HTML file at `<skill_dir>/assets/templates/plan.html` as a guide to structure the output

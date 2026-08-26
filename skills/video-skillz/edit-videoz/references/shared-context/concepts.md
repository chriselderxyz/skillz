# Concepts

## Segment
- A numbered group of clips (`<n>-head`, `<n>-screen`, `<n>-audio`)
- Artifacts for that group live in `edit/<n>/`

## Clip
- Numbered raw video clips in `<src>` in the format `<n>-<clip-type>`
- The number on a clip is the segment it belongs to
- If clips are not numbered, stop and ask the user to number them

## Clip Types
- `head`: A talking head camera shot
- `screen`: A screen recording
- `audio`: Audio only

## Take
- One line in a series of repeated lines
- We are looking to keep the best takes
- Each take belongs to a Beat

## Beat
- A set of takes that repeat the same words or meaning

## Scene
- A set of Beats
- Each Scene tells a story or serves a purpose in the video flow, using a group of Beats

## Clocks
- Segment clock: `ranges` — time on that segment's audio reference clip
- Edit clock: `graphics`, `pip` — time in `edit.mp4`

## Audio Reference Clip
- For a segment with multiple clips, the clip audio is sourced from and secondary clips are synced on

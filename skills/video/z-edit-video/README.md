# Edit Video

## Summary

This skill edits numbered raw sources into one finished video. It records your format and style choices, syncs and transcribes the footage, then plans the cut with you through a review loop. After you approve the plan, it renders a draft, checks the edit, and renders a finalized QuickTime movie with uncompressed audio. When you ask it to process audio, Auphonic runs speech isolation, AutoEQ, and loudness normalization, and writes a transcript, subtitles, shownotes, and chapters. It then writes `edit/edit.mp4`.

## Features

- Multi-source sync.
- Transcription.
- Cut planning.
- Full-frame crops.
- Picture-in-picture.
- Color grading.
- Burned-in captions.
- Subtitle file.
- Motion graphics.
- Browser recordings.
- Plan review.
- Draft review.
- Finalized render.
- Auphonic audio processing.
- Chapter markers.
- Reusable configs.

## Inputs

The skill asks for any of these that you have not already provided, then confirms them before planning starts.

| Input | Required | Choices | What it controls |
| --- | --- | --- | --- |
| `video_settings` | Yes | A file in `configs/video-settings/`, or create new | Output shape, frame rate, and loudness target |
| `video_style` | Yes | A file in `configs/video-styles/`, or create new | Cut timing, cleanup, layouts, graphics, and how the video opens |
| `description` | Yes | Free text | What the video is about. The cut planner uses this |
| `caption_style` | No | A file in `configs/caption-styles/`, `none`, or create new | Captions burned into the picture |
| `srt_style` | No | A file in `configs/srt-styles/`, `none`, or create new | A sidecar SubRip subtitle file (`.srt`) |
| `pip_style` | No | A file in `configs/pip-styles/`, `none`, or create new | The picture-in-picture inset |
| `grading_style` | No | A file in `configs/grading-styles/`, `none`, or `auto` | Color grade. `auto` generates options for you to pick |
| `graphics_style_guide` | No | A file in the create-graphics skill `configs/`, a file path, or create new | Look of generated graphics. Skipped when the video style turns both graphics flags off |
| `generate_chapters` | No | `true` or `false` | Whether `edit/chapters.md` is written with the finalized render |
| `process_audio` | No | `true` or `false` | Whether Auphonic processes the finalized movie |
| `src` | No | A folder. Default is the working directory (`.`) | Where the raw sources live |
| `script` | No | A file path | The planned spoken script. The skill still transcribes the sources on its own |

`create new` writes a config with the create-config skill. Graphics style guides are written for the create-graphics skill. The other new configs are written for this skill.

## Definitions
- **Source** -> A raw video file.
- **Source Group** -> **Sources** that share a number and are synced together.
- **Audio Source** -> The **source** audio is taken from in each **source group**.
- **Line** -> One thing the speaker says, and every attempt at saying it.
- **Take** -> One attempt at a **line**.
- **Cut** -> One continuous section of a **source** inside a **take**.
- **Scene** -> A group of **lines** that serves one purpose in the video.
- **Layer** -> One picture in a **line**, stacked back to front.
- **Picture-in-picture** -> The inset **layer**, frame `pip`.

## Source Types

Sources in `src` are named `<source-group>-<source-type>`, for example `1-head.mp4` and `1-screen.mov`. The number is the source group. Sources that share a number are one source group and are synced together.

| Source type | Role | Typical use |
| --- | --- | --- |
| `screen` | Main footage | Screen recording, often with a picture-in-picture face |
| `head` | Main footage | Talking-head camera |
| `graphic` | Main footage | A motion graphic you already have |
| `browser` | Main footage | A browser recording of a webpage. The skill generates it |
| `audio` | Main footage | Audio recorded with the main footage |
| `wide` | Extra footage | A wide shot of the place |
| `detail` | Extra footage | A close-up |
| `reaction` | Extra footage | Someone reacting |
| `cutaway` | Extra footage | A short shot that bridges a cut |
| `voiceover` | Extra footage | Audio recorded separately from the picture |

## Config Files

Configs live in `configs/` and are copied into `edit/edit.json` under the same name as the input. A choice of `none` is left out of `edit.json`. `grading_style` is also left out while it is still `auto`, and written after you pick a grade.

| Folder | Chooses |
| --- | --- |
| `configs/video-settings/` | Output format |
| `configs/video-styles/` | Cut timing and edit style |
| `configs/caption-styles/` | Burned-in caption look and line wrapping |
| `configs/srt-styles/` | Sidecar subtitle line wrapping |
| `configs/pip-styles/` | Picture-in-picture size, shape, and placement |
| `configs/grading-styles/` | Color grade passed to ffmpeg |

### Video settings

| File | Orientation | Resolution | Frame rate |
| --- | --- | --- | --- |
| `short-30.json` | Portrait (9:16) | HD (1080×1920) | 30 |
| `short-29.97.json` | Portrait (9:16) | HD (1080×1920) | 29.97 |
| `youtube-long.json` | Landscape (16:9) | 4K (3840×2160) | 29.97 |

All three target −14 LUFS (loudness units relative to full scale).

| Field | Meaning |
| --- | --- |
| `orientation` | `landscape` (16:9) or `portrait` (9:16) |
| `resolution` | `HD` or `4K`. This is the export size, combined with orientation |
| `fps` | Output frame rate |
| `target_lufs` | Integrated loudness target for Auphonic. Omit it to skip loudness normalization |

### Video styles

| File | Open | Picture |
| --- | --- | --- |
| `long-talking-head.json` | Greeting | Full frame, split, and picture-in-picture. A shot may hold up to 60 seconds |
| `short-talking-head.json` | Cold open | Full frame and picture-in-picture. A shot may hold up to 4 seconds |
| `short-talking-head-retention.json` | Cold open | Full frame and picture-in-picture. A shot may hold up to 2 seconds |
| `short-text-only-single-clip.json` | Text card | One full-frame clip with text overlays |
| `short-text-only-multi-clip.json` | Text card | Full-frame text cards and text overlays. A shot may hold up to 2.5 seconds |

| Field | Meaning |
| --- | --- |
| `cut_padding_ms` | Padding kept on each side of a cut |
| `line_gap_ms` | Air when a cut changes line or speaker |
| `silence_cut_threshold_ms` | Silences longer than this are removed. `cut_padding_ms` still applies |
| `cut_fillers` | Remove um, uh, ah, and similar fillers |
| `cut_breaths` | Remove breaths |
| `cut_keyboard` | Remove keyboard clacking |
| `take_selection_mode` | `last`, `best`, or `highest-energy` |
| `b_roll_enabled` | Stored on the style. The cut planner does not read it yet |
| `full_frame_graphics_enabled` | A graphic may be the picture |
| `graphic_overlays_enabled` | A graphic may sit over other layers |
| `min_graphic_length_ms` | Shortest graphic |
| `max_graphic_length_ms` | Longest graphic |
| `browser_enabled` | A browser recording may be a layer |
| `min_browser_length_ms` | Shortest browser recording |
| `max_browser_length_ms` | Longest browser recording |
| `max_continuous_shot_length_ms` | Longest one full-frame source may stay up |
| `allowed_layouts` | `full`, `top-bottom-split`, `pip` |
| `opening_type` | `cold-open`, `greeting`, `question`, `text-card`, or `mid-action` |
| `zoom_cut` | Allow a jump to a tighter view of a full-frame `head` shot. Talking-head styles turn this on |
| `zoom_amount` | How much tighter that jump is. `1` is the crop. `1.15` is 15% tighter |
| `other_instructions` | Extra instructions for this style |

### Caption styles

Shipped style: `chriselderxyz.json` (uppercase Impact, one short line, teal stroke, sitting near the bottom of the frame). Word highlighting is off.

| Field | Meaning |
| --- | --- |
| `case` | `upper`, `lower`, `title`, or `normal` |
| `chars_per_line` | Maximum characters on a caption line |
| `num_lines` | Maximum lines on screen at once |
| `font_name` | Font name |
| `font_size` | Size in pixels |
| `bold`, `italic`, `underline`, `strike_out` | Type style flags |
| `spacing` | Extra pixels between characters |
| `angle` | Rotation in degrees |
| `text_color` | Text color, as hex |
| `stroke_color` | Stroke color, as hex |
| `back_color` | Shadow color, as hex |
| `border_style` | `1` for a stroke and shadow, `3` for an opaque box |
| `stroke_thickness` | Stroke thickness in pixels. With `border_style` `3`, this is the box padding |
| `shadow` | Shadow size in pixels |
| `alignment` | Numpad position (`2` is bottom center) |
| `margin_v` | Vertical margin in pixels. 90 or more keeps captions off the frame edge |
| `word_highlight` | Restyle the word being spoken. Off when omitted. Requires at least one highlight field |
| `highlight_text_color` | Spoken-word fill, as hex |
| `highlight_stroke_color` | Spoken-word stroke color, as hex |
| `highlight_stroke_thickness` | Spoken-word stroke thickness in pixels |
| `highlight_zoom` | Spoken-word scale. `1.15` is 15% larger |
| `highlight_bold` | Bold on the spoken word. Turn this on with a thicker stroke |

### Subtitle styles

Shipped style: `default.json` (42 characters per line, 2 lines). Sidecar subtitles are sentence case. The style only sets wrapping.

| Field | Meaning |
| --- | --- |
| `chars_per_line` | Maximum characters on a subtitle line |
| `num_lines` | Maximum lines in one cue |

### Picture-in-picture styles

| File | Shape | Width | Anchor |
| --- | --- | --- | --- |
| `bottom-right-circle.json` | Circle | 23% of the frame | Bottom right |
| `bottom-center-circle.json` | Circle | 32% of the frame | Bottom center |
| `bottom-right-rounded-rect.json` | 16:9 rectangle with rounded corners | 28% of the frame | Bottom right |

| Field | Meaning |
| --- | --- |
| `shape` | `circle`, `square`, or `rect` |
| `width_fraction` | Inset width as a fraction of the output frame |
| `aspect` | Width:height for `rect`, such as `16:9`. Circle and square are always 1:1 |
| `anchor` | `bottom_right`, `bottom_left`, `top_right`, `top_left`, `bottom_center`, or `top_center` |
| `margin_fraction` | Gap from the anchored edges, as a fraction of frame width |
| `border_px` | Stroke width. `0` means no stroke |
| `border_color` | Stroke color, `#RRGGBB` |
| `corner_radius_fraction` | `0` is sharp, about `0.5` is a pill. Ignored for circles |

### Grading styles

A grade is an ffmpeg filter description: `eq` for contrast, brightness, and saturation; `curves` for tone; `color_balance` for shadows, midtones, and highlights.

| File | Look |
| --- | --- |
| `subtle.json` | A small contrast lift and slightly lower saturation |
| `neutral-punch.json` | A little more contrast plus a gentle S-curve |
| `warm-cinematic.json` | Higher contrast, lower saturation, warm highlights, and an S-curve |

`auto` does not use one of these files up front. The grade planner renders options from a talking-head source, you pick one, and that choice can be saved into `configs/grading-styles/`.

## Phases

### Phase 1 — Prep

- Check the required tools and the transcription key.
- Collect your inputs and confirm them.

### Phase 2 — One-time tasks

- Create the `edit/` folders and the first `edit/edit.json`.
- Probe the sources and record problems.
- Sync sources and transcribe the audio.
- Detect silences and repair broken word timings.
- Pack the transcripts into a take list.

### Phase 3 — Plan and review

- Plan the cut, crops, picture-in-picture, grade, and captions.
- Build a review page.
- Revise from your comments until you approve the plan.

### Phase 4 — Produce Draft

- Generate graphics.
- A subagent records browser recordings.
- Render a draft.
- Check the edit transcript and the cuts.
- You review the draft.

### Phase 5 — Produce Finalized

- Render `edit/edit.mov` with uncompressed audio.
- Write the subtitle file, and write chapters when you asked for them.
- You review the finalized render.

### Phase 6 — Process Audio

- Runs only when `process_audio` is true.
- If the Auphonic CLI is not installed, the phase tells you to install it from `https://auphonic.com/cli` and skips the rest.
- A subagent runs the process-audio skill on `edit/edit.mov`.
- You review `edit/edit-auphonic.mov`, `edit/edit-auphonic-transcript.html`, `edit/edit-auphonic-subtitles.srt`, `edit/edit-auphonic-shownotes.md`, and `edit/edit-auphonic.chapters.txt`.

### Phase 7 — Produce MP4

- Converts the Auphonic movie to `edit/edit.mp4` when Process Audio ran.
- Otherwise converts `edit/edit.mov`.
- You review `edit/edit.mp4`.

### Phase 8 — Cleanup

- Move draft files and intermediate folders to the trash.

## edit.json

`edit/edit.json` is the edit. Prep writes the sources and measured source facts. The plan phase fills in scenes, lines, takes, what is on screen, and picture-in-picture. The renderer, the review page, subtitles, and the edit transcript all read this file.

Times are `HH:MM:SS.ss` strings.

| Clock | Fields | Meaning |
| --- | --- | --- |
| Edit clock | `edit_start`, `edit_end` | Time in the finished video. The first line starts at `00:00:00.00`, and each later line starts where the previous one ends |
| Audio Source clock | `audio_source_start`, `audio_source_end` | Time on that source group's audio source. A footage layer uses these same times. Rendering adds that source's sync offset. Unsynced footage is stored from `00:00:00.00` for the length of the layer, and compiling does not add a sync offset |

| Key | Contents |
| --- | --- |
| `title` | Video title |
| `description` | One paragraph on what the video is |
| `sources` | One record per source: `path`, `type`, `audio`, `duration`, `resolution`, `fps`, and `base_crops` |
| `video_settings` | The video-settings config object |
| `video_style` | The video-style config object |
| `caption_style` | The caption style object. Omitted when captions are off |
| `srt_style` | The subtitle style object. Omitted when the sidecar file is off |
| `pip_style` | The picture-in-picture style object. Omitted when the inset is off |
| `grading_style` | The grade object. Omitted while grading is off or still `auto` |
| `source_groups` | One object per source group number |
| `issues` | One `{ "tag", "text" }` object per root-cause problem |
| `scenes` | The cut, in play order |

### Source Groups

`sources.<name>` holds `path`, `type`, `audio`, `duration`, `resolution`, `fps`, and `base_crops`. The number in the source name is its source group. `base_crops` holds `full`, `pip`, `top`, and `bottom`. A layer's `crop` is used when the layer has one. Otherwise `base_crops` for that `frame`. A frame written as `{ "x", "y", "w", "h" }` keeps its crop on the layer.

`audio_source` names the source whose audio the source group follows.

`sync` maps each other source to an offset in seconds. The offset is that source's time minus the audio source's time for the same moment. A positive offset means the other source started first.

### Scenes, lines, and takes

Scene ids are `s1`, `s2`, and so on. Line ids are `l1`, `l2`. Take ids are `t1`, `t2`. Numbers increase across the whole file and are never reused. Deleting one retires its number. Key order inside `scenes` and `lines` is play order, and so is the order of the `cuts` array.

| Piece | What it holds |
| --- | --- |
| Scene | A `name` and a `lines` object. A scene is one stretch of the story |
| Line | `edit_start`, `edit_end`, `kept_take`, `rejected_takes`, and `layers` |
| Kept take | `id`, `audio_source`, `transcript`, and `cuts` |
| Rejected take | The same fields plus `reason` |
| Cut | `audio_source_start`, `audio_source_end`, and, on a kept take, the `transcript` of that slice |

A line is one thing the speaker says, and every attempt at saying it. The kept take is the attempt that stays. A take can be several cuts from the same source, which is how a silence in the middle of a good reading is removed. The kept take's cut durations add up to the line's length on the edit clock.

### What is on screen

Each line has a `layers` array, painted back to front. A layer's `edit_start` and `edit_end` fall inside that line. The cuts on a footage layer add up to that layer's length on the edit clock.

| Layer | Fields | Meaning |
| --- | --- | --- |
| Full frame | `frame` `full`, `source`, `edit_start`, `edit_end`, `cuts` | The picture that fills the frame |
| Picture-in-picture | `frame` `pip`, plus the same footage fields | The inset. `pip_style` places and sizes it |
| Split | `frame` `top` or `bottom`, plus the same footage fields | One half of the frame |
| Window | `frame` `{ "x", "y", "w", "h" }`, plus the same footage fields | A box, as fractions of the frame |
| Graphic | `frame` `full`, `source`, `edit_start`, `edit_end` | A graphic that fills the frame. An overlay keeps transparent pixels so the layers under it show through. No cuts |
| Full-frame browser recording | `frame` `full`, `source`, `edit_start`, `edit_end` | A webpage recording that fills the frame. No cuts |
| Split browser recording | `frame` `top` or `bottom`, `source`, `edit_start`, `edit_end` | That recording in one half of the frame. No cuts |
| Window browser recording | `frame` `{ "x", "y", "w", "h" }`, `source`, `edit_start`, `edit_end` | That recording placed in a window. No cuts |

`source` names the entry in `sources`. A graphic source has `type` `graphic` and `description`. `path` is the rendered file, relative to the working directory, omitted until the graphic exists. A generated graphic that is the picture is `edit/graphics/<order>-graphic-<graphic-name>.mp4`. An overlay is that same full frame as a transparent `.webm`. That path is written on the source.

A browser recording source has `type` `browser`, `description`, and `actions`. `path` is omitted until the recording exists. The file is `edit/browser/<order>-browser-<name>.mp4`. The page is recorded at that layer's size: the full video, one half, or the window. `actions` run on the recording clock, which starts at `00:00:00.00` when that browser recording starts. Every `open` has `url` and shows that page. Each page is already loaded when its `open` starts. A one-click banner is cleared before the page is on screen. A page that still covers the words is not used. A recording can `scroll` more than once. `scroll` brings `to` into view. `highlight` marks `text`. Layers that share one browser recording have to meet, with no gap. Coming back to a page after other footage is a new browser recording.

A crop is integer source pixels, `x`, `y`, `w`, and `h`. `full` matches the output. `pip` matches the inset. `top` and `bottom` match half the frame: 32:9 on a 16:9 landscape output, and 9:8 on a 9:16 portrait output.

A full-frame `head` layer may set `zoom_cut` to true when the video style allows it. The render jumps in by `zoom_amount`, centered inside the crop. `1.15` is 15% tighter. The next line that omits `zoom_cut` is back at the crop. Consecutive lines can each set it, and the tighter view holds across them as one zoom cut. A zoom cut needs a full-frame `head` shot on the line before it, so it never lands on the first line or on a cut back from a graphic, a screen, or a browser recording. At least 2 lines without a zoom cut sit between zoom cuts.

## Scripts

Scripts live in `scripts/` and are run from the working directory with `uv run --no-project`. Paths below are relative to the skill folder.

### Sync

| Script | What it does |
| --- | --- |
| `scripts/sync/sync_pair.py` | Aligns every source that has audio onto the source group's audio source by comparing volume envelopes, then writes `sync` offsets into `edit/edit.json` |

### Transcription

| Script | What it does |
| --- | --- |
| `scripts/transcription/transcribe_batch.py` | Transcribes each source group's audio source with ElevenLabs Scribe, four at a time, into `edit/source-transcriptions/`. Skips sources that already have a transcript |
| `scripts/transcription/transcribe.py` | Transcribes one file. The batch script calls it. Extracts 16 kHz mono audio, requests verbatim text, speaker labels, audio events, and word times |
| `scripts/transcription/repair_timings.py` | Finds impossible word timings: zero-length words, single words lasting seconds, and words stretching across a silence in `edit/silences.json`. Splits each flagged stretch at its silences, re-transcribes each piece on its own, and splices the new words into the transcript. Keeps the raw transcript in `edit/source-transcriptions-original/`. Skips transcripts it already repaired |
| `scripts/transcription/pack_transcripts.py` | Turns those transcripts into `edit/takes-packed.md`, with phrases split on half-second silences and speaker changes |
| `scripts/transcription/detect_silences.py` | Finds silences on each source group's audio source. Probes that audio and sets its silence floor from those levels, then keeps silences at or above the video style's silence threshold. Writes `edit/silences.json`, including the floor used for each source. Times are on that audio source clock. Silences that sit on a transcribed audio event are left out. Timing repair and the cut planner both use this file |

### Production

| Script | What it does |
| --- | --- |
| `scripts/production/build_plan_html.py` | Validates `edit/edit.json` and writes `edit/plan-<hash>.html` for review. The hash is the first 8 hex digits of `edit.json`, so a stale review page is obvious. Writes nothing if validation fails |
| `scripts/production/render.py` | Renders `edit.json`: extracts each range, grades talking-head picture, concatenates the ranges, composites layers in order, and burns captions last. `--draft` writes the review render with compressed audio. A finalized render writes PCM audio |
| `scripts/production/record_browser.py` | Records each browser recording with Playwright. Opens pages, scrolls, highlights text, and writes `edit/browser/<order>-browser-<name>.mp4` plus that source's `path`. `--name` re-records one source. `--zoom` sets the page zoom. 4K uses 2 unless `--zoom` is passed |
| `scripts/production/build_srt.py` | Builds an edit-clock `.srt` from `edit.json` and the transcripts, using `srt_style` for wrapping |
| `scripts/production/plan_model.py` | Shared loader. Parses timecodes, checks that edit-clock times match the audio-source-clock cuts, and compiles the timeline that the review page, renderer, and subtitle builder use |
| `scripts/production/srt_timeline.py` | Shared caption-cue builder. Maps transcript words onto the edit clock, writes the sidecar SubRip file, and writes the burn-in script `edit/burn-captions.ass` |

### Grading

| Script | What it does |
| --- | --- |
| `scripts/grading/grade.py` | Applies a named grading-style file, or a JSON grade passed on the command line, to a still or a video |
| `scripts/grading/json_to_grade_vf.py` | Turns a grade object into an ffmpeg video-filter string. Used by `grade.py` and `render.py` |
| `scripts/grading/apply_grade.py` | Runs that filter string on a still or a video. Used by `grade.py` |

### Inspect

| Script | What it does |
| --- | --- |
| `scripts/inspect/screenshot.py` | Grabs one frame. Defaults to the midpoint. Used for grade, crop, and caption previews |
| `scripts/inspect/pip_crop_preview.py` | Crops a still with source-pixel `x,y,w,h` and writes a preview. Used for full-frame crops and picture-in-picture crops |
| `scripts/inspect/caption_style_preview.py` | Overlays sample caption text on a still using a caption style. Also makes a 9:16 crop when the still is 16:9 |
| `scripts/inspect/timeline_view.py` | Builds a filmstrip with a waveform underneath for a time range. Used to check each cut in the draft |

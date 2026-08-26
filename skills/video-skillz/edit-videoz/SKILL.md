---
name: edit-videoz
description: Edit a video from numbered raw clips into one finished video through gated Plan, Produce, and Export phases.
disable-model-invocation: true
---

# Context

Read `references/shared-context/concepts.md`

## Subagent Use

Tell any subagent you spin up the following
- All raw **clips** are in `<src>/*`, do not modify them
- `references/`, `assets/` and `scripts/` resolve from the skill directory - `<skill_dir>`

## Context Skills
Run the /skill-workflowz skill

## EDL (Edit Decision List)
- Editing decisions and information
- Ordered list of which **audio source** and **active clip** to play, from which timestamp to which
- The top-level `edit/edl.json` is the **EDL** for the whole video
- Each **segment** has `edit/<n>/edl.json` for optional `caption_style` / `grading_style` / `pip_style` overrides (these merge with the top level settings)
- Every path written into an **EDL** is relative to the working directory (or absolute)

# Phase 1 - Prep

Run the /session-memoriez skill

## 1. Environment Check
Verify 3 things and fix what is missing: 
- `ffmpeg` and `ffprobe` on `PATH`, and `ffmpeg` has the `subtitles` filter (needed to burn captions)
    - Run `ffmpeg -hide_banner -h filter=subtitles`
    - If the output is `Unknown filter 'subtitles'`, this build was not compiled with libass. Install a full ffmpeg that includes the `subtitles` filter, put it on `PATH`, and re-check until it succeeds
- `ELEVENLABS_API_KEY` in the environment or in `.env` in the skill directory
    - Ask the user to paste an API key rather than inventing one
    - Save it to `.env` in the skill directory
    - Never write it into `.`
- Node.js 22+ if `use_graphics` is true

## 2. Inputs
Prompt the user for each input if it wasn't already provided
- `video_type` (required)
    - Used to read video-type files in `assets/video-types/<video_type>.json`
    - Options: File names under `assets/video-types/*` or "create new"
- `description` (required)
- `caption_style`
    - Options: File names under `assets/caption-styles/*`, "none", or "create new"
- `srt_style`
    - Options: File names under `assets/srt-styles/*`, "none", or "create new"
- `pip_style`
    - Options: File names under `assets/pip-styles/*`, "none", or "create new"
- `grading_style`
    - Options: File names under `assets/grading-styles/*`, "none", or "auto"
- `use_graphics`
    - Boolean used to determine if graphics planning and generation should occur
- `graphics_style_guide`
    - Options: File names under `assets/graphics-style-guides/*` or "create new"
- `src`
    - The folder holding raw video files to edit
    - Default: working directory (`.`)

Create New Options
- For any variable the user selects "create new" for, follow the steps in the corresponding .md file in `references/create-assets/*`


# Phase 2 — Plan
## 1. Setup
- Create `edit/`
- Create `edit/edl.json`
- Create `edit/plan.html` (modeled after `assets/templates/plan.html`)
- Create `edit/<n>/` for each **segment**
- Create `edit/<n>/edl.json` for each **segment**

## 2. EDL Writes
- Add an entry to the `sources` object for each **clip**, where the key is the **clip** name (ex. "1-head"), and the value is the path to each **clip**
- Read `assets/video-types/<video_type>.json`, and write the JSON to `edit/edl.json` under the `video_type` key
- If the following input variables are not "none", write the JSON from the corresponding file into `edit/edl.json` under the same key as the input variable
    - `caption_style`
    - `srt_style`
    - `pip_style`
    - `grading_style`
- If `grading_style` is "auto", skip that property

## 3. Scan Clips
- `ffprobe` every **clip**
- Record duration, resolution, and fps for each **clip** in `edit/plan.html`, grouped by **segment**
- Check for issues
    - Examples
        - Value mismatches between **clips**
        - Value mismatches against `video_type`
        - Gaps in the numbering (missing **segments**)
        - Silent audio tracks
        - Other issues you think are relevant
- Flag issues for each **clip** in `edit/plan.html`
    - Do not duplicate the same issue (one root cause = one issue)
    - Edit decisions are not issues, do not consider them here
    - Skill override's from the user are not issues
    - A **clip** with no or little transcript is not an issue, it is likely just a bad take

## 4. Select Audio Reference Clips and Sync
- If any **segments** have more than 1 **clip**, give a subagent the following prompt
```md
You are using a script to determine audio offsets for syncing multiple sets of video/audio files on audio

Execute `references/subagents/plan-clip-sync.md`
```

Wait for the subagent to complete, then add an "Audio Reference" label to each **audio reference clip** in `edit/plan.html` summary

## 5. Transcribe
- Transcribe one **clip** per **segment** into `edit/clip_transcriptions/<clip-name>.json`
- If the **segment** has only one **clip**, use that, otherwise use the **audio reference clip** from the Sync step

```bash
uv run --no-project --with 'requests>=2,<3' scripts/transcription/transcribe_batch.py <src>
```

## 6. Pack Transcriptions
- Turn transcriptions into the **packed transcript**, a readable cut-picking view
```bash
uv run --no-project scripts/transcription/pack_transcripts.py
```

## 7. Subagent Tasks

- Run the subagents in this step in parallel
- Wait for all to complete before moving on

### Cut Subagent
- Run a subagent to make cut decisions with the following prompt
```
You are editing a <video_type> video, described as:
<description>

Execute `references/subagents/plan-cuts.md`

If `<src>/script.md` exists, use it as a skeleton for video structure
```

### Picture-in-Picture (PIP) Crop Subagent

- If `<pip_style>` is not "none" then run a subagent to plan PIP crop values for each **segment** using the following prompt
```
You are planning a picture-in-picture (PIP) crop for different video **clips**

All **clips** live in `<src>/*`
You are only planning PIP crops for `head` **clip types**

Execute `references/subagents/plan-pip-crops.md`
```

### Color Grade Subagent
- If `<grading_style>` is "none", skip this step
- If `<grading_style>` is a preset filename, read `references/create-artifacts/create-grade-preview.md` and create a preview for the grading
- If `<grading_style>` is "auto", run a subagent with the following prompt
- Use the first `head` **clip** in `src/` for `clip_name`

```
You are creating color grading options for a video using a SINGLE reference **clip** (`<src>/<clip_name>`)

Read `references/subagents/plan-auto-grading.md` and follow the guidelines and steps within
```

## 8. Caption Preview
- If `<caption_style>` is not "none", and a preview wasn't already created when creating a new style, read `references/create-artifacts/create-caption-preview.md` and run the steps

## 9. Compile Results
- Add any grading, PIP, or caption previews into `edit/plan.html`

## 10. Plan Graphics and Active Clips

For each **beat**, a single **active clip** will be used

### Read Plan
- Read the PLAN section of `edit/plan.html` written by the cut subagent

### Active Clip Guidelines
- Generally, **A-Roll** **clip types** should be used as the **active clip** for each **beat**
    - If the beat is explaining something on screen, the `screen` **clip** should be used if one is available
    - If the beat is explaining something in a provided `graphic`, the `graphic` **clip** should be used
    - Otherwise, prefer a `head` **clip**, especially for conclusions of a point, punchlines, or transitions to a new point (when the subject is likely talking to the camera)
    - Avoid quick flashes between clip -> `head` -> clip, it's disorientating
- **B-Roll** **clip types** should be used as the **active clip** to enhance cuts or add visual interest
- If `use_graphics` is true, then you can suggest graphics to use as the **active clip** for any **beat**
    - Graphics should be treated as **A-Roll**, a primary communication mechanism
- **Active clips** can span more than one beat if they work with the audio from the kept takes

### Graphics Guidelines
- When adding graphics, consider what other **A-Roll** and **B-Roll** is available, and if a graphic would be better
- Graphics will be generated post-approval using Hyperframes
- The graphic must be readable at 1x
- Graphics should be at least 3s long, 5-7s for a simple card, 8-14 for a denser diagram, longer if it makes sense
    - Beat-synced accents are the exception
    - In a fast montage, 0.5–2s is fine
    - For faster graphics, the bar is *recognizable* at 1x, not *fully readable*, because the graphic is a visual accent rather than information
- With a voiceover, the total duration should be at least the narration length + 1s

### Determine Source Segment Clock Range

When using a source **clip** as the **active clip**, the renderer needs to know which source **clip** to use, and the **segment clock** range within that clip to render out

The **segment clock** duration must match the **edit clock** duration

For each beat:
- If the **active clip** is the same **clip** as the kept take
    - Use its **segment clock** time range
- If the **active clip** has no audio, is **B-Roll**, or is from a separate segment than the kept take **clip**
    - Start the **segment clock** range from 0
- If the **active clip** is from the same segment
    - Use the **segment clock** range of the kept take as a baseline
    - Look up the sync offset for the clip produced by the Sync step (`edit/<n>/sync.json`)
    - Apply the sync offset

### Write Output
- Write the planned **active clips** into `edit/plan.html`
- For graphics, include a description

## 11. PIP Planning
- Based on the PLAN section of `edit/plan.html`, decide where PIP should go
- Record each window on the **edit clock** as `HH:MM:SS.ss` (timecode in the assembled **EDL**)
- Make sure the **segment clock** duration matches the **edit clock** duration for the beat
- Guidelines
    - Do not apply PIP if
        - The **active clip** is a `head` clip (head is the PIP)
        - The **active clip** is the same as the **clip** for the kept take
        - The **active clip** is a **B-Roll** **clip type**
    - Always apply PIP if `head` is available when
        - The **active clip** is a suggested graphic
        - The **active clip** is a `screen` or `graphic` clip
- Update `edit/plan.html` with the planned PIP locations
    
## Gate
- Open `edit/plan.html` with Lavish
    - All comments will be provided via Lavish
- If `grading_style` is "auto"
    - Don't move on until the user has selected a grading option
    - Ask the user if they want to save the selection to `assets/grading-styles`, and if yes, write the new JSON file
    - Record the grading option choice in `edit/plan.html`
- Feedback Loop
    - Wait for approval to continue to Phase 3 or for comments on the plan
    - Address comments and wait again

# Phase 3 — Produce

This phase follows the finalized plan in `edit/plan.html`

## 1. Generate Graphics
- If `use_graphics` is true, spin up a single subagent to generate all planned graphics using the following prompt
```md
You are generating graphics for a video

The video is <description>

Graphics style guide: `assets/graphics-style-guides/<graphics_style_guide>.md`

Generate the following, one at a time, in this order:
- `edit/graphics/<n>-graphic-<graphic-name>.mp4`
    - <start>–<end> on the **edit clock**
    - <description>
- <Give the full list of graphics in the order from plan.html>

Execute `references/subagents/create-graphics.md`
```

Wait for the subagent to complete before continuing

## 2. plan.html -> edl.json

Write the following values to the `edit/edl.json` file

Parse `HH:MM:SS.ss` from `plan.html` into float seconds (`00:00:09.41` → `9.41`). Do not round.

### graphics
- Add each graphic generated in the last step
- Add each graphic to `sources` as well, keyed by the file stem, so a range can use it as `active_clip`
- `start` / `end` are when the graphic appears in `edit.mp4` (**edit clock**)

```json
{
    "graphics": [
        {
            // The path to the graphic file
            "file": "edit/graphics/<n>-graphic-<graphic-name>.mp4",

            // Start second on the edit clock
            "start": 0.0,

            // End second on the edit clock
            "end": 5.0
        }
    ]
}
```

### ranges
- This is the **EDL** for the whole video, in play order
- `start` / `end` are the kept take on the **segment clock**
- `audio_source` is that take's **clip** (from takes_packed / the **audio reference clip**)
- `active_clip` is the A-roll picture for this **beat**
    - Always set, even when it matches `audio_source`
    - The renderer maps `start` onto `active_clip` using that **clip**'s offset in `edit/<n>/sync.json`
- Captions and the sidecar subtitle file follow `audio_source`

```json
{
    "ranges": [
        {
            // Kept take / audio clip from takes_packed
            "audio_source": "1-head",

            // A-roll picture for this beat (always set)
            "active_clip": "1-screen",

            // Start second on the segment clock
            "start": 2.42,

            // End second on the segment clock
            "end": 6.85
        }
    ]
}
```

### pip
- If `<pip_style>` is "none", skip
- Crop comes from `edit/<n>/pip-crop.json`
- `start` / `end` come from the planned PIP windows in `plan.html`
- `start` / `end` are when PIP appears in `edit.mp4` (**edit clock**)
- Write the array onto `edit/edl.json`

```json
{
    "pip": [
        {
            // Head clip from sources
            "source": "1-head",

            // Start second on the edit clock
            "start": 4.0,

            // End second on the edit clock
            "end": 9.0,

            "crop": {
                "x": 420,
                "y": 80,
                "w": 1080,
                "h": 1080
            }
        }
    ]
}
```

### grading_style
- If `grading_style` is already set, leave it
- If `grading_style` was "auto", populate the property with the settings for the user's selected grading option

## 3. Do the Cut
```bash
uv run --no-project scripts/production/render.py \
  -o edit/edit.mp4 --draft
```

## 4. Verification Loops

- Run the loops in this step, sequentially
- The loops follow these steps
    - Check for issues
    - Fix **EDL**
    - Rerender
    - Check again
    - Cap at 3 passes
    - Move on if there are no issues
    - Flag any remaining issues to the user at the Gate

### Transcript
- Use the **clip** level transcripts and the **EDL** ranges to create `edit/transcript.edit.md`
- Do not retranscribe in this step, use the existing transcriptions
- Read the transcript
- Look for issues
    - A cut that severed a word
    - Dropped a needed clause
    - Joined two halves into a sentence that no longer parses
    - etc.

### Visual Jumps
- Run `scripts/inspect/timeline_view.py` on `edit/edit.mp4` — not on the sources — across ±1.5s of every cut boundary, writing into `edit/verify/`
- Check each image for issues
    - A visual jump or flash at the cut
    - A waveform spike at the join
    - A graphic in the wrong place or showing the wrong content
    - etc.

## Gate
- Summarize the render for the user
- Ask the user to review `edit.mp4` and `transcript.edit.md`
- Address any user comments
- Wait for approval before moving on

# Phase 4 — Export

## 1. Render
```bash
uv run --no-project scripts/production/render.py \
  -o edit/edit.mp4
```

## 2. Normalize Audio
- Skip when `<video_type>.target_lufs` not set
- loudnorm the `edit.mp4` file
```bash
uv run --no-project scripts/production/normalize_audio.py edit/edit.mp4 \
  -o edit/normalized-edit.mp4 --target-lufs <video_type>.target_lufs
```

## 3. Subtitle File
- If `srt_style` is not "none", read `references/create-artifacts/create-srt.md` and follow the steps

## Gate
- Summarize phase to user
- Ask for any feedback required
- Wait for approval before moving on

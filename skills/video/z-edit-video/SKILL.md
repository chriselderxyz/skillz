---
name: z-edit-video
description: Edit a video from numbered raw sources into one finished video through gated Plan, Produce Draft, Produce Finalized, Process Audio, and Produce MP4 phases.
disable-model-invocation: true
---

# Global Context

## Context Skills
- Run the /z-task-skill-structure skill.

## Shared Context
- Read `references/shared-context/concepts.md`.
- Read `references/shared-context/edit-json.md` for context on the edit.json.

## Subagent Use
- Tell any subagent you spin up the following.
    - All raw **sources** are in `<src>/*`, do not modify them.
    - `references/`, `assets/`, `configs/` and `scripts/` resolve from the skill directory - `<skill_dir>`.
    - Paths referenced by another invoked skill resolve from that skill's directory.

# Phase 1 - Prep

Run the /z-session-memory skill.

## Action 1. Environment Check
Verify 2 things and fix what is missing. 
- `ffmpeg` and `ffprobe` on `PATH`, and `ffmpeg` has the `subtitles` filter (needed to burn captions).
    - Run `ffmpeg -hide_banner -h filter=subtitles`.
    - If the output is `Unknown filter 'subtitles'`, this build was not compiled with libass. Install a full ffmpeg that includes the `subtitles` filter, put it on `PATH`, and re-check until it succeeds.
- `ELEVENLABS_API_KEY` in the environment or in `.env` in the current working directory.
    - Ask the user to paste an API key rather than inventing one.
    - Save it to `.env`.

## Action 2. Inputs
Prompt the user for each input if it was not already provided.
- `video_settings` (required).
    - Used to read video-settings files in `configs/video-settings/<video_settings>.json`.
    - Options: File names under `configs/video-settings/*` or "create new".
- `video_style` (required).
    - Used to read video-style files in `configs/video-styles/<video_style>.json`.
    - Options: File names under `configs/video-styles/*` or "create new".
- `description` (required).
- `caption_style`.
    - Options: File names under `configs/caption-styles/*`, "none", or "create new".
- `srt_style`.
    - Options: File names under `configs/srt-styles/*`, "none", or "create new".
- `pip_style`.
    - Options: File names under `configs/pip-styles/*`, "none", or "create new".
    - The recommended option should be a circle.
- `grading_style`.
    - Options: File names under `configs/grading-styles/*`, "none", or "auto".
- `graphics_style_guide`.
    - Skip when `full_frame_graphics_enabled` and `graphic_overlays_enabled` are both false on `video_style`.
    - Options: File names under the `/z-create-graphics` skill's `configs/*`, an explicit file path or "create new".
- `generate_chapters`.
    - Boolean used to determine if video chapters should be generated.
- `process_audio`.
    - Boolean used to determine if the Process Audio phase runs.
- `src`.
    - The folder holding raw video files to edit.
    - Default: working directory (`.`).
- `script`.
    - The filename or path to a Script file that has the planned script for the video (This is NOT the exact transcript).

Create New Options.
- If the user selects "create new" for any input option.
    - Use the `/z-create-config` skill to create a new config.
    - For `graphics_style_guide`, create the config for the `/z-create-graphics` skill.
    - For all other inputs, create the config for this skill.
    - Use video-settings, video-styles, caption-styles, srt-styles, or pip-styles as the config type.
    - For guidelines, read the following for each input.
        - `video_settings`: `references/create-configs/create-video-settings.md`.
        - `video_style`: `references/create-configs/create-video-style.md`.
        - `caption_style`: `references/create-configs/create-captions-style.md`.
        - `srt_style`: `references/create-configs/create-srt-style.md`.
        - `pip_style`: `references/create-configs/create-pip-style.md`.
        - `graphics_style_guide`: `references/create-graphics-style-guide.md` from `/z-create-graphics`.

## Gate
- Confirm all inputs and configs with the user before moving on.
- When `video_style.full_frame_graphics_enabled` or `video_style.graphic_overlays_enabled` is true, verify Node.js 22+.
- When `video_style.browser_enabled` is true, verify Playwright can launch Chromium.
    - Run `uv run --no-project --with playwright python -c "from playwright.sync_api import sync_playwright; p = sync_playwright().start(); b = p.chromium.launch(headless=True); b.close(); p.stop()"`.
    - If that fails, run `uv run --no-project --with playwright python -m playwright install chromium` and verify again.

# Phase 2: One Time Tasks

## Action 1. Folders
- Create `edit/`.
- Create `edit/<n>/` for each **source group**.

## Action 2. Initial Writes
- Write top level `title` and `description` properties to `edit/edit.json`.
- Write `source_groups` to `edit/edit.json`, one key per **source group** number.
- Write `sources` to `edit/edit.json`.
    - An entry in `sources` for each **source**, keyed by the **source** name (ex. "1-head").
    - `path` is the file, relative to the working directory.
    - Set `type` from the **source type** in the filename.
- Write the JSON from `configs/video-settings/<video_settings>.json` under the `video_settings` key.
- Write the JSON from `configs/video-styles/<video_style>.json` under the `video_style` key.
- Write the JSON from the corresponding file for each of these input variables, under the same key as the input variable.
    - `caption_style`.
    - `srt_style`.
    - `pip_style`.
    - `grading_style`.
    - Skip any of those that are "none", and skip `grading_style` if it is "auto".

## Action 3. Probe Sources
- `ffprobe` every **source** that has a `path`.
- Write `audio`, `duration`, `resolution`, and `fps` for each probed **source** onto its entry in `sources`.

## Action 4. Scan Sources for Issues
- Use the **source** values written to `edit/edit.json` `sources`.
- Check for issues.
    - Value mismatches between **sources**.
    - Value mismatches against `video_settings`.
    - Gaps in the numbering (missing **source groups**).
    - Silent audio tracks.
    - Other issues you think are relevant.
- Write issues to `edit/edit.json` under `issues`, one object per issue with a `tag` and `text`.
    - Do not duplicate the same issue (one root cause = one issue).
    - Edit decisions are not issues, do not consider them here.
    - Skill override's from the user are not issues.
    - A **source** with no or little transcript is not an issue, it is likely just a bad take.
    - A **source** with no audio is not an issue.
    - A **source group** with only 1 audio file is not an issue.
- Variations between the transcript and `script` are not issues, do not mention them to the user.

## Action 5. Select Audio Sources
- For each **source group**, select a single **source** as the **audio source**.
    - The selected source must have `audio = true`.
    - If no audio exists, skip the **source group**.
- Select the **audio source** with the following **source type** priority.
  1. `audio`
  2. `voiceover`
  3. `screen`
  4. `head`
  5. `graphic`
  6. Any other **B-Roll**
- Write the selected **source** name to `audio_source` on that **source group** in `edit/edit.json`.

## Action 6. Sync Sources
- Write source offsets to `edit/edit.json`.
```bash
uv run --no-project scripts/sync/sync_pair.py <src>
```

## Action 7. Transcribe
- Transcribe the **audio source** for each **source group** into `edit/source-transcriptions/<source-name>.json` with the following command.

```bash
uv run --no-project --with 'requests>=2,<3' scripts/transcription/transcribe_batch.py <src>
```

## Action 8. Detect Silences
- Write the silences on each **audio source** to `edit/silences.json`.
```bash
uv run --no-project scripts/transcription/detect_silences.py
```

## Action 9. Repair Transcription Timings
- Repair broken word timings in `edit/source-transcriptions/`.
```bash
uv run --no-project --with 'requests>=2,<3' scripts/transcription/repair_timings.py
```

## Action 10. Pack Transcriptions
- Turn transcriptions into the **packed transcript**, a readable cut-picking view.
```bash
uv run --no-project scripts/transcription/pack_transcripts.py
```

# Phase 3: Plan and Review Loop

## Phase Context
- Run these actions in a loop with a user feedback gate at the end.
- Run the Cut Subagent first because **layer** assignments must exist before full-frame crops can be planned.
- After the Cut Subagent finishes, the remaining subagents can be run in parallel.

## Action 1. Cut Subagent

### Action Context
- If the `script` input variable exists, tell the subagent to use it as a skeleton for video structure.
- Always tell the subagent the value for `pip_style`.

### A. Initial Loop Run
- Run a subagent to make cut decisions with the following prompt.
```md
You are editing a <video_settings> video in the <video_style> style, described as:
<description>

Execute `references/subagents/plan-cuts.md`
```

### B. Edits
- If edits are required after user feedback, run the subagent with the following prompt.
```md
You are editing a <video_settings> video in the <video_style> style, described as:
<description>

This is not the initial edit pass

The following user feedback has been provided:
- List of user feedback with full context on the pieces of edit.json they apply to.

Use `references/subagents/plan-cuts.md` to apply the requested changes

Do not fully regenerate `edit/edit.json`, just apply changes
```

## Action 2. Crop Subagent
- Run one subagent to plan every crop.
- On an edit pass, pass the feedback and the sources it applies to.
```
You are planning crops for video sources in a <video_settings> video

All sources live in `<src>/*`

Execute `references/subagents/plan-crops.md`
```

## Action 3. Color Grade Subagent
- If `<grading_style>` is "none", skip this step.
- If `<grading_style>` is a preset filename, read `references/create-artifacts/create-grade-preview.md` and create a preview for the grading.
- If `<grading_style>` is "auto", run a subagent with the following prompt.
- Use the first `head` **source** in `src/` for `source_name`.
```
You are creating color grading options for a video using a SINGLE reference **source** (`<src>/<source_name>`)

Read `references/subagents/plan-auto-grading.md` and follow the guidelines and steps within
```

## Action 4. Caption Preview
- If `<caption_style>` is not "none", and a preview was not already created when creating a new style, read `references/create-artifacts/create-caption-preview.md` and run the steps.

## Action 5. Build Plan HTML
- Wait until all subagents have finished.
- Run the script to generate plan.html.
```bash
uv run --no-project scripts/production/build_plan_html.py
```

- The script reports every problem it finds and writes nothing until they are all fixed.
- Correct `edit/edit.json` and rerun until it succeeds.
- Note the `edit/plan-<hash>.html` path it prints, that is the file the user reviews.

## Gate

### A. Auto Grading
- If `grading_style` is "auto" and the Color Grade Subagent ran in this loop iteration.
    - Ask the user to select one of the styles.
    - Ask the user if they want to save the selected style to `configs/grading-styles`, and if yes, write the new JSON file.
    - Write the settings for the selected option to `edit/edit.json` under `grading_style`.

### B. Open Plan HTML File
- If you have access to any skills for tooling used to review html documents, open the plan html file (`edit/plan-<hash>.html`) using that and listen for comments.
    - Each element in the cut plan has a `data-json-path` property used to map html elements to edit.json keys.
- If no skills are available, open it in the default browser.

### C. User Feedback Loop
- If the user gives comments/feedback, re-run the required actions from this phase with the new context.
    - 1. Cut Subagent - If edits to the **scenes**/**lines**/**takes**/**cuts**/**layers**/**graphics**/browser recordings/PIP placement/zoom cuts.
    - 2. Crop Subagent - If **layers** changed or a crop needs edits.
    - 3. Color Grade Subagent - If the user requests a new auto grading run.
    - 4. Caption Preview - If the user requests to change the `caption_style`.
    - 5. Build Plan HTML - Always do this if any edits were made.
- Make sure you use subagents for the Actions that call for them, don't do edits manually yourself unless required.

### D. Approval
- Wait for explicit approval before moving to Phase 4, approval of one piece is not full approval.

# Phase 4: Produce Draft

This phase follows the finalized plan in `edit/edit.json`.

## Action 1. Graphics

### Action Context
- Wait for all subagents to complete before continuing.
- Every **source** with `type` `graphic` is one graphic.
- A graphic **layer** names that **source**.
- Read `orientation` and `resolution` from `video_settings` in `edit/edit.json`.
- Skip graphic creation and graphic editing when `full_frame_graphics_enabled` and `graphic_overlays_enabled` are both false.

### A. Graphic Creation
- Use this step to create NEW graphics.
- A graphic **source** that already has `path` is finished. Skip it.
- Spin up a single subagent to run `/z-create-graphics` with the following prompt.

```md
You are generating graphics for a video

Run `/z-create-graphics` with these inputs:
- `mode`: `create`.
- `video_description`: <description>.
- `graphics_style_guide`: <graphics_style_guide>.
- `orientation`: <orientation from edit/edit.json>.
- `resolution`: <resolution from edit/edit.json>.
- `output_dir`: `edit/graphics`.
- `graphics`.
    - <Give every graphic source that has no `path`, in order of first appearance. graphic_number is that order. graphic_name is the source name. graphic_duration is that graphic's total duration, as HH:MM:SS.ss. graphic_description is the source description. frame is that graphic's frame. Include whether other layers sit behind it>.
```

### B. Graphic Editing
- Use this step to edit EXISTING graphics.
- Spin up a single subagent to run `/z-create-graphics` with the following prompt.

```md
You are editing existing graphics for a video

Run `/z-create-graphics` with these inputs:
- `mode`: `edit`.
- `video_description`: <description>.
- `orientation`: <orientation from edit/edit.json>.
- `resolution`: <resolution from edit/edit.json>.
- `output_dir`: `edit/graphics`.
- `graphics`.
    - <Give each affected graphic source with its original graphic_number, graphic_name, graphic_duration as that graphic's total duration, graphic_description from the source, graphic_feedback, frame, and whether other layers sit behind it>.
```

### C. Update the Source
- After the subagent returns from creation or editing, write `path` on `sources.<graphic-name>`.
- `path` is that graphic's rendered file, relative to the working directory.
- `ffprobe` the file and write `audio`, `duration`, `resolution`, and `fps` on that source.

## Action 2. Browser Recordings

### Action Context
- Wait for the subagent to complete before continuing.
- Every **source** with `type` `browser` is one browser recording.
- A browser recording **layer** names that **source**.
- Skip this step when `browser_enabled` is not true.
- Skip this step when no **source** has `type` `browser`.
- Read `resolution` from `video_settings` in `edit/edit.json`.

### A. Browser Recording Creation
- Use this step to record NEW browser recordings.
- A browser recording **source** that already has `path` is finished. Skip it.
- Spin up a single subagent with the following prompt.

```md
You are recording browser recordings for a video

Execute `references/subagents/record-browser.md`

Mode: `create`
```

### B. Browser Recording Editing
- Use this step when a browser recording **source** needs a new recording.
- Spin up a single subagent with the following prompt.
- Name each **source** whose `actions`, duration, or frame size changed.
- Include a custom `page_zoom` if the user has requested it or feedback indicated it is needed.

```md
You are re-recording browser recordings for a video

Execute `references/subagents/record-browser.md`

Mode: `edit`

Page zoom: <page_zoom>.

Re-record these sources:
- <source-name>.
```

## Action 3. Do the Cut
- The script reports every problem it finds in `edit/edit.json` and renders nothing until they are all fixed.

```bash
uv run --no-project scripts/production/render.py \
  -o edit/edit-draft.mp4 --draft
```

- When rerendering, `rm` the draft folders/files first.
    - `edit/edit-draft.mp4`.
    - `edit/base-draft.mp4`.
    - `edit/range-cuts-draft/`.
    - `edit/sources-pip-draft/`.
- Do not delete draft folders/files if a draft rerender is not required.

## Action 4. Build Review HTML
- Run the script to generate the review page.

```bash
uv run --no-project scripts/production/build_review_html.py
```

- Note the `edit/review-<hash>.html` path it prints. That is the file the user reviews.

## Action 5. Verification Loops

- Loop Steps.
    - Check for issues.
    - Fix `edit/edit.json`.
    - Rerender.
    - Rebuild the review page.
    - Check again.
    - Cap at 3 passes.
    - Move on if there are no issues.
    - Flag any remaining issues to the user at the Gate.

### A. Transcript
- Use the **source** level transcripts and the kept takes in `edit/edit.json` to create `edit/transcript.edit.md`.
- Do not retranscribe in this step, use the existing transcriptions.
- Read the transcript.
- Look for issues.
    - A cut that severed a word.
    - Dropped a needed clause.
    - Joined two halves into a sentence that no longer parses.
    - etc.

### B. Draft Checks
- Run the script to check `edit/edit-draft.mp4` for issues.

```bash
uv run --no-project --with numpy scripts/inspect/check_draft.py
```

## Gate
- When the render is ready for review, explicitly tell the user.
- Summarize the render for the user.
- If you have access to any skills for tooling used to review html documents, open the review html file (`edit/review-<hash>.html`) using that and listen for comments.
    - Each element in the review has a `data-json-path` property used to map html elements to edit.json keys.
- If no skills are available, open it in the default browser.
- Ask the user to review `edit/review-<hash>.html` and `transcript.edit.md`.
- Address any user comments by rerunning the phase with the feedback and corrections as context.
- Wait for explicit approval before moving on to the next phase.

# Phase 5: Produce Finalized

## Action 1. Render
```bash
uv run --no-project scripts/production/render.py \
  -o edit/edit.mov
```

## Action 2. Subtitle File
- If `srt_style` is not "none", read `references/create-artifacts/create-srt.md` and follow the steps.

## Action 3. Chapters
- If `generate_chapters` is true, create a `edit/chapters.md` file with the following format.
- Use edit.json as a reference, but don't blindly follow the scenes written in it.
```md
00:00 - Intro
01:28 - Chapter Name
mm:ss - Chapter Name
...
```

## Gate
- Explicitly tell the user when the finalized render is ready to review.
- Summarize phase to user.
- Ask for any feedback required.
    - Rerun this phase with any feedback as context.
- Wait for explicit approval before moving on.

# Phase 6: Process Audio

## Phase Context
- Skip this phase when `process_audio` is false.

## Action 1. Auphonic CLI
- If `auphonic` is not on `PATH`, tell the user to install the Auphonic CLI from `https://auphonic.com/cli` and skip the rest of this phase.

## Action 2. Process
- Spin up a single subagent to run `/z-process-audio` with the following prompt.
- Wait for the subagent to finish before the Gate.

```md
You are processing the audio of a finished video

Run `/z-process-audio` with these inputs:
- `mode`: `create` on the first run, `edit` when rerunning this phase.
- `input_file`: `edit/edit.mov`.
- `output_dir`: `edit`.
- `target_lufs`: <video_settings.target_lufs when set, otherwise omit>.
```

## Gate
- Explicitly tell the user when the Auphonic video, transcript, subtitles, shownotes, and chapters are ready.
- Ask for any feedback required.
    - Rerun this phase with any feedback as context.
- Wait for explicit approval before moving on.

# Phase 7: Produce MP4

## Action 1
- When Process Audio ran, convert `edit/edit-auphonic.mov`.
- Otherwise convert `edit/edit.mov`.
- Write `edit/edit.mp4`.

```bash
ffmpeg -y -i <source> -c:v copy -c:a aac -b:a 192k -ar 48000 -movflags +faststart edit/edit.mp4
```

## Gate
- Explicitly tell the user when `edit/edit.mp4` is ready.
- Ask for any feedback required.
    - Rerun this phase with any feedback as context.
- Wait for explicit approval before moving on.

# Phase 8: Cleanup

## Action 1
- Do not clean up until the user approves the final exports from Produce MP4.
- Move the following folders/files in the `edit/` directory to trash.
    - `edit-draft.mp4`.
    - `base-draft.mp4`.
    - `base.mp4`.
    - `grading-previews/`.
    - `range-cuts-draft/`.
    - `range-cuts/`.
    - `sources-pip-draft/`.
    - `sources-pip/`.

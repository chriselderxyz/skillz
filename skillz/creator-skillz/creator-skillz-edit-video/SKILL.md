---
name: creator-skillz-edit-video
description: Cut raw multi-clip footage into a finished YouTube video through gated Plan, Produce, Fix, Export, and Cleanup phases.
disable-model-invocation: true
---

# Purpose

Orchestrate `video-use` and `hyperframes` to turn numbered raw clips into one finished video, one segment at a time, stopping at a gate for the user's review between every phase.

# Inputs

- `footage_dir` (required): the directory holding the raw clips.
- `script.md` (optional): a written script for this video, found at the root of `footage_dir`.

Resolve `footage_dir` from the request. If missing, ask the user.

Clips are named `<n>-cam.<ext>` and `<n>-screen.<ext>`, numbered in playback order. A **segment** is one number: `1-cam` and `1-screen` are both segment 1. A segment may have a cam clip only, a screen clip only, or both.

When `script.md` is present it is the intended shape of the video, not a transcript of it. Use it in Plan to name the beats and to report any beat the footage never delivered. The delivered words always win over the script's words.

# Layout

Originals are read-only inputs and stay in `footage_dir`. Everything this skill produces lives in `edit/`.

```
<footage_dir>/
├── 1-cam.mp4  1-screen.mp4  2-cam.mp4  ...   read-only
├── script.md                optional input
└── edit/
    ├── plan.md              whole-video plan + user comments
    ├── decisions.md         which take won, and why
    ├── project.md           session memory
    ├── transcripts/         cached ElevenLabs JSON, keyed by source
    ├── final.mp4
    ├── final.srt
    └── <n>/                 one folder per segment
        ├── transcript.plan.md
        ├── transcript.edit.md
        ├── transcript.fix-<i>.md
        ├── sync.json        cam/screen offset, intermediate
        ├── base.mp4         cam+screen composited, intermediate
        ├── edl.json         the cut list
        ├── graphics/<slot>/ brief.md + composition + render
        └── segment-<n>-final.mp4
```

`edl.json` is `video-use`'s Edit Decision List: the ordered list of which source to play, from which timestamp to which, plus the grade and any overlays. Called the **cut list** everywhere below, and specified under that heading.

`project.md` is `video-use`'s session memory, one appended entry per working session. It exists so an edit picked up days later can be resumed from the artifacts rather than from recall.

# The wrapped skills

**`video-use` is a set of helper scripts here, not a process.** Run the helpers; the phases below replace its `SKILL.md`, which prescribes a different pipeline — one cut list for the whole video assembled by beat across all clips, and animations built by parallel sub-agents.

Helpers resolve next to that `SKILL.md`, typically symlinked at `~/.claude/skills/video-use/helpers/`. `render.py` already enforces in code the parts that otherwise fail silently: per-segment extraction, 30ms audio fades at every boundary, PTS-shifted overlays, subtitles applied last. Two rules stay yours — never cut inside a word, and pad every cut edge by 30–200ms.

**`hyperframes` is scoped to the graphics slots.** Its description claims it is the mandatory entry point for any request to make or edit a video. Here it owns the contents of `graphics/` and nothing else — the cut, the composite, the subtitles, and the export follow the phases below.

**Normalize once, at the end.** Render every segment with `--no-loudnorm`. `render.py` normalizes to -14 LUFS by default, which on a per-segment render levels each segment independently and makes a deliberately quiet moment match a loud one.

## The cut list

```json
{
  "version": 1,
  "sources": {"1cam": "/abs/path/1-cam.mp4", "1base": "/abs/path/edit/1/base.mp4"},
  "ranges": [
    {"source": "1base", "start": 2.42, "end": 6.85,
     "beat": "HOOK", "quote": "...", "reason": "last take, no false start"}
  ],
  "grade": "none",
  "overlays": [
    {"file": "edit/1/graphics/<slot>/render.mp4", "start_in_output": 0.0, "duration": 5.0}
  ],
  "total_duration_s": 42.1
}
```

`grade` is a `grade.py` preset name or a raw ffmpeg filter string. `start_in_output` is measured on the cut timeline, after the ranges are joined. Leave out the `subtitles` key — those are built once at export.

# Gates

A gate ends a phase. At a gate: write the phase's artifacts, append a session entry to `project.md`, tell the user exactly which files to review, and stop. Wait for an explicit instruction to continue.

Whatever you reasoned about and did not write down is not available to the next phase. The artifacts are the hand-off.

When resuming with no memory of the previous phase, read `project.md`, `plan.md`, and `decisions.md`, then summarize the last session in one sentence before continuing.

## User comment syntax

Users annotate `plan.md` and any transcript file with:

```
Content to apply changes to
[COMMAND: context]
```

- `[EDIT: request for a change]`
- `[CUT: remove this]`
- `[EXPAND]` — expand on a point
- `[NOTE: take into consideration]`

Remove a comment only once its change is clearly resolved. Preserve ambiguous comments and ask about them.

# Phase 1 — Plan

1. **Preflight.** `ffprobe` every clip. Record duration, resolution, fps, and audio stream per clip in `plan.md`. Flag resolution or fps mismatches between clips, gaps in the numbering, and silent audio tracks. Raise anything unresolved with the user before transcribing.
2. **Transcribe.** `transcribe_batch.py <footage_dir>`, then `pack_transcripts.py --edit-dir <footage_dir>/edit`. The cam clip carries the voice; a screen clip's transcript is only useful when it is the sole clip in its segment.
3. **Per segment**, create `edit/<n>/` and write `transcript.plan.md`: the packed phrase-level transcript for that segment with every proposed cut marked inline, plus a `## Graphics` section proposing motion graphics and B-roll with the payoff word each one should land on.
   - Cut filler words, fluff, and false starts.
   - Where a line is repeated, keep the best take, which is usually the last one. Slight wording differences between takes still make them the same take, not different content.
   - Every cut edge lands on a word boundary from the transcript, padded by 30–200ms to absorb timestamp drift.
4. **Record the reasoning.** Write `edit/decisions.md` as you go: for each beat, which take won, which lost, and why. The inline marks in the plan transcripts get consumed once cuts are applied; this file is what survives into Fix.
5. **Summarize.** Write `edit/plan.md`: preflight table, the video's shape beat by beat, per-segment runtime estimate and running total, which segments are picture-in-picture, which need graphics, the subtitle and grade direction, and — when `script.md` exists — any scripted beat the footage does not cover.

**Gate.** Every clip has a `transcript.plan.md`, every segment appears in `plan.md`, every beat has an entry in `decisions.md`, and preflight has no unresolved flag. Point the user at `plan.md` and the transcript files.

# Phase 2 — Produce

Work one segment at a time, in order.

1. **Apply the user's comments** from `plan.md` and `transcript.plan.md` first.
2. **Build the base.** A segment with both a cam and a screen clip is picture-in-picture: read [`PIP.md`](PIP.md) and composite them into `edit/<n>/base.mp4`. A single-clip segment uses the original directly as its base.
3. **Build the graphics.** A segment with approved graphics: read [`GRAPHICS.md`](GRAPHICS.md). A segment with none skips to the cut.
4. **Cut.** Write `edit/<n>/edl.json` from the approved plan transcript and render with `render.py --no-loudnorm`, producing `edit/<n>/segment-<n>-final.mp4`. Grade and overlays go in the cut list; subtitles do not — those are built once at export.
5. **Verify.** Write `transcript.edit.md` by transcribing `segment-<n>-final.mp4`. Read every line of it. A cut that severed a word, dropped a needed clause, or joined two halves into a sentence that no longer parses will show up here. Where it does, fix the cut list and re-render, then re-transcribe.

**Gate.** Every segment folder holds a `segment-<n>-final.mp4` and a `transcript.edit.md`, and you have read every line of every edit transcript. Point the user at the edit transcripts.

# Phase 3 — Fix

A loop. Each pass:

1. Read `plan.md` and every transcript file in `edit/` for new comments. With no new comments, or once the user says to move on, go to Export.
2. Apply the changes, re-rendering only the segments they touch. Append any take or cut reversal to `decisions.md`.
3. Write `transcript.fix-<i>.md` for each changed segment, `<i>` counting from 1. Derive it from the existing transcript and the cuts you applied; reach for ElevenLabs again only when a change added footage no transcript covers.
4. Ask for feedback and stop.

**Gate.** Every comment in every transcript is either applied or answered back to the user.

# Phase 4 — Export

1. **Join.** Concatenate the segment finals in numeric order into `edit/final.mp4` with ffmpeg's concat demuxer and `-c copy`. `render.py` has no join mode; every segment final already came out of it at matching resolution and codec, so no re-encode is needed.
2. **Normalize** the joined file to -14 LUFS, the YouTube target. This is the only loudness pass in the pipeline.
3. **Subtitle.** Transcribe `edit/final.mp4` and build `edit/final.srt` from that transcript, so every cue's timing is measured against the delivered audio. Read it end to end: a sentence garbled across a join is how a bad join shows up in text. Where a term the segment transcripts spelled correctly comes back mangled, correct the spelling in the `.srt`.
4. **Inspect.** Run `timeline_view.py` on `final.mp4` across ±1.5s of every segment join, checking for a visual jump or an audio pop. Confirm the `ffprobe` duration matches the sum of the segment finals.

**Gate.** `final.mp4` and `final.srt` exist, duration matches, and you have inspected every join. Report the paths and the runtime.

# Phase 5 — Cleanup

1. Confirm the originals in `footage_dir` are byte-identical to how they started.
2. Delete the intermediates: `sync.json`, `base.mp4`, `clips_graded/`, preview and draft renders, and the node modules under each graphics slot.
3. Keep everything else the layout lists: transcripts, plans, `decisions.md`, cut lists, graphic briefs and renders, segment finals, `final.mp4`, `final.srt`, `project.md`.
4. Append a closing entry to `project.md`: the shape that shipped, the decisions worth remembering, and anything deferred.

**Gate.** `edit/` holds only the artifacts in the layout, and the originals are untouched.

---
name: z-process-audio
description: Create or reprocess an Auphonic production with speech isolation, AutoEQ, loudness normalization, a transcript, subtitles, shownotes, and chapters.
---

# Global Context

## Context Skills
- Run `/z-task-skill-structure`.

# Phase 1: Setup

## Action 1. Inputs
- Prompt the user for each input if it was not provided.
    - `mode` (required).
        - Options: `create` or `edit`.
    - `input_file`.
        - Required when `mode` is `create`.
        - Video or audio file to upload.
        - When `mode` is `edit`, use it only for output file names.
    - `output_dir`.
        - Folder for the Auphonic files.
        - Default: the folder that contains `input_file`.
        - Required when `input_file` is omitted.
    - `target_lufs`.
        - Integrated loudness target.
        - Used when `mode` is `create`.
        - Omit to skip loudness normalization.
    - `production_uuid`.
        - Auphonic production to reprocess.
        - When `mode` is `edit` and this is omitted, read `uuid` from `<output_dir>/auphonic-production.json`.

## Action 2. Auphonic CLI
- Run `auphonic version`.
- If `auphonic` is not on `PATH`, tell the user to install the Auphonic CLI from `https://auphonic.com/cli` and do not continue until `auphonic version` succeeds.
- Run `auphonic user`.
- If `auphonic user` fails, tell the user to run `auphonic auth login` and do not continue until `auphonic user` succeeds.

# Phase 2: Process

## Action 1. Create
- Skip when `mode` is `edit`.
- `<stem>` is the `input_file` name without its extension.
- Create and start one singletrack production with `auphonic process`.
- Do not pass `--speech-service`.
- Do not pass `--preset`.
- When `target_lufs` is set, pass `--norm-loudness` and `--loudness <target_lufs>`.
- When `target_lufs` is not set, pass `--norm-loudness=false`.
- When `input_file` is a video, pass `--output "format=video"`.
- When `input_file` is audio only, pass `--output "format=wav"`.

```bash
auphonic process "<input_file>" \
  --output-basename "<stem>-auphonic" \
  --denoise \
  --denoise-method speech_isolation \
  --filtering \
  --filter-method autoeq \
  --leveler \
  --max-peak -1 \
  --speech-recognition \
  --shownotes \
  --output "format=transcript,ending=html,filename=<stem>-auphonic-transcript.html" \
  --output "format=speech,ending=json,filename=<stem>-auphonic-speech.json" \
  --output "format=subtitle,ending=srt,filename=<stem>-auphonic-subtitles.srt" \
  --output "format=chaps" \
  --quiet
```

- Write `<output_dir>/auphonic-production.json`.

```json
{
  "uuid": "production uuid"
}
```

## Action 2. Edit
- Skip when `mode` is `create`.
- Change settings with `auphonic update "<production_uuid>"`.
- Pass only the flags that need to change.
- Do not pass `input_file` to `auphonic update`.
- Start the existing production with `auphonic start "<production_uuid>"`.

## Action 3. Download
- Wait until the production status is done.

```bash
auphonic wait "<production_uuid>"
```

- If `auphonic wait` exits with code 3, run it again until the status is done.
- Read the production.

```bash
auphonic get "<production_uuid>" --json
```

- If any `output_files[].filename` equals the `input_file` name, stop and tell the user.
- Download the output files into `output_dir`.

```bash
auphonic download "<production_uuid>" --dir "<output_dir>" --overwrite
```

- Write `<output_dir>/<output_basename>-shownotes.md` from the production `output_basename` and `shownotes` fields.
- Report the output paths when the files are saved.

```md
# Shownotes

## Subtitle
<shownotes.summaries.subtitle>

## Brief
<shownotes.summaries.brief>

## Summary
<shownotes.summaries.long>

## Tags
- <each entry in shownotes.tags>.
```

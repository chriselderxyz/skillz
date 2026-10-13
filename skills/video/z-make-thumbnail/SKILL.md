---
name: z-make-thumbnail
description: Brainstorm and build YouTube thumbnail variations in Affinity from a template, with Higgsfield image generation and reusable thumbnail styles, font styles, and thumbnail guidelines.
disable-model-invocation: true
---

# Global Context

## Context Skills
- Run `/z-task-skill-structure`.

## Shared Context
- Read `references/shared-context/definitions.md`.

# Phase 1: Setup

## Action 1. Memories
- Run the `/z-session-memory` skill.

## Action 2. Environment
- Verify the Affinity MCP `list_sdk_documentation` tool responds.
    - If it fails, ask the user to open Affinity, turn on its MCP server and file access in its MCP settings, and connect `http://localhost:6767/sse` to this agent, then verify again.
- Verify the Higgsfield MCP `models_explore` tool responds.
    - If it fails, ask the user to connect the Higgsfield MCP to this agent, then verify again.

## Action 3. Inputs
- Prompt the user for each missing input:
    - `project_folder` (required):
        - The project's folder in the working directory.
    - `video_description` (required):
        - What the video is about.
    - `thumbnail_descriptions`:
        - Descriptions of specific thumbnails to build, or a request to brainstorm **concepts** with any direction to explore.
    - `skip_brainstorm`:
        - Defaults to false when no `thumbnail_descriptions` is provided.
        - If the user gives `thumbnail_descriptions`, ask if they want to skip brainstorming new thumbnail ideas.
    - `thumbnail_style` (required):
        - Options: File names under `configs/thumbnail-styles/*` or "create new".
    - `font_style` (required):
        - Options: File names under `configs/font-styles/*` or "create new".
    - `thumbnail_guidelines` (required):
        - Options: File names under `configs/thumbnail-guidelines/*` or "create new".
- If `thumbnail_style`, `font_style`, or `thumbnail_guidelines` is "create new":
    - Use the `/z-create-config` skill to create a new config for this skill.
    - Use `thumbnail-styles`, `font-styles`, or `thumbnail-guidelines` as the config type.
    - For creation instructions, read the following for each input:
        - `thumbnail_style`: `references/create-configs/create-thumbnail-style.md`.
        - `font_style`: `references/create-configs/create-font-style.md`.
        - `thumbnail_guidelines`: `references/create-configs/create-thumbnail-guidelines.md`.

## Action 4. Thumbnail File
- Skip when `<project_folder>/thumbnails/thumbnail.af` exists.
- Copy `assets/templates/thumbnail-template.af` to `<project_folder>/thumbnails/thumbnail.af`.
- If `assets/templates/thumbnail-template.af` is missing, ask the user to add it, then copy it.

# Phase 2: Brainstorming

## Phase Context
- Skip this phase when `skip_brainstorm` is true.
- Read `references/shared-context/higgsfield.md`.
- Read `references/shared-context/thumbnail-rules.md`.
- Read `references/shared-context/thumbnail-style.md`.
- Read `references/shared-context/font-style.md`.
- Read the **thumbnail style**, **font style**, and **thumbnail guidelines**.

## Action 1. Plan Concepts
- Plan 6 **concepts**, or the number the user asks for.
- Make each **concept** a distinct idea for `video_description` that follows the user's direction.
- Follow the thumbnail rules, **thumbnail style**, **font style**, and **thumbnail guidelines** in each image prompt.
- Give each **concept** a `concept_number`, a kebab-case `concept_name`, a one-sentence description, and an image prompt.
- Number new **concepts** after the highest `concept_number` in `<project_folder>/thumbnails/concepts/`, starting at 1.

## Action 2. Generate Concepts
- Generate each **concept** image as a complete thumbnail, text included.
- Use `gpt_image_2` at `aspect_ratio` `16:9`, `quality` `low`, and `resolution` `1k`.
- Use a different model at the user's request.
- Save each image to `<project_folder>/thumbnails/concepts/<concept_number>-<concept_name>.png`.

## Gate
- Open the new **concept** images for the user.
- List each new **concept**'s `concept_number`, `concept_name`, and description.
- Ask the user to choose **concepts** to build, with any changes, or to give feedback for a new round.
- Rerun this phase with the feedback until the user chooses **concepts** to build.

# Phase 3: Build Thumbnails

## Phase Context
- Each chosen **concept** and each specific thumbnail description is one **variation**.

## Action 1. Build Subagent
- Give each new **variation** a kebab-case `variation_name`.
- Run one subagent with the following prompt.
- On a feedback pass, list only the **variations** to create or edit.
- Wait for the subagent to finish.

```md
You are building YouTube thumbnail **variations** in Affinity

Execute `references/subagents/build-variations.md`

Paths under `references/` and `scripts/` resolve from `<skill_dir>`.

- `project_folder`: <project_folder>.
- `video_description`: <video_description>.
- `thumbnail_style`: <thumbnail style config path>.
- `font_style`: <font style config path>.
- `thumbnail_guidelines`: <thumbnail guidelines config path>.
- Variations:
    - <Each new **variation**'s `variation_name` and description, with its **concept**'s image path and job id when it comes from a **concept**. Each existing **variation**'s layer name and the user's feedback>.
```

## Gate
- Tell the user the **variations** are ready to review in Affinity.
- Summarize what the subagent built and any issues it reported.
- Ask the user for feedback:
    - Rerun this phase for new **variations** or edits.
    - Rerun Phase 2 for new **concepts**.
- Move to Phase 4 when the user approves.

# Phase 4: Cleanup

- Delete `~/Desktop/z-make-thumbnail/`.

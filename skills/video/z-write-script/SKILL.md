---
name: z-write-script
description: Use when writing or editing a video outline and script.
disable-model-invocation: true
---

# Global Context

## Skills
- Run these skills for context.
    - `/z-task-skill-structure`.
    - `/z-markdown-comments`.
- Use `obsidian` skills when required.

## Publication Document
- The single document this skill writes to.
- Outline, script, and description/caption are sections of this one document, not separate documents.
    - `# Outline`.
    - `# Script`.
    - `# Description/Caption`.

## Brand Voice Guidelines
- Don't use brand voice context as an excuse to force a narrative.
- If a narrative doesn't fit a video, then it doesn't belong, even if the brand voice suggests something like it.

## Video Length
- Video length is inconsequential, it will be as long as it needs to be to convey the points fully and correctly.
- Do not cut for the sake of breivity, and do not pad for the sake of length.
- Do not make a just incase cut list.

## Review and Edit Loops

- Applies to the user interactive portion of Outline and Script writing.
- Repeat the loop until the user explicitly approves the final output.

### Loop Steps
- Before running a Review and Edit loop, run the `/z-checkpointing` skill.
    - Use a checkpoint before all changes and after all user edits to the **publication document**.
- Ask the user to review the current **publication document**.
- Use a diff between checkpoints to find all.
    - New user feedback.
    - User edits (do not remove these).
- Address feedback and ask for review again.

# Phase 1: Setup

## Action 1. Memories
- Run the `/z-session-memory` skill.

## Action 2. Inputs
- Prompt the user for each input if it wasn't provided.
    - `video_idea` (required).
        - The subject and intent of the video.
    - `pub_folder`.
        - Optional path to a folder to put a new **publication document** in.
        - Default to the working directory.
    - `pub_doc`.
        - Optional path to a pre-existing **publication document**.
    - `ref_notes`.
        - Note names of previous **publication documents** to model after.
    - `script_type`.
        - Options: Files in `configs/script-types/*`, 'create new' or none.
    - `brand_voice`.
        - Options: Files in `configs/brand-voices/*`, 'create new' or none.
    - `local_research_guide`.
        - Options: Files in `configs/local-research-guides/*`, 'create new' or none.

- If the user selects 'create new' for any input option.
    - Read the creation instructions for the input, and use its config path.
        - `script_type`: `references/script-type-creation-guidelines.md`, `configs/script-types/<name>.md`.
        - `brand_voice`: `references/brand-voice-creation-guidelines.md`, `configs/brand-voices/<name>.md`.
        - `local_research_guide`: `references/local-research-guide-creation-guidelines.md`, `configs/local-research-guides/<name>.md`.
    - Ask the user for a name for the new config, and for any reference files to model it on.
    - Ask clarifying questions until you can write the config.
    - Write the config to its path.
    - Show the user the new config, and revise it until they approve.
    - Use the new config for that input.

## Action 3. Read Config
- Read the `configs/*` for `script_type` and `brand_voice` (if they were not just created).

## Action 4. Create Publication Document
- If `pub_doc` is not set, use `assets/script-template` to create a new **publication document** in `pub_folder`.
- Use the `video_idea` to derive a short and reasonable name.
- If there is a naming style in `pub_folder`, adhere to that.

# Phase 2: Pick Research Topics

- Given the `video_idea`, select 1-5 research topics.
- Do not add extra research topics unless it is actually required for the video.

## Gate
- Verify the selected research topics with the user.

# Phase 3: Research

## Action 1. Online Research
- Spin up a subagent to research each topic.
- If the user asked to use a specific research skill or workflow, use that.
- Otherwise use the /z-research-thing skill.
- Give the subagent a brief summary of the video being scripted, along with the research topic they are responsible for.

## Action 2. Local Research

### Action Context
- Use `configs/local-research-guides/<local_research_guide>`.

### A. Search
- Locate potential files to read.
- Dedupe the candidates.

### Gate
- Present the note names to the user and wait for comments or approval.
- Give a set of suggested notes.

### B. Read
- Read the full contents of approved notes.

## Gate
- Wait for all subagents to complete.

# Phase 4: Outline

## Phase Context

### Outline Guidelines
- Rough bullet points only.
- Do not expand on topics or write script lines.
- Do not add a hook as a base for the video.
    - Hooks come AFTER the outline is approved so they reflect what the actual video says.
- All headings under `# Outline` MUST be prefixed with `Outline - ` to avoid heading conflicts.

### Video Section Guidelines
- Each section makes a SINGLE point or teaches one concept.
- Sections must flow logically.
- Do not group multiple points in one section - related points flow together between sections, they are not grouped together.
- Do not plan multiple sections illustrating the same point, even if there are slight differences.
- Sections end with conclusions, conclusions don't get their own sections.

### Outline Format
```md
# Outline
## Summary
### Premise
- Suggested video premise/thesis.
- Not needed for tutorials where there is no thesis.
### Sections
- Intro.
- Section 1: How the section fits in the story/flow.
- Section 2: How section 2 fits.
- <rest-of-sections>.
- Outro.
## Section 1: Section Name
### Purpose
- Purpose of the section.
- Point the section is making or concept its explaining.
### Evidence/Demonstrations
- Evidence or practical demonstrations that will be presented to support the point the section is making or concept it is teaching.
- Each different piece of evidence or demonstration should be a `#### Subsection`.
```

## Action 1. Create Outline
- Use the `video_idea`, `ref_notes` and research results to draft a complete script outline under `# Outline`.

## Action 2. Review and Edit Loop
- Run an interactive Review and Edit loop for the outline.

# Phase 5: Script

## Phase Context
Read `references/script-writing-rules`.

## Action 1. Write Script
- Use the final outline draft as structure for the script.
- Write the script under `# Script`.

## Action 2. Review and Edit Loop

### Action Context
- Headings are contextual to the content, not feedback.
    - Example Feedback: [NOTE: the coding example here is arbitrary, it should show a realist example].
        - Bad Heading: `### A Real One`.
        - Good Heading: `### Uploader Synctest Example`.
- Preserve user edited content unless explicitly told to modify or revert it.
- Do NOT regenerate regions from your own hardcoded content, that is how user edits get destroyed.
- Do NOT add content back in that the user removed.
- Do surgical replacements instead of rebuilding whole regions, large changes destroy user edits.
- The script must still flow nicely when edits restructure the script, DO NOT copy paste one part of the script to another without adjusting it to fit where it's going.
- Preserve ambiguous comments and ask about them.
- Do not explain why an edit took place in the script, the whole point is to change the script, it needs no references to past versions.
- Do not add non-heading text that is meant as a label for the reader, no one reads titles outloud from a script.
- If the user requests restructuring.
    - After moving sections, read the **publication document** again and make sure each section still flows together in the new structure.
    - Modify moved sections to fit the new location in the script.
- ONLY do the requested edits, do not invent tasks.

### Actions
- Run a Review and Edit loop for the script.
- The outline should be updated to match any script edits.

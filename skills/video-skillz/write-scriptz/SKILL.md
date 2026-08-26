---
name: write-scriptz
description: Syntax to use to receive user feedback on a markdown artifact. Only invoked by other skills writing outputs to markdown.
---

# Context

## Skills
- Run these skills for context
    - `/skill-workflowz`
    - `/markdown-commentz`
- Use `obsidian` skills when required

## Hard Scripting Rules
- Do not use acronyms in scripts
- The script should flow, no rough transitions
- Do not use online research verbatim, it must be re-written
- Do not add tables to a script

## Script Guidelines
### Causal Explanations
- All explanations should follow a causal chain of logic, tell a story
- The conclusion of a point should be predictable given the content before it

Good Example: Reads as a story
```
- I've been tired in the morning for most of my life
- But I started doing some research on glutamine
- The research shows 'this'
- Now I've been taking it for the last month
- And my sleep score has improved
```

Bad Example: Reads as a research report
```
- Glutamine has been shown in studies to...
- The mechanism of action is proposed to be...
- It's supposed to work like this...
- My sleep score has improved x points after taking glutamine
```

# Phase 1: Prep

## Memories
Run the `/session-memoriez` skill

## Inputs
Prompt the user for each input if it wasn't provided
- `video_idea` (required)
    - The subject and intent of the video
- `script_file`
    - Optional path to a pre-existing script file to use
- `ref_notes`
    - Note names of a previous publications to model the script after
- `script_type`
    - Options: Files in `assets/script-types/*`, 'create new' or none
- `brand_voice`
    - Options: Files in `assets/brand-voices/*`, 'create new' or none

If the user selects 'create new'
- Prompt them to provide the relevant information
- Compile into a guide used by the script writing agent
- Ask for the users approval or comments
- Save the final draft a new .md file in the correct asset folder
- Use that file as the input variable for this run

## Read Assets
- Read the `assets/*` for `script_type` and `brand_voice` (if they were not just created)

## Create Script/Publication File
- If `script_file` is not set, use `references/script-template` to create a new script file in `7. Publication/`
- Use the `video_idea` to derive a short and reasonable name

# Phase 2: Pick Research Topics

## Pick Topics
- Given the `video_idea`, select 1-5 research topics
- Do not add extra research topics unless it is actually required for the video

## Gate
- Verify the selected research topics with the user

# Phase 3: Research

## Online Research
- Spin up a subagent to research each topic
- If the user asked to use a specific research skill or workflow, use that
- Otherwise use the /research-thingz skill
- Give the subagent a brief summary of the video being scripted, along with the research topic they are responsible for

## Local Research

### Search
- Look for local files in the working directory related to any of the research topics using `obsidian search`
- Search for files in the following folders
    - `./2. Index`: Related index notes
    - Use `obsidian links` to collect the notes it references
    - Relevant notes linked to by indexes
    - `4. Permanent`: Ideas and technical notes
    - `3. Sources`: Source notes
    - `7. Publication`: Previous publications
- Do not use `search:context`, previews, or `read` on any candidate file
- Dedup the candidates

### Gate
- Present the note names to the user and wait for comments or approval

### Read
- Read the full contents of approved notes
- Set the script note's `inputs` frontmatter property to a YAML list of wikilinks for exactly the approved notes

## Gate
- Wait for all subagents to complete

# Phase 4: Outline
- Use the `video_idea`, `ref_notes` and research results to draft a complete script outline
- Place the outline under the `# Outline` heading in the publication note
- Tell the user the outline is ready for review
- Wait for an explicit instruction to continue

# Phase 5: Script

- After the user continues, read the publication note again
- Incorporate the current outline and all user edits and comments for writing the script
- If an annotation changes the intended meaning ambiguously, ask before writing
- Write the complete script under `# Script`
- Tell the user the script is ready
- Wait until the user says approves or gives comments

## Phase 6: Review Loop

- On each turn:
    - Read the publication note again
    - Find all new user feedback
    - Revise the affected script passages while keeping the approved outline and source material coherent
    - Remove comments only when their requested change is clearly resolved
    - Preserve ambiguous comments and ask about them
    - Write the revised `# Script` section through the CLI and ask the user to review again
- Repeat until the user explicitly approves the script
- On approval, make no further content changes unless requested; report the publication note path and finish

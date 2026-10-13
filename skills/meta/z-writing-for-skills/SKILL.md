---
name: z-writing-for-skills
description: Use anytime you are creating or editing ANY part of a skill (including scripts) for best practices, rules and guidelines to follow.
---

# Verification (IMPORTANT!!)
- Before finishing any changes to a skill, check every change against each Hard Rule and Guideline in this skill.
    - Check changes in every skill file, including scripts.
- Fix EVERY violation, then repeat the check until none remain.

# Hard Rules (IMPORTANT!!)

## DO NOT Explain Why Something is Not Another Way
- The agent only needs to know what to do, not reasons why something is done one way instead of another.
- This is especially important when editing a skill, if the user asks for a change:
    - Do not explain in the skill why the change was made from what it was before, just do the change like you were asked.
    - Do not include instructions to not do something the old way, the skill ONLY needs to know what to do now. Running the skill WILL NOT have ANY context of how it used to look, so do not include it

### Bad Example
- Before: Write text that should be included in the graphic on the 'description' property of the source object
- Use Request: The text should not be on description, it should live on its own text_elements property
- After: Write text that should be included in the graphic on the 'text_elements' property of the source object, not on the 'description' property
- The Problem: The agent DOES NOT need to be told to not write on the 'description' property. That is context from the old version of the skill. When you tell the agent what to do, it automatically means don't do the other thing, no clarification is needed.

## DO NOT Explain Future Steps
- The Global Context and Phases do not need to know what future steps will do.

### Bad Example
```md
# Global Context
- `edit/edit.json` holds the whole video.
    - `sources` and the input variable settings are written by hand in Phase 2.
    - scenes are filled in during the cut, never written in Phase 2.
```

- The explanation of what happens in a future phase is not required

## No Extraneous Information
- Do Not add information the agent doesn't need to know.
- The agent doesn't need to know why something is, ONLY what to do.

## No Script Explainations
- The agent does not need to know about logic handled by a script, only when and how to use it.
- DO NOT add script explainations in markdown.
- DO NOT add instructions that cover something a script already does.

## Reference File Structure
- If a file in `reference/` is used to perform a sequence of actions, and not just for context, run `/z-task-skill-structure` and use the SKILL.md structure as a model for the reference file.

## Reference File Content
- Reference files do not need information about where in the SKILL.md they were referenced, or why it wouldn't have been referenced.

### Bad Example
```md
Reached from Produce, step 3. Source Groups with no approved graphic skip this entirely.
```

- It does not matter where a file was "reached" from

## Progressive Disclosure
- The agent running a skill should get context at the exact point its needed.
- For **task-based skills**
    - Use `# Global Context` for context used in multiple phases.
    - Use `## Phase Context` for context used in a single phase.
    - Use `### Action Context` for context used in a single action within a phase.
    - If context is only needed on a branching path of the skill, put it in `references/` and have the agent read it only when required.

## Do Not Add Extraneous Global Context
- Global Context is for things that multiple phases NEED to know.
- It is not a dumping ground for general information about the skill.

### Bad Example

- The agent doesn't need to know this up front.
- It gets explained and infered through actual Actions in the Phase that writes to the files.
- This also breaks progressive disclosure, only add context WHERE IT IS NEEDED.

```md
# Global Context
## Authored Files
- `edit/edit.json` is the plan, everything the user reviews.
    - The source of truth for every **scene**, **line**, **take**, **layer**, and PIP decision.
    - Also holds `title`, `description`, and `issues`.
    - Read `references/shared-context/plan.md` before reading or writing it.
```

## Do Not Put Instructions in Context Sections
- Context sections are for information required for actions/tasks.
- The instruction to do an action/task is always put in a Phases Action.

## Writing Files
- When the skill instucts an agent to write a file, it either needs a description of the file OR an example to follow.
- DO NOT use both.

# Guidelines

## General Prose
- Use the least number of words required to communicate tasks or context to the agent.

## Use Bullet Points
- Use bullet points for every line (`-`).
- End every bullet point with a period.
- A new bullet point is used for each piece of information or command.
- Use nested bullet points for related additional info.
- A bullet point introducing nested items has no period:
    - List item one.

## Avoid Contractions
- Prefer full form over contractions.
- Example: Do Not, instead of Don't.

## Inputs
- Inputs to the skill should be verified and/or collected in Phase 1.
- Inputs are used to customize skill behaviour.
- Input names should be `snake_case`.

### Example
```md
# Phase 1: Setup

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
```

## Meta Skills
- Add these to skills you are writing/editing as required.
- It is preferrable to directly call skills, rather than relying on the agent to do it automatically.

### z-session-memory
- Adds session memory to the skill, so you can continue the same skill run from a new session.
- Long running **task-based skills** should use this.
- If used, this should be run as the first action in Phase 1.

### z-checkpointing
- Add checkpoint functionality when editing output files.
- **Task-based skills** that edit files multiple times or receive user feedback in files directly should use this.
- If used, run this at the start of the Phase/Action that requires file editing.
- It can also be run in Global Context if required in multiple phases.

#### Example
```md
# Global Context

## Review and Edit Loops
- Process run by multiple phases.

### Loop Steps
- Before running a Review and Edit loop, run the `/z-checkpointing` skill.
    - Use a checkpoint before all changes and after all user edits to the **publication document**.
- Ask the user to review the current **publication document**.
- Use a diff between checkpoints to find all.
    - New user feedback.
    - User edits (do not remove these).
- Address feedback and ask for review again.
```

### z-create-config
- Used when a user selects "create new" for **config** inputs.
- This is a general skill, the calling skill still needs to know.
    - What **config-type** to use (`configs/<config-type>/`).
    - Guidelines for creating each **config-type** (branching path, put in `references/`).

#### Example

```md
# Phase 1: Setup

## Action 2. Inputs

... input list

- If the user selects 'create new' for any input option.
    - Use the `/z-create-config` skill to create a new **config** for this skill.
    - Use script-type, brand-voice, or local-research-guide as the **config-type**.
    - For guidelines, read the following for each input.
        - `script_type`: `references/script-type-creation-guidelines`.
        - `brand_voice`: `references/brand-voice-creation-guidelines`.
        - `local_research_guide`: `references/local-research-guide-creation-guidelines`.
```

### z-task-skill-structure
- Outlines **task-based skill** structure.
- This should be run by all **task-based skills** at the top of Global Context.

#### Example
```md
# Global Context
## Run Context Skills
- Run `/z-task-skill-structure`.
```

### z-markdown-comments
- Describes the syntax used for user feedback in markdown documents.
- The skill should use this when user feedback is required on markdown documents.

#### Example
```md
# Phase 4: Review and Edit
## Phase Context
- Run `/z-markdown-comments` for feedback syntax.
```

### z-search-and-fetch-preferences
- The users preferred tools and best practices when searching and fetching online.
- The skill should use this when it does any online searching or fetching.

#### Example
```md
# Phase 2: Research
## Phase Context
- Run `/z-search-and-fetch-preferences` for guidelines for online search and fetch.
```

## Subagents

### When to Use
- Use subagents for Actions in a skill when any are true:
    - It will result in less context in the main agent.
    - It facilitates parallel execution.
    - The main agent only requires a summarized result for it's task, and not full context of how the result was found or created.

### Subagent Task Files
- Each subagent should follow steps defined in `references/subagents/<task-name>.md`.
- The subagent task files should follow the same structure as a **task-based skill**.

### Shared Context for Subagents
- If a large amount of context is shared between the main agent, and any subagents, move the context to `references/shared-context/<name>.md`.

### Subagent Global Context
- If multiple subagents are used by the skill, add a `## Subagent Use` section to `# Global Context` that provides information passed to every subagent.
- If only one subagent is used, the context for the agent should be local to the call.

#### Example
```md
## Subagent Use
- Tell any subagent you spin up the following.
    - All raw **sources** are in `<src>/*`, do not modify them.
    - `references/`, `assets/`, `scripts/` and `configs/` resolve from the skill directory - `<skill_dir>`.
    - Read context from `references/shared-context/<name>.md`.
```

### Running Subagents Example
```md
# Phase 2: Research
## Action 1

- Wait for all subagents to complete before moving on.

### A. Online Research
- Run a subagent to do online research.
- Give it a topic to research and ask for a summary of results back.
- The subagent should run steps in `references/subagents/research.md`.

### B. Local Research
- Run a subagent to do local research using the following prompt.
`<full-prompt>`
```

### Wait for Agents
- The skill should always wait for agents to complete before moving on
- The main agent may do other tasks in parallel, but anything dependent on the subagent output must happen after

### Don't Overexplain an Agents Purpose
- The prompt the skill passes to a subagent is enough context for the main skill agent
- The main agent does not need another line saying: `This subagent is for <purpose>`
- It should already have a line like: `Run a subagent with the following prompt to <do thing>`

## Definitions
- Add skill specific term definitions to Global Context under a `## Definitions` heading
- When referencing terms in the skill or supporting skill files, use **bold**
- Do not bold headings

# Skill Structure

## Skill Types

### Task-Based Skill
- A skill that executes a sequence of steps to accomplish a goal.

### Context Only Skill
- A skill that just provides guidance or context useful for a separate task the agent is working on (skill or otherwise).

## SKILL.md Structure
- If the skill your working on is a **task-based skill**, run `z-task-skill-structure` to understand the SKILL.md structure.
- **Context only skills** don't have a defined SKILL.md structure. Use top level headings for each type of context that is needed.

## Skill Folders

### Base Folders
- `references/` for context `.md` files that the skill will read.
- `assets/` for templates, boilerplate documents, icons, fonts, stylesheets, etc.
- `scripts/` for scripts the skill will run.
- `configs/` for user generated config files.

### The Configs Folder
- **Config Files**.
    - User created or created by you with user assistance.
    - Used to customize a skill for different use cases.
    - **Config** types are defined by skills that have them.
    - **Config** files can be any type (.md, .json, etc.).
- **Config** files go in the `configs/` folder in the skill directory.

### Subfolders
- If there are more than 5 files in `references/`, `assets/` or `scripts`, add subfolders for organization.
- Subfolders for assets and scripts depend on the skill and actual files, decide names yourself.
- If there aren't more than 5 then DO NOT use subfolders.
- Reference subfolders have some standard names, but can also vary by skill if you deem it necessary.

#### References Subfolder Examples
- `references/subagents`: For subagent tasks.
- `references/shared-context`: For context shared by the main agent and/or multiple subagents.
- `references/create-configs`: For context or steps used when creating a new **config file** for the user.
- `references/create-artifacts`: For context or steps used when creating skill output files.

## File Names
- `SKILL.md` for the main .md file.
- All other files are named with `kebab-case`.

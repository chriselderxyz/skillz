---
name: z-create-skill
description: Use when creating an agent skill.
disable-model-invocation: true
---

# Global Context

## Writing Guidelines
- Run `/z-writing-for-skills` for best practices, rules and guidelines for writing skills.

# Phase 1: Setup

## Action 1. Memories
- Run the `/z-session-memory` skill.

## Action 2. Inputs
- Prompt the user for each input if it wasn't provided, or if clarification is required.
    - `name` (required).
        - The name for the new skill.
    - `requirements` (required).
        - A description of the skill that includes: what it does, how it should behave, what the outcome of using the skill should be.
    - `inputs`.
        - A list of inputs the skill should accept, with descriptions of what each is.

# Phase 2: Draft Skill

## Action 1. Create Skill
- Create the skill folder and SKILL.md.

## Action 2. Determine Skill Type
- Select a skill type (task-based or context-only).

## Action 3. Get Context
- For a task-based skill, run `z-task-skill-structure` for context.

## Action 4. Plan Initial Draft
- Write an initial skill draft, including the SKILL.md, and any supporting files.

# Phase 3: Interactive Review and Edit Loop

## Phase Context
- Run `z-markdown-comments` to learn markdown feedback syntax.

## Action 1. Checkpointing
- Before starting the review + edit loop, run the `/z-checkpointing` skill.
- Checkpoint all files before any edits and after user edits.

## Action 2. Get Feedback
- Tell the user to review the skill and provide feedback in the files directly or in chat.

## Action 3. Address Feedback
- Address the users feedback then move back to step 2.
- Only finish the loop after user approval.

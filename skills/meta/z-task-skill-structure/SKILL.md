---
name: z-task-skill-structure
description: Only invoked from other skills. Provides context on the different steps in a SKILL.md file.
---

# SKILL.md Structure

```md
# Global Context
- Subheadings for different types of context.

# Phase 1: <phase-name>

## Phase Context
- Context specific to this phase.
- Use subheadings for different types of context.

## Action 1. <action-name>

### Action Context
- Context specific to this step.
- use subheadings for different types of context.

### A. <subaction-name>
- Action steps.

### B. <subaction-name>
- Action steps.

## Action 2. <action-name>
- Action list.
- No subheadings needed if the step is short and has no extra context.

## Gate
- Stop for user feedback.
- Do not proceed until approved.
- Gate headings are not numbered.
- ONLY STOP AT GATES.
- Do not stop for user feedback at arbitrary points.

## Action 3. <action-name>
...

# Phase 2: <phase-name>
...
```

# SKILL.md Execution Steps
- Order.
    - Read Global Context.
    - Execute each phase in linear order.
- Each piece is marked with a Heading.
    - Global Context: Relevant information for the whole workflow.
    - Phases: Large steps in the workflow.
    - Actions: Individual steps inside each phase.
        - Heading is `Action <n>. <action-name>`.
        - A phase with one action uses `Action 1`.
    - Subactions: Individual steps inside each Action.

# Config Folder
- The `configs/` folder in the skill directory used to house user-created config files.
- Config files are used to customize skill behaviour for different use cases.

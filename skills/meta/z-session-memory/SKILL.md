---
name: z-session-memory
description: Only used from other skills. Adds session memory to the skill.
---

# Global Context

## Purpose
- Give the agent durable memory when using another skill over multiple sessions.

## Memory Location
- Memories are stored on a per skill, per project basis.
- Memories should be saved at `.skill-session-memory/<skill-name>/<project-name>/memory.md`.
- If this skill is running in an environment like Cursor or in a git repository, use the agents global temp folder instead of the working directory; otherwise the user may be forced to review the temporary file.

## Memory File Structure
```md
---
finished: false
---
# Phase <n> — <YYYY>-<MM>-<DD>
## Strategy
- One paragraph describing the approach.
## Decisions
- All choices for the phase, with reasoning.
## Issues
- Any issues the user flagged, and what solution was applied.
```

# Phase 1. Read Memories

## Action 1. Search
- Look for existing memory files for the calling skill.
- Only consider memories where the finished frontmatter property is `false`.
- Only read the frontmatter, do not read the whole file.

## Gate
- Present the list of project-names to the user that have an unfinished memory file.
- Sort them by modification date (newest to oldest).
- Ask if this session is a continuation of any of the projects.

## Action 2. Resume Session
- If the user indicates this session is a continuation.
    - Read the full memory file for the project.
    - Summarize the completed phases in 1-2 sentences for the user.

# Phase 2. Write Memories

## Action 1. Create
- If this is a new project (not a continuation).
    - Decide on a project name if it wasn't provided by the user.
    - Create `.skill-session-memory/<skill-name>/<project-name>/memory.md`.
    - Set finished to `false`.

## Action 2. Write
After each phase of the calling skill, write to `memory.md`.

# Phase 3. Finish

- After the project the calling skill is working on is complete, change the finished property to `true`.
- Do this ONLY after the full project is finished and approved by the user.

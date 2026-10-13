---
name: z-checkpointing
description: Use to apply checkpointing for all file edits done by a skill. Only used via other skills.
---

# Phase 1: Checkpoints

## Phase Context
- Save checkpoint files in `.skill-temp/<skill-name>/<task-name>/*`.
- Use timestamps in the name of checkpoint files to organize.
- If this skill is running in an environment like Cursor or in a git repository, use the agents global temp folder instead of the working directory; otherwise the user may be forced to review the temporary file.

## Action 1. Pre-Edit
- Before ANY edit to a file, make a checkpoint copy.

## Action 2. User Edits
- If you receive user feedback or the user edits the file directly, save a checkpoint file before making any additional changes to the file.
- Use diffs between the old and new checkpoint files to identify user feedback and edits.

# Phase 2: Cleanup

- After a task or skill execution is complete and approved, remove all temporary checkpoint copies of the related files.

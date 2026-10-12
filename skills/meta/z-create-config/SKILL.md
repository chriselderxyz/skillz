---
name: z-create-config
description: Use when creating or editing config files for any skill in it's configs/ folder.
---

# Global Context

## Goal
- Create a config file for a specific skill.

## Config Files
- User created or created by you with user assistance.
- Used to customize a skill for different use cases.
- Config types are defined by skills that have them.
- Config files can be any type (.md, .json, etc.).

# Phase 1: Get Inputs

## Phase Context
- Inputs will be different for each config file type.
- The user or calling agent should provide you with the required inputs.

## Action 1
- Ask the user for a new name for the config.
- Ask the user to provide any reference files used to model the new config off of.
- Ask the user clarifying questions until you have a good enough understanding to write the new config.

# Phase 2: Write Config

## Action 1
- Create the new config file in `configs/<config-type>/<config-name>`.
- If the calling skill has no config type, create it in `configs/<config-name>`.
- If this config was created via a user selecting "create new" as an input option in another skill, use the new config for that input for the rest of this session.

# Phase 3. Review Loop

## Action 1
- Tell the user where the new document lives.
- Ask the user for feedback or approval.
- Address comments and review again.
- Finish when approved.

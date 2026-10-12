---
name: z-markdown-comments
description: Syntax to use to receive user feedback on a markdown artifact. Only invoked by other skills writing outputs to markdown.
---

# User Feedback Markdown Syntax

## General Form
```
Content to apply changes to
[COMMAND: context]
```

## Commands
- [EDIT: Request for an edit].
- [CUT: Request to remove content].
- [EXPAND]: expand on a point.
- [NOTE: Take into consideration and make changes].

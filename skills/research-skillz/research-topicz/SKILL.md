---
name: research-topicz
description: Do deep research on a topic.
---

# Phase 1: Decompose
- Break the research topic into a number of independent questions or research angles
- The questions should reveal
    - Background topic information
    - The 'what', 'how' and 'why' of a topic
- Consider what this research is being used for
- Use reasoning to pick the best 5 questions, unless given a different `limit`

## Phase 2: Fan-Out Research
- Spin up a subagent for each of the selected questions and make it run the `/answer-questionz` skill
- Wait for the subagents to complete

## Phase 3: Cross-Check
- Spin up a subagent with each answer you received in Phase 2 and make it run the `/run-cross-checkz` skill to verify the information 
- Wait for the subagents to complete
- If no sources could be found to verify an answer, take note and move on
- If any of the results indicate low confidence that the information was correct
    - Go back to Phase 2 and ask the question again
    - Give the subagent context returned by `/run-cross-checkz`

# Phase 4: Filter
- Discard any information that could not be verified by Phase 3

# Phase 5: Synthesize
- Summarize all information that has not been discarded into a single report and return it
- The caller should have enough information from your report to speak confidently about the research topic
- The report should include citations back to supporting sources

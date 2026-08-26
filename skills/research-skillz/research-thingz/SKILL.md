---
name: research-thingz
description: Do deep research on a topic or question.
---

# Phase 1: Research Loop

Run the following research loop for each topic or question given

## 1. Web Search
- Use the users preferred search tool to find a list of primary and secondary sources to answer the specific question or the 'what', 'how' and 'why' of a topic
    - result snippets + URLs
- Use a short, specific query (not the whole question)
- Judge which sources look relevant enough to fetch
- Consider what this research is being used for

## 2. Fetch
- Fetch the full page content of relevant sources
- Extract specific information relevant to the question
- Note the source URL for all information

## 3. Reaccess
- Do the findings adequetly answer the question?
- If not, identify remaining gaps and loop back to step 1

# Phase 2: Cross-Check
- Spin up a subagent
- Give it the information or answers that you have found, along with the sources
- make it run the `/run-cross-checkz` skill to verify the information
- Wait for the subagent to complete
- Information that can't be validated by the cross check will receive a lower confidence score
- If any of the results indicate a very low confidence that the information was correct
    - Go back to Phase 1 to investigate further using the context received from the subagent
    - Cap the loop back to one run (do not continually try to research and verify the same information if cross-check comes back negative multiple times)

# Phase 4: Filter
- Discard any information that could not be verified by Phase 3

# Phase 5: Synthesize
- Summarize all information that has not been discarded into a single report and return it
- The caller should have enough information from your report to speak confidently about the research topic
- The report should include citations back to supporting sources

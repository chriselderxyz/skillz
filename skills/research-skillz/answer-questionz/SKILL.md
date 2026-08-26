---
name: answer-questionz
description: When the user asks you to use 'deep research' to answer questions, use this skill. Do not invoke for regular questions.
---

# Phase 1: Research Loop

Run the following research loop for each question given

## 1. Web Search
- Use the users preferred search tool to find a list of primary and secondary sources to answer the question (result snippets + URLs)
- Use a short, specific query (not the whole question)
- Judge which sources look relevant enough to fetch

## 2. Fetch
- Fetch the full page content of relevant sources
- Extract specific information relevant to the question
- Note the source URL for all information

### 3. Reaccess
- Do the findings adequetly answer the question?
- If not, identify remaining gaps and loop back to step 1

# Phase 2: Respond
- Summarize the answers to each question, and provide references to the most relevant sources

WIP - just notes for now

DO NOT put explainations or logic into a markdown file for the agent to consume if it is already handled by a script. The agent only needs to know how and when to invoke the script

The agent should read files on demand, not all at once at the beginning (NOTE for video - kindof counter to what you think as a programmer where constants are defined at the top)

Reference files do not need information about where in the SKILL.md they were referenced, or why it wouldn't have been referenced
- Bad Example: Reached from Produce, step 3. Segments with no approved graphic skip this entirely.


Use
- kebab-case for `references/` and `assets/` file names
- snake_case for script names and skill input variables


Don't add information the agent doesn't need to know
- If you change something in a script, the agent still only needs to know how to call it
- The agent doesn't need to know why something is, only what to do

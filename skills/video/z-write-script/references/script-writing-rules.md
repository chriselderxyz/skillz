
# Script Structure
- Structure should match the approved outline.
- All headings under `# Script` MUST be prefixed with `Script - ` to avoid heading conflicts.

Example Structure.
```md
# Script
## Intro
## <section-one-name>
### <subsection-name>
### <subsection-name>
## <section-two-name>
### <subsection-name>
### <subsection-name>
<rest-of-the-sections>...
## Outro
```

# Intro Guidelines

## Structure
- Hook.
- Context for the video (ONLY WHAT'S REQUIRED - brief).
- Bridge to first section (can be specific or generic).

## No Summaries
- Do not summarize the video sections in the Intro, it's boring and loses viewers.
- The Intro only promises an outcome, it does not describe how that outcome is going to be presented.

## Hooks
- Put the hook right at the start of the video.
- SHORT talking head shots that kick off the Intro.
- The hook should.
    - Confirm to the viewer the video matches what they clicked on.
    - Create a reason to stay - curiosity gap.

## Common Hook Types
- Bold Statement Hook.
    - Make a claim that's surprising or contrarian.
    - DO NOT be contrarian for controversies sake.
- Relatable Problem Hook.
    - Name a pain point the audience has.
- Question Hook.
    - Pose a question the viewer wants answered.
- Visual Hook.
    - Lead with something eyecatching before a word is spoken.
    - Good for shorts.

# Outro Guidelines
- Don't summarize the video in the outro.

# Grammar
- The script is a **performance score**, not prose.
— Spelling is bent to encode delivery.

# Diagrams and Motion Graphics
- Suggest diagrams or motion graphics to display if they will help the viewer understand a point.
- Prefer motion graphics over diagrams, they are more engaging.

Suggestions should be in a caption, with a **stage direction** to present it.

**Show Graphic**
> Suggested Graphic

# Causal Explanations
- All explanations should follow a causal chain of logic, tell a story.
- The conclusion of a point should be almost predictable given the content before it.

Bad Example: Research report. Facts listed, jargon first, result bolted on with no chain connecting them.
```
Glutamine has been shown in studies to improve subjective sleep quality.

The proposed mechanism of action is conversion to GABA, an inhibitory neurotransmitter that reduces neuronal excitability.

Sleep scores improved X points following supplementation.
```

Good Example: Lived story. Each beat causes the next, so the ending is obvious before you say it.
```
I've been tired in the morning for most of my life.

I started looking into why, and kept seeing glutamine come up.

Your body turns glutamine into the chemical your brain uses to calm down at night.

So I started taking it before bed.

A month later my sleep score is up, and I actually feel awake in the morning.
```

# No Fluff
- Sections must only include content that helps make the sections point clearer.
- Do not pad with unrelated content.
- Do not pad with related but un-needed content.

# Explain Claims Fully
- Points or claims made in the script need full explainations.
- Explainations should be made as brief as possible, while still fully explaining.
- Do not assume the viewer is stupid, the simplest pieces of an explaination can be glossed over.
- Do not assume the viewer is an expert, do not gloss over key pieces of information.
- The viewer should always understand the what, why and how backing any points/claims.

## Example: Explaining Flaky Clock Tests in Go
Bad:
```
The duration is not a promise it is a suggestion

The scheduler gets busy, the machine has other work, and we lose the timing assumption
```

Good:
```
In Go, 
- when you sleep for a millisecond,
- Or use something like time.After like we’re doing here
- you are NOT asking to be woken up IN a millisecond.
- You're asking to be woken up AFTER a millisecond.

And once that timer fires,
- the runtime still has to get your goroutine back onto a thread,
- Annnd the operating system has to get that thread back onto a core.

That wake up cost is maybe a couple hundred microseconds
- Which, can push the measured time outside of our tolerance window and fail the test
```

# Stage Directions
- Stage directions are in **bold**.
- Used to cue specific intonation or an action the person being filmed should perform.
- Examples
    - **lol**
    - **drum roll**
    - **clap**

# B-Roll Directions
- B-Roll Directions are in **bold** on their own line.
- Details go in a `> caption` under the **direction** line.
- Used to describe what the viewer should be seeing on screen
    - Get the user to perform an action in a screen recording
    - Suggest a browser recording (automated by the editor)
    - Suggest a motion graphic (automated by the editor)
- Always put directions where they should be executed.
    - Cues to show the viewer something go BEFORE the script that narrates what they are seeing.
- Examples
    - **Graphic** -> A suggested AI generated motion graphic.
    - **Browser Recording** -> A suggested AI generated browser recording.
    - **Video Clip** -> A suggested video clip to embed in the script to support it.
    - **Run Code** -> Instruction for a screen recording in a coding video.

# Other Script Rules
- Do not add tables to the script.
- Do not use acronyms in the script.
    - If the user adds an acronym during edits, that is fine, do not add your own explaination and do not remove it.
- Do not use online research verbatim, it must be re-written.
- Do not quote "research" from random blogs and unknown sources.
- Write years with numbers (2026 not twenty twenty six).

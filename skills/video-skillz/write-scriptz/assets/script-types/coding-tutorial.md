# Context

## Purpose
This script type is for a coding tutorail video

## Hard Rules
- Do not use code examples verbatim, use them to derive fresh examples illustrating the same point
- Always assume I am using the latest version of technologies in the video, do not explain how new versions differ, it's irrelevant
    - This should apply to any topics you research

# Script Guidelines

## Sections
- Each topic within what I am trying to teach should be its own section in the script
- Each coding section should consist of coding implementations, followed by a single run section at the end to demonstrate the point

## Code Blocks
- Coding videos are live coding, while talking
- Every piece of code should be paired with the script
- Code blocks should build on each other as the script progresses
- Split codeblocks based on the script, it's ok if individual blocks would not compile
- Only put a whole function in one codeblock if I am meant to copy paste it because the implementation provides no educational value OR the function is small enough to write during a single part of the script

Example:
Ok, lets build out a simple function that sorts a slice of int's
```go
    func Sort(s []int) {}
```

First we're going to check the length
```go
    func Sort(s []int) {
        len := len(s)
    }
```

## Terminal Commands and Output

- I will ALWAYS run terminal commands myself, either live or in prep
- You can run terminal commands if its relevant to plan the script in general, but DO NOT cite results you get as something I should present
    - Use a [REPLACE: context] tag instead that will illustrate the point when I fill them in
- Do not include phrases like "And here's what we get when I run this command", running the code is the story beat I narrate over, not something I summarize
- Do not use "video actions" like **Run Command** without actual script words explaining what I'm doing

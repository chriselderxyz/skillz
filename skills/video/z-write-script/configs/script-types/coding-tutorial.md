# Purpose
This script type is for a coding tutorial video.

# Code Repo
- If the user has not provided a `code_repo` input variable, ask the user where coding examples should go.
- Each script section should have its own folder in `code_repo` with the section number (ex. `01-basic-benchmarks`).
- Add all code from each section to the section folder.
- Keep the number of files minimal.
- When editing the **publication document**, keep the code repo in sync.

# Hard Rules
- Do not use code examples verbatim, use them to derive fresh examples illustrating the same point.
- Always assume I am using the latest version of technologies in the video, do not explain how new versions differ, it's irrelevant.
    - This should apply to any topics you research.
- The Intro of the video must NOT have coding.

# Code Example Guidelines
- Code examples should be real use cases, not arbitrary demonstrations of specific functionality.

# Script Guidelines

## Sections
- Each topic within what I am trying to teach should be its own section in the script.
- Each coding section should consist of code implementations, followed by a single run section at the end to demonstrate the point.
- A single section may have multiple sets of "code + run", only if they work together to make a single point.
- Do not make multiple sections illustrating the same point, even if the code differs between them.

## Code Blocks
- Coding videos are live coding, while talking.
- Coding blocks should BUILD on each other progressively (ex. a function being slowly filled out).
- It's ok if individual blocks wouldn't compile.

### Copy Pasting Code
- Generally prefer typing code while narrating.
- If a coding block/implementation provides no educational value OR the function is small enough to write during a single script segment, it is ok to plan to copy paste it.
- If a code block is meant to be copy pasted in, add a stage direction.
- Narration when pasting code should actually explain what it is.
    - Bad: "So here's the thing we're testing".
    - Good: "For this example we’re gonna test an Uploader struct that simulates uploading things".

### Script Considerations
- Every piece of code must be paired with the script.
- The script should fully explain the code as it gets typed, including things like narrating function definitions, not just the highlights (ex. "So well start with a Retry function").
- The script must describe what I am doing, not the final result (bad: "Annnd here's our work channel" | good: "And we'll put a work channel in here").
- Split codeblocks based on explanation boundaries, not clean syntax.
    - Two pieces of logic that are explained separately should be in different blocks.
- Do not summarize a large code block unless the intent is to paste the whole block and explain it.
- Only put a whole function in one codeblock if I am meant to copy paste it.

### Examples

#### Bad Example: Summarizing a large change is confusing for the viewer
Fails twice, works on the third try.
```go
func TestRetry(t *testing.T) {
	calls := 0
	err := Retry(context.Background(), 3, time.Second, func() error {
		calls++
		if calls < 3 {
			return errors.New("boom")
		}
		return nil
	})
}
```

#### Good Example: Fully explaining logic as typing happens

Ok, so well start with a simple test for our Retry function
```go
func TestRetry(t *testing.T) {}
```

We'll make a call count variable
Then call the Retry function 
```go
func TestRetry(t *testing.T) {
    calls := 0
    err := Retry(context.Background(), 3, time.Second, func() error {})
}
```

And the function being retried will fail for 2 calls before succeeding
```go
func TestRetry(t *testing.T) {
    calls := 0
    err := Retry(context.Background(), 3, time.Second, func() error {
		calls++
		if calls < 3 {
			return errors.New("boom")
		}
		return nil
	})
}
```

#### Good Example

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
## Code Example Flow
- It is best for coding examples to build on each other.
- Only introduce fully new examples when the previous section cannot be easily repurposed.
- Arrange sections so code examples flow together more easily, while still considering actual video flow.

## Terminal Commands and Output
- I will ALWAYS run terminal commands myself, either live or in prep.
- You can run terminal commands if its relevant to plan the script in general, but DO NOT cite results you get as something I should present.
    - Use a [REPLACE: context] tag instead that will illustrate the point when I fill them in.
- Do not include phrases like "And here's what we get when I run this command", running the code is the story beat I narrate over, not something I summarize.
- Do not use "video actions" like **Run Command** without actual script words explaining what I'm doing.
- Include `> bash command` when relevant.

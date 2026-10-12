# Get Screenshot
- Run `scripts/inspect/screenshot.py` to get a SINGLE screenshot of a **source** to preview grading for.
- `edit/grading-previews/original.png` is that one frame.
- `screenshot.py` is the only writer of `original.png`. Do not manually extract screenshots.
```bash
uv run --no-project scripts/inspect/screenshot.py <source> -o edit/grading-previews/original.png
```

# Make Previews
- Pass `edit/grading-previews/original.png` to `grade.py`.
- `grade.py` is the only writer of a graded preview.
- Each graded preview is that same still.
- ONE frame/screenshot per preview

## Named Preset
Use `--grading-style`.
```bash
uv run --no-project scripts/grading/grade.py edit/grading-previews/original.png \
  -o edit/grading-previews/<name>.png \
  --grading-style <grading-style-name>
```

## auto
Use `--json` with the `grading_style` object.

```bash
uv run --no-project scripts/grading/grade.py edit/grading-previews/original.png \
  -o edit/grading-previews/<name>.png \
  --json '{"eq":{"contrast":1.05,"saturation":0.98}}'
```

# Get Screenshot
- Screenshot the **source** to `edit/grading-previews/original.png`.
- `screenshot.py` is the only writer of `original.png`.
```bash
uv run --no-project scripts/inspect/screenshot.py <source> -o edit/grading-previews/original.png
```

# Make Previews
- Grade `edit/grading-previews/original.png` into one preview per grading style.
- `grade.py` is the only writer of a graded preview.

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

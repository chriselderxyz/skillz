# Get Screenshot
- Run `scripts/inspect/screenshot.py` to get a screenshot of a **clip** to preview grading for
```bash
uv run --no-project scripts/inspect/screenshot.py <clip> -o edit/grading-previews/original.png
```

# Preview
## Named Preset
Use `--grading-style`
```bash
uv run --no-project scripts/grading/grade.py edit/grading-previews/original.png \
  -o edit/grading-previews/<name>.png \
  --grading-style <grading-style-name>
```

## auto
Use `--json` with the `grading_style` object

```bash
uv run --no-project scripts/grading/grade.py edit/grading-previews/original.png \
  -o edit/grading-previews/<name>.png \
  --json '{"eq":{"contrast":1.05,"saturation":0.98}}'
```

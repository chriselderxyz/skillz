# Phase 1: Record

## Action 1. Run the Recorder
- Pass `--zoom` with the page zoom if it was given to you.
- On `create`, run the script with no `--name`.

```bash
uv run --no-project scripts/production/record_browser.py --zoom <page-zoom>
```

- On `edit`, pass `--name` once for each **source** named in the prompt.

```bash
uv run --no-project scripts/production/record_browser.py --zoom <page-zoom> --name <source-name>
```

## Action 2. Probe
- `ffprobe` each file the script recorded.
- Write `audio`, `duration`, `resolution`, and `fps` on `sources.<source-name>` in `edit/edit.json`.

# Phase 2: Respond

- Return each **source** you recorded and its `path`.

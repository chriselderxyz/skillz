# Global Context

## References
- Read `references/shared-context/edit-json.md`.

## Mode
- `create` records every browser recording **source** that has no `path`.
- `edit` re-records each **source** named in the prompt.

# Phase 1: Record

## Action 1. Run the Recorder
- The script writes `path` on each recorded **source**.
- On `create`, run the script with no `--name`.
- Pass `--zoom` with the page zoom if it was given to you.

```bash
uv run --no-project scripts/production/record_browser.py --zoom <page-zoom>
```

- On `edit`, pass `--name` once for each named **source**.

```bash
uv run --no-project scripts/production/record_browser.py --zoom <page-zoom> --name <source-name>
```

## Action 2. Probe
- `ffprobe` each file the script recorded.
- Write `audio`, `duration`, `resolution`, and `fps` on that **source**.

# Phase 2: Respond

## Action 1
- Return each **source** you recorded and its `path`.

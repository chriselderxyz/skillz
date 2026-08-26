# Create The `.srt`
- Run `scripts/production/build_srt.py` against the top-level cut list + transcripts to create the sidecar `.srt`

```bash
uv run --no-project <skill_dir>/scripts/production/build_srt.py -o edit/edit.srt
```

# Verify
- Read the `.srt` end to end and fix mangled terms
- If you have a question or any remaining issues, flag to the user at the gate

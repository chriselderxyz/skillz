# Context

Read `<skill_dir>/references/shared-context/concepts.md`

# Select Segments to Sync
- Check for segments that have multiple clips
- Only run sync for those

# Pick the Audio Reference Clip
- Pick one clip as the `audio_reference_clip` for each segment (other clips are aligned onto it)
- Confirm the candidate has an audio stream (`ffprobe`) before picking it
- Walk this list in order and take the first clip that has one
  1. `<n>-audio` if it exists
  2. else `<n>-screen` if it exists
  3. else `<n>-head`
- If no audio exists, skip this segment

# Sync Clips
Run `sync_pair.py` for each segment you selected 
```bash
uv run --no-project <skill_dir>/scripts/sync/sync_pair.py <audio_reference_clip> <other-clip> [<other-clip> ...] -o edit/<n>/sync.json
```

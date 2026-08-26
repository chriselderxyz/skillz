# Context

Read `references/shared-context/concepts.md`

# Phase 1: Select Segments to Sync
- Check for **segments** that have multiple **clips**
- Only run sync for those

# Phase 2: Pick the Audio Reference Clip
- Pick one **clip** as the `audio_reference_clip` for each **segment** (other **clips** are aligned onto it)
- Confirm the candidate has an audio stream (`ffprobe`) before picking it
- Select the **audio reference clip** with the following **clip type** priority
  1. `audio`
  2. `screen`
  3. `head`
  4. `graphic`
  5. `voiceover`
  6. Any other **B-Roll**
- If no audio exists, skip this **segment**

# Phase 3: Sync Clips
Run `sync_pair.py` for each **segment** you selected 
```bash
uv run --no-project scripts/sync/sync_pair.py <audio_reference_clip> <other-clip> [<other-clip> ...] -o edit/<n>/sync.json
```

# Phase 4: Response
Respond with the name of the **audio reference clip** for each source

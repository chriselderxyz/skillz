# Create Video Type
- Ask for a name and description of the video style they want
- Use the description to build a new video-type json file at `assets/video-types/<name>.json`
- Ask clarifying questions if necessary
- Present the video settings for approval before moving on

# Video Type Expected Properties

```json
{
    // landscape = 16:9 | portrait = 9:16
    "orientation": "landscape",

    // HD | 4K — final ffmpeg output pixel size only (with orientation)
    // landscape HD 1920x1080, 4K 3840x2160
    // portrait HD 1080x1920, 4K 2160x3840
    "resolution": "HD",

    // Desired frame rate
    "fps": 30,

    // Target loudness for normalization
    // Missing - no normalization
    "target_lufs": -14,

    // ms to pad cut edges with
    // <50 is not advised due to transcription timing drift
    "cut_padding_ms": 100,

    // ms to pad cut edges that switch beats or speakers
    // Leaves more breathing room than cut_padding_ms
    "beat_gap_ms": 500,

    // Silent sections longer than this are cut
    // cut_padding_ms applies
    "silence_cut_threshold_ms": 400
}
```

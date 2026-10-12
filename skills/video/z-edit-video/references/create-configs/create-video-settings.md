# Video Settings Expected Properties

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
    "target_lufs": -14
}
```

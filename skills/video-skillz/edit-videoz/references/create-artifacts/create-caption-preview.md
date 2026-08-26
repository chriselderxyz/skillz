# Create Caption Preview
- Screenshot the first `head` clip in `<src>` (lowest segment number)

```bash
uv run --no-project <skill_dir>/scripts/inspect/screenshot.py <src>/<n>-head.<ext> -o edit/caption-style/screenshot.png
```

- Overlay example captions on that still

```bash
uv run --no-project <skill_dir>/scripts/inspect/caption_style_preview.py \
  edit/caption-style/screenshot.png \
  --style <skill_dir>/assets/caption-styles/<name>.json \
  -o edit/caption-style
```

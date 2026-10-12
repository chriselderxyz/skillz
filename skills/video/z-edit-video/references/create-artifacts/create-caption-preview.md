# Create Caption Preview
- Screenshot the first `head` **source** in `<src>` (lowest **source group** number).

```bash
uv run --no-project scripts/inspect/screenshot.py <src>/<n>-head.<ext> -o edit/caption-style/screenshot.png
```

- Overlay example captions on that still.

```bash
uv run --no-project scripts/inspect/caption_style_preview.py \
  edit/caption-style/screenshot.png \
  --style configs/caption-styles/<name>.json \
  -o edit/caption-style
```

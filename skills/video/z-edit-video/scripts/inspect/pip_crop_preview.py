"""Preview a source-pixel crop as a PNG still.

Crops a screenshot with explicit x, y, w, h coordinates and writes a still
the agent and user can judge. Used for both full-frame and PIP crops.

Usage:
    python scripts/inspect/pip_crop_preview.py edit/1/head-frame.png \\
      --crop 420,80,1080,1080 -o edit/1/1-head-pip-crop.png
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

# ==================================================
# Preview crop — main
# ==================================================


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Preview a source-pixel crop as a still"
    )
    ap.add_argument("image", type=Path, help="Head-frame PNG from screenshot.py")
    ap.add_argument(
        "--crop",
        type=str,
        required=True,
        help="Crop as x,y,w,h in source pixels",
    )
    ap.add_argument(
        "-o",
        "--output",
        type=Path,
        required=True,
        help="Output PNG path (ex. edit/<n>/<source>-pip-crop.png)",
    )
    ap.add_argument(
        "--size",
        type=int,
        default=512,
        help="Long-edge length of the preview in pixels (default 512)",
    )
    args = ap.parse_args()

    if not args.image.exists():
        sys.exit(f"image not found: {args.image}")

    parts = [p.strip() for p in args.crop.split(",")]
    if len(parts) != 4:
        sys.exit("--crop must be x,y,w,h")
    try:
        cx, cy, cw, ch = (int(p) for p in parts)
    except ValueError:
        sys.exit("--crop values must be integers")
    if cw <= 0 or ch <= 0:
        sys.exit("--crop w and h must be positive")

    long_edge = max(2, int(args.size) // 2 * 2)
    if cw >= ch:
        out_w = long_edge
        out_h = max(2, int(round(long_edge * ch / cw)) // 2 * 2)
    else:
        out_h = long_edge
        out_w = max(2, int(round(long_edge * cw / ch)) // 2 * 2)
    vf = (
        f"crop={cw}:{ch}:{cx}:{cy},"
        f"scale={out_w}:{out_h}:force_original_aspect_ratio=increase,"
        f"crop={out_w}:{out_h}"
    )
    out = args.output
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(args.image),
        "-frames:v",
        "1",
        "-vf",
        vf,
        str(out),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    print(f"crop preview → {out} (crop={cx},{cy},{cw},{ch})")


if __name__ == "__main__":
    main()

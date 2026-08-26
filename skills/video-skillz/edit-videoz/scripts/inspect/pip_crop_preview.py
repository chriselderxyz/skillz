"""Preview a PIP face crop as a PNG still.

Grabs a frame from the head clip, applies `pip.crop`, and writes a still
the agent and user can judge.

Usage:
    python scripts/inspect/pip_crop_preview.py <head.mp4> \\
      --crop 420,80,1080,1080 -o edit/1/pip-crop.png
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

#==================================================
# Preview PIP crop — main
#==================================================

def main() -> None:
    ap = argparse.ArgumentParser(description="Preview a PIP face crop as a still")
    ap.add_argument("video", type=Path, help="Head (inset) clip")
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
        help="Output PNG path (ex. edit/<n>/pip-crop.png)",
    )
    ap.add_argument(
        "--time",
        type=float,
        default=None,
        help="Frame time in seconds (default: midpoint)",
    )
    ap.add_argument(
        "--size",
        type=int,
        default=512,
        help="Long-edge length of the preview in pixels (default 512)",
    )
    args = ap.parse_args()

    if not args.video.exists():
        sys.exit(f"video not found: {args.video}")

    parts = [p.strip() for p in args.crop.split(",")]
    if len(parts) != 4:
        sys.exit("--crop must be x,y,w,h")
    try:
        cx, cy, cw, ch = (int(p) for p in parts)
    except ValueError:
        sys.exit("--crop values must be integers")
    if cw <= 0 or ch <= 0:
        sys.exit("--crop w and h must be positive")

    t = args.time
    if t is None:
        probe = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(args.video),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        duration = float(probe.stdout.strip() or "0")
        t = max(0.0, duration / 2.0)

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
        "ffmpeg", "-y",
        "-ss", f"{t:.3f}",
        "-i", str(args.video),
        "-frames:v", "1",
        "-vf", vf,
        str(out),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    print(f"pip crop preview → {out} (t={t:.3f}s crop={cx},{cy},{cw},{ch})")


if __name__ == "__main__":
    main()

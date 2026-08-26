"""Grab a single still frame from a video.

Default time is the midpoint. Pass `--time` for an explicit second.

Usage:
    python scripts/inspect/screenshot.py <video> -o edit/grading-previews/original.png
    python scripts/inspect/screenshot.py <video> --time 12.5 -o edit/1/head-frame.png
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser(description="Extract one still frame from a video")
    ap.add_argument("video", type=Path, help="Input video")
    ap.add_argument("-o", "--output", type=Path, required=True, help="Output image path")
    ap.add_argument(
        "--time",
        type=float,
        default=None,
        help="Frame time in seconds (default: midpoint)",
    )
    args = ap.parse_args()

    video = args.video
    if not video.exists():
        sys.exit(f"video not found: {video}")

    probe = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(video),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    duration = float(probe.stdout.strip() or "0")

    if args.time is None:
        t = max(0.0, duration / 2.0)
    else:
        if args.time < 0:
            sys.exit("--time must be >= 0")
        if duration > 0 and args.time > duration:
            sys.exit(f"--time {args.time} past end of clip ({duration:.3f}s)")
        t = args.time

    out = args.output
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y",
        "-ss", f"{t:.3f}",
        "-i", str(video),
        "-frames:v", "1",
        "-q:v", "2",
        str(out),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    print(f"screenshot → {out} (t={t:.3f}s)")


if __name__ == "__main__":
    main()

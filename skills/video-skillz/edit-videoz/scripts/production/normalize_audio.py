"""Two-pass loudness normalize a finished video (audio only; video stream-copied).

Uses ffmpeg `loudnorm`. Peak (-1 dBTP) and loudness range (11) stay fixed;
`--target-lufs` is the integrated target from the video type (commonly -14).

Usage:
    python scripts/production/normalize_audio.py <video> -o <out> --target-lufs -14
    python scripts/production/normalize_audio.py edit/edit.mp4 -o edit/edit.mp4 --target-lufs -14
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

#==================================================
# Loudnorm constants
#==================================================

LOUDNORM_TP = -1.0
LOUDNORM_LRA = 11.0

#==================================================
# Main
#==================================================

def main() -> None:
    ap = argparse.ArgumentParser(
        description="Loudness-normalize a video (audio only, video copied)"
    )
    ap.add_argument("video", type=Path, help="Input video")
    ap.add_argument("-o", "--output", type=Path, required=True, help="Output video path")
    ap.add_argument(
        "--target-lufs",
        type=float,
        required=True,
        help="Integrated loudness target (video-type target_lufs, typically -14)",
    )
    args = ap.parse_args()

    src = args.video.resolve()
    if not src.exists():
        sys.exit(f"video not found: {src}")

    out_path = args.output.resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    print(
        f"loudness normalization → {args.target_lufs} LUFS "
        f"/ -1 dBTP / LRA 11"
    )

    if src == out_path:
        tmp = out_path.with_suffix(".prenorm.mp4")
        apply_loudnorm_two_pass(src, tmp, target_i=args.target_lufs)
        tmp.replace(out_path)
    else:
        apply_loudnorm_two_pass(src, out_path, target_i=args.target_lufs)

    size_mb = out_path.stat().st_size / (1024 * 1024)
    print(f"done: {out_path} ({size_mb:.1f} MB)")

#==================================================
# ffmpeg loudnorm
#==================================================

def measure_loudness(video_path: Path, target_i: float) -> dict[str, str] | None:
    """Run ffmpeg loudnorm first pass and parse the JSON measurement."""
    filter_str = (
        f"loudnorm=I={target_i}:TP={LOUDNORM_TP}:LRA={LOUDNORM_LRA}:print_format=json"
    )
    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-nostats",
        "-i",
        str(video_path),
        "-af",
        filter_str,
        "-vn",
        "-f",
        "null",
        "-",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    stderr = proc.stderr

    start = stderr.rfind("{")
    end = stderr.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        data = json.loads(stderr[start : end + 1])
    except json.JSONDecodeError:
        return None
    needed = {"input_i", "input_tp", "input_lra", "input_thresh", "target_offset"}
    if not needed.issubset(data.keys()):
        return None
    return data


def apply_loudnorm_two_pass(
    input_path: Path,
    output_path: Path,
    target_i: float,
    fast: bool = False,
) -> None:
    """Normalize to target_i LUFS; video stream-copied, audio re-encoded."""
    if fast:
        filter_str = f"loudnorm=I={target_i}:TP={LOUDNORM_TP}:LRA={LOUDNORM_LRA}"
        cmd = [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-nostats",
            "-i",
            str(input_path),
            "-c:v",
            "copy",
            "-af",
            filter_str,
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-ar",
            "48000",
            "-movflags",
            "+faststart",
            str(output_path),
        ]
        print(f"  loudnorm (1-pass fallback) → {output_path.name}")
        subprocess.run(
            cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE
        )
        return

    print(f"  loudnorm pass 1: measuring {input_path.name}")
    measurement = measure_loudness(input_path, target_i=target_i)
    if measurement is None:
        print("  loudnorm measurement failed — falling back to 1-pass")
        apply_loudnorm_two_pass(
            input_path, output_path, target_i=target_i, fast=True
        )
        return

    print(
        f"    measured: I={measurement['input_i']} LUFS  "
        f"TP={measurement['input_tp']}  LRA={measurement['input_lra']}"
    )

    filter_str = (
        f"loudnorm=I={target_i}:TP={LOUDNORM_TP}:LRA={LOUDNORM_LRA}"
        f":measured_I={measurement['input_i']}"
        f":measured_TP={measurement['input_tp']}"
        f":measured_LRA={measurement['input_lra']}"
        f":measured_thresh={measurement['input_thresh']}"
        f":offset={measurement['target_offset']}"
        f":linear=true"
    )
    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-nostats",
        "-i",
        str(input_path),
        "-c:v",
        "copy",
        "-af",
        filter_str,
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-ar",
        "48000",
        "-movflags",
        "+faststart",
        str(output_path),
    ]
    print(f"  loudnorm pass 2: normalizing → {output_path.name}")
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


if __name__ == "__main__":
    main()

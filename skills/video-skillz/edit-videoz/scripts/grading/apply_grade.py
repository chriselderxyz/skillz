"""Apply a color-grade ffmpeg filter string to a video or still.

Importable helper used by `grade.py`.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}


#==================================================
# Apply grade
#==================================================

def apply_grade(input_path: Path, output_path: Path, filter_string: str) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    is_image = output_path.suffix.lower() in IMAGE_SUFFIXES

    if not filter_string:
        if is_image and input_path.suffix.lower() in IMAGE_SUFFIXES:
            cmd = ["ffmpeg", "-y", "-i", str(input_path), str(output_path)]
        else:
            cmd = [
                "ffmpeg", "-y", "-i", str(input_path),
                "-c", "copy", str(output_path),
            ]
    elif is_image:
        cmd = [
            "ffmpeg", "-y", "-i", str(input_path),
            "-vf", filter_string,
            "-frames:v", "1",
            str(output_path),
        ]
    else:
        cmd = [
            "ffmpeg", "-y", "-i", str(input_path),
            "-vf", filter_string,
            "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-pix_fmt", "yuv420p",
            "-c:a", "copy",
            "-movflags", "+faststart",
            str(output_path),
        ]
    subprocess.run(cmd, check=True)

"""Preview a caption style on a still.

Overlays sample cue text with the burn-in script. When word highlighting is
on, the middle word uses the highlight color. When the still is 16:9, also
center-crops to 9:16 and overlays the same cue on that crop.

Usage:
    python scripts/inspect/caption_style_preview.py edit/caption-style/screenshot.png \\
      --style configs/caption-styles/<name>.json \\
      -o edit/caption-style
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

SAMPLE_TEXT = "This is an example caption to check size and placement on the frame"

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "production"))

from srt_timeline import write_ass  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description="Burn a caption-style sample onto a still")
    ap.add_argument("image", type=Path, help="Screenshot PNG")
    ap.add_argument(
        "--style",
        type=Path,
        required=True,
        help="Caption style JSON",
    )
    ap.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        required=True,
        help="Directory for preview.png and optional 9:16 files",
    )
    args = ap.parse_args()

    image = args.image
    if not image.is_file():
        sys.exit(f"image not found: {image}")
    if not args.style.is_file():
        sys.exit(f"style not found: {args.style}")

    style = json.loads(args.style.read_text())
    if not isinstance(style, dict):
        sys.exit(f"{args.style} must be a JSON object")

    probe = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height",
            "-of",
            "csv=p=0",
            str(image),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    dims = probe.stdout.strip().split(",")
    if len(dims) != 2:
        sys.exit(f"could not read width/height from {image}")
    width, height = int(dims[0]), int(dims[1])
    if width <= 0 or height <= 0:
        sys.exit(f"invalid frame size {width}x{height}")

    caption_case = str(style.get("case", "upper"))
    chars_per_line = int(style.get("chars_per_line", 42))
    num_lines = int(style.get("num_lines", 2))
    word_highlight = style.get("word_highlight", False)

    sample = SAMPLE_TEXT
    if caption_case == "upper":
        sample = sample.upper()
    elif caption_case == "lower":
        sample = sample.lower()
    elif caption_case == "title":
        sample = sample.title()

    words = sample.split()
    lines: list[str] = []
    current = ""
    for word in words:
        trial = word if not current else f"{current} {word}"
        if len(trial) <= chars_per_line:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    lines = lines[: max(1, num_lines)]

    cue_lines = [
        [{"text": word, "start": 0.0, "end": 5.0} for word in line.split()]
        for line in lines
    ]
    cues = [{"start": 0.0, "end": 5.0, "lines": cue_lines}]
    flat_count = sum(len(line) for line in cue_lines)
    highlight_word = (flat_count // 2) if word_highlight else None

    out_dir = args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    jobs = [(image, out_dir / "preview.png", width, height)]

    is_16x9 = abs((width / height) - (16 / 9)) < 0.08
    if is_16x9:
        crop_w = max(2, int(height * 9 / 16) // 2 * 2)
        crop_h = max(2, height // 2 * 2)
        crop_x = max(0, (width - crop_w) // 2)
        crop_path = out_dir / "screenshot-9x16.png"
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(image),
                "-vf",
                f"crop={crop_w}:{crop_h}:{crop_x}:0",
                "-frames:v",
                "1",
                str(crop_path),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        print(f"9:16 crop → {crop_path}")
        jobs.append((crop_path, out_dir / "preview-9x16.png", crop_w, crop_h))

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".ass", delete=False, encoding="utf-8"
    ) as tmp:
        ass_path = Path(tmp.name)

    try:
        for src, dest, play_w, play_h in jobs:
            write_ass(
                cues,
                ass_path,
                style,
                (play_w, play_h),
                highlight_word=highlight_word,
            )
            subs_abs = str(ass_path.resolve()).replace(":", r"\:").replace("'", r"\'")
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-i",
                    str(src),
                    "-vf",
                    f"subtitles='{subs_abs}'",
                    "-frames:v",
                    "1",
                    str(dest),
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
            print(f"caption preview → {dest}")
    finally:
        ass_path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()

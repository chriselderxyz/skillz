"""Preview a caption style on a still.

Overlays sample cue text with the style's ASS force_style. When the still
is 16:9, also center-crops to 9:16 and overlays the same cue on that crop.

Usage:
    python scripts/inspect/caption_style_preview.py edit/caption-style/screenshot.png \\
      --style assets/caption-styles/<name>.json \\
      -o edit/caption-style
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

SKILL_STYLE_KEYS = {"case", "chars_per_line", "num_lines"}
SAMPLE_TEXT = "This is an example caption to check size and placement on the frame"


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Burn a caption-style sample onto a still"
    )
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
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "csv=p=0",
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

    # Map caption-style JSON onto ffmpeg subtitles force_style (ASS).
    # Skip layout keys that are not ASS properties.
    force_style = (
        "FontName=Helvetica,FontSize=18,Bold=1,"
        "PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BackColour=&H00000000,"
        "BorderStyle=1,Outline=2,Shadow=0,"
        "Alignment=2,MarginV=90"
    )
    parts: list[str] = []
    bool_style_keys = {"bold", "italic", "underline", "strike_out"}
    for key, value in style.items():
        if key in SKILL_STYLE_KEYS:
            continue

        # snake_case → ASS PascalCase (font_name → FontName, primary_color → PrimaryColour)
        ass_key = "".join(
            "Colour" if p == "color" else p.capitalize()
            for p in key.split("_")
        )

        # ASS toggles are -1 on / 0 off
        if key in bool_style_keys:
            if not isinstance(value, bool):
                sys.exit(
                    f"caption style {key} must be a boolean, got: {value!r}"
                )
            value = -1 if value else 0
        elif (
            isinstance(value, str)
            and key.endswith("_color")
            and not value.startswith("&H")
        ):
            hex_rgb = value.removeprefix("#")
            if len(hex_rgb) != 6:
                sys.exit(
                    f"caption style {key} must be RRGGBB or &HAABBGGRR, "
                    f"got: {value!r}"
                )
            value = f"&H00{hex_rgb[4:6]}{hex_rgb[2:4]}{hex_rgb[0:2]}".upper()
        parts.append(f"{ass_key}={value}")

    if parts:
        force_style = ",".join(parts)

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
    cue = "\n".join(lines)

    srt_text = (
        "1\n"
        "00:00:00,000 --> 00:00:05,000\n"
        f"{cue}\n"
    )

    out_dir = args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".srt", delete=False, encoding="utf-8"
    ) as tmp:
        tmp.write(srt_text)
        srt_path = Path(tmp.name)

    jobs = [(image, out_dir / "preview.png")]

    is_16x9 = abs((width / height) - (16 / 9)) < 0.08
    if is_16x9:
        crop_w = max(2, int(height * 9 / 16) // 2 * 2)
        crop_h = max(2, height // 2 * 2)
        crop_x = max(0, (width - crop_w) // 2)
        crop_path = out_dir / "screenshot-9x16.png"
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", str(image),
                "-vf", f"crop={crop_w}:{crop_h}:{crop_x}:0",
                "-frames:v", "1",
                str(crop_path),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        print(f"9:16 crop → {crop_path}")
        jobs.append((crop_path, out_dir / "preview-9x16.png"))

    subs_abs = str(srt_path.resolve()).replace(":", r"\:").replace("'", r"\'")
    vf = f"subtitles='{subs_abs}':force_style='{force_style}'"
    for src, dest in jobs:
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", str(src),
                "-vf", vf,
                "-frames:v", "1",
                str(dest),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        print(f"caption preview → {dest}")

    srt_path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()

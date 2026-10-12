"""Build a sidecar SubRip (.srt) from `edit/edit.json` and transcripts.

Remaps the audio-source transcript onto the edit clock using wrap settings
from `edit.json srt_style` (`chars_per_line`, `num_lines`). Sentence case.

Does not load `configs/srt-styles/` — the agent copies the srt-style JSON into
`srt_style` on `edit/edit.json` before calling this script.

Burn-in is separate: `render.py` writes `edit/burn-captions.ass` from transcripts + `caption_style`.

Transcripts are read from `edit/source-transcriptions`.

Usage:
    python scripts/production/build_srt.py -o edit/edit.srt
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from plan_model import compile_timeline
from srt_timeline import build_timeline_srt


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Build an edit-clock SRT from edit/edit.json and per-source transcripts"
    )
    ap.add_argument(
        "-o",
        "--output",
        type=Path,
        required=True,
        help="Output .srt path",
    )
    args = ap.parse_args()

    plan_path = Path("edit").resolve() / "edit.json"
    timeline = compile_timeline(plan_path)
    edit_dir = plan_path.parent
    transcripts_dir = edit_dir / "source-transcriptions"
    out_path = args.output.resolve()

    # ==================================================
    # SRT style from edit.json
    # ==================================================

    srt_style = timeline.get("srt_style")
    if srt_style is None:
        sys.exit(
            "edit.json srt_style is required (copy the srt-style JSON into edit.json)"
        )
    if not isinstance(srt_style, dict):
        sys.exit("edit.json srt_style must be an object")

    chars_per_line = int(srt_style.get("chars_per_line", 42))
    num_lines = int(srt_style.get("num_lines", 2))
    print(
        f"edit.json srt_style → chars_per_line={chars_per_line} num_lines={num_lines}"
    )

    n = build_timeline_srt(
        timeline,
        transcripts_dir,
        out_path,
        edit_dir=edit_dir,
        chars_per_line=chars_per_line,
        num_lines=num_lines,
        caption_case="normal",
    )
    print(f"master SRT → {out_path} ({n} cues)")


if __name__ == "__main__":
    main()

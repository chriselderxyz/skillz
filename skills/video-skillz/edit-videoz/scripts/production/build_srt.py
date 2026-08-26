"""Build a sidecar SubRip (.srt) from an EDL + transcripts.

Remaps the audio-clip transcript onto the edit clock using wrap settings
from `edl.srt_style` (`chars_per_line`, `num_lines`). Sentence case.

Does not load `assets/srt-styles/` — the agent copies the srt-style JSON into
`edl.srt_style` on the top-level `edit/edl.json` before calling this script.

Burn-in is separate: `render.py` builds cues from transcripts + `caption_style`
(top-level, with per-segment keys merged on).

Transcripts are read from `<edit>/clip_transcriptions` next to the EDL.

Usage:
    python scripts/production/build_srt.py -o edit/edit.srt
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from srt_timeline import build_timeline_srt


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Build an edit-clock SRT from an EDL and per-source transcripts"
    )
    ap.add_argument(
        "-o",
        "--output",
        type=Path,
        required=True,
        help="Output .srt path",
    )
    args = ap.parse_args()

    edl_path = Path("edit").resolve() / "edl.json"
    if not edl_path.exists():
        sys.exit(f"edl not found: {edl_path}")

    edl = json.loads(edl_path.read_text())
    edit_dir = edl_path.parent
    transcripts_dir = edit_dir / "clip_transcriptions"
    out_path = args.output.resolve()

    #==================================================
    # SRT style from EDL
    #==================================================

    srt_style = edl.get("srt_style")
    if srt_style is None:
        sys.exit(
            "edl.srt_style is required (copy the srt-style JSON into the EDL)"
        )
    if not isinstance(srt_style, dict):
        sys.exit("edl.srt_style must be an object")

    chars_per_line = int(srt_style.get("chars_per_line", 42))
    num_lines = int(srt_style.get("num_lines", 2))
    print(
        f"edl.srt_style → chars_per_line={chars_per_line} "
        f"num_lines={num_lines}"
    )

    n = build_timeline_srt(
        edl,
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

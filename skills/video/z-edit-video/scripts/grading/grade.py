"""Apply a color grade to a video or still via ffmpeg.

Styles live in `configs/grading-styles/<name>.json`, or pass a JSON object
string with `--json` for on-the-fly grades (Plan-phase auto).

Filter-string conversion: `json_to_grade_vf.py`.
Apply step: `apply_grade.py`.

Usage:
    python scripts/grading/grade.py <in> -o <out> --grading-style subtle
    python scripts/grading/grade.py <in> -o <out> --grading-style none
    python scripts/grading/grade.py <in> -o <out> --json '{"eq":{"contrast":1.05}}'
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from apply_grade import apply_grade
from json_to_grade_vf import json_to_grade_vf_string

STYLES_DIR = (
    Path(__file__).resolve().parent.parent.parent / "configs" / "grading-styles"
)

# ==================================================
# Apply grading — main
# ==================================================


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Apply a color grade via ffmpeg filter chain"
    )
    ap.add_argument("input", type=Path, help="Input video or still")
    ap.add_argument("-o", "--output", type=Path, required=True, help="Output path")
    ap.add_argument(
        "--grading-style",
        type=str,
        default=None,
        help=(
            "Grading-style name under configs/grading-styles/, or 'none' for no grade."
        ),
    )
    ap.add_argument(
        "--json",
        type=str,
        default=None,
        dest="grading_json",
        help=(
            "Inline grading_style JSON object string "
            '(ex. \'{"eq":{"contrast":1.05}}\'). '
            "Empty object {} is no grade. Mutually exclusive with --grading-style."
        ),
    )
    args = ap.parse_args()

    if not args.input.exists():
        sys.exit(f"input not found: {args.input}")

    if args.grading_style is not None and args.grading_json is not None:
        sys.exit("pass either --grading-style or --json, not both")

    if args.grading_json is not None:
        try:
            data = json.loads(args.grading_json)
        except json.JSONDecodeError as e:
            sys.exit(f"invalid --json: {e}")
        if data is not None and not isinstance(data, dict):
            sys.exit("--json must be a JSON object")
        filter_string = json_to_grade_vf_string(data or {})
    elif args.grading_style is None or args.grading_style == "none":
        filter_string = ""
    else:
        path = STYLES_DIR / f"{args.grading_style}.json"
        if not path.exists():
            available = ", ".join(sorted(p.stem for p in STYLES_DIR.glob("*.json")))
            sys.exit(f"unknown style '{args.grading_style}'. Available: {available}")
        filter_string = json_to_grade_vf_string(json.loads(path.read_text()))

    print(f"grading {args.input.name} → {args.output.name}")
    if filter_string:
        print(
            f"  filter: {filter_string[:120]}{'...' if len(filter_string) > 120 else ''}"
        )
    else:
        print("  filter: (none — copy)")

    apply_grade(args.input, args.output, filter_string)
    print(f"done: {args.output}")


if __name__ == "__main__":
    main()

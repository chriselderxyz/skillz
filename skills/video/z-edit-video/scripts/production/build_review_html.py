#!/usr/bin/env python3
"""Compile edit.json into the draft review page.

Reads `edit/edit.json` and `assets/review-draft.html`. Styles, playback, and
timeline zoom stay in the template. This script fills the title, the draft
video, and the timeline cards. Each card carries the same `data-json-path`
the plan page uses, so a review comment can be traced back to that layer.

Usage:
    python scripts/production/build_review_html.py
    python scripts/production/build_review_html.py --file assets/temp.html --video edit/edit-draft.mp4
"""

from __future__ import annotations

import argparse
import html as html_lib
import re
import sys
from pathlib import Path

from plan_model import fmt_tc, load_plan
from srt_timeline import build_caption_cues


#==================================================
# Main
#==================================================


def main() -> None:
    #==============================
    # CLI Argument Inputs
    #==============================
    skill_dir = Path(__file__).resolve().parent.parent.parent

    ap = argparse.ArgumentParser(
        description="Compile edit/edit.json into a draft review page"
    )
    ap.add_argument(
        "--plan",
        type=Path,
        default=Path("edit/edit.json"),
        help="Path to edit.json (default: edit/edit.json)",
    )
    ap.add_argument(
        "--assets",
        type=Path,
        default=skill_dir / "assets" / "review-draft.html",
        help="Review template used for styles and script",
    )
    ap.add_argument(
        "-o",
        "--out-dir",
        type=Path,
        default=Path("edit"),
        help="Directory to write review-<hash>.html into (default: edit)",
    )
    ap.add_argument(
        "--file",
        type=Path,
        default=None,
        help="Write this path instead of review-<hash>.html",
    )
    ap.add_argument(
        "--video",
        default="edit-draft.mp4",
        help="Draft video path written into the page (default: edit-draft.mp4)",
    )
    ap.add_argument(
        "--tolerance",
        type=float,
        default=0.011,
        help="Allowed clock drift in seconds when merging layer cards (default: 0.011)",
    )
    args = ap.parse_args()

    plan_path = args.plan.resolve()
    assets_path = args.assets.resolve()
    if not assets_path.is_file():
        sys.exit(f"review template not found: {assets_path}")
    page = assets_path.read_text()
    if "<!-- review-gutter -->" not in page or "<!-- review-lanes -->" not in page:
        sys.exit(
            f"{assets_path} must contain <!-- review-gutter --> and <!-- review-lanes -->"
        )
    if "<script>" not in page:
        sys.exit(f"{assets_path} must contain the review <script>")

    model = load_plan(plan_path, tolerance=args.tolerance)
    scenes = model["scenes"]
    title = model["title"] or "Draft Review"
    video = html_lib.escape(args.video, quote=True)

    #==================================================
    # Pack layer cards the same way the plan page does
    #==================================================

    packed = []
    max_column = 1
    for scene in scenes:
        cards_by_line: dict[str, list] = {}
        for card in scene["cards"]:
            cards_by_line.setdefault(card["line_id"], []).append(card)

        runs: list[list] = []
        open_runs: list[list] = []
        for line in scene["lines"]:
            available = list(open_runs)
            open_runs = []
            for card in cards_by_line.get(line["id"]) or []:
                match = None
                for run in available:
                    prev = run[-1]
                    same = (
                        prev["type"] == card["type"]
                        and (prev.get("source") or "") == (card.get("source") or "")
                        and prev.get("frame") == card.get("frame")
                        and bool(prev.get("zoom_cut")) == bool(card.get("zoom_cut"))
                    )
                    if (
                        same
                        and prev.get("end") is not None
                        and card.get("start") is not None
                        and abs(prev["end"] - card["start"]) <= args.tolerance
                    ):
                        match = run
                        break
                if match is None:
                    match = [card]
                    runs.append(match)
                else:
                    available.remove(match)
                    match.append(card)
                open_runs.append(match)

        placed: list[tuple[list, int]] = []
        for run in runs:
            row_start = run[0]["row_start"]
            row_end = run[-1]["row_end"]
            taken = set()
            for other, other_col in placed:
                if row_start < other[-1]["row_end"] and other[0]["row_start"] < row_end:
                    taken.add(other_col)
            column = 1
            while column in taken:
                column += 1
            placed.append((run, column))

        for run, column in placed:
            card = dict(run[0])
            card["span"] = [part["line_id"] for part in run]
            card["end"] = run[-1]["end"]
            card["column"] = column
            card["scene_id"] = scene["id"]
            card["scene_name"] = scene["name"]
            packed.append(card)
            if column > max_column:
                max_column = column

    by_column: dict[int, list] = {col: [] for col in range(1, max_column + 1)}
    for card in packed:
        by_column[card["column"]].append(card)
    for column in by_column:
        by_column[column].sort(key=lambda card: card["start"] or 0)

    #==================================================
    # Subtitle cues
    #==================================================

    cues = []
    cue_path = ""
    caption_style = model.get("caption_style")
    srt_style = model.get("srt_style")
    if isinstance(caption_style, dict):
        cue_style = caption_style
        cue_path = "caption_style"
        caption_case = str(caption_style.get("case") or "upper")
    elif isinstance(srt_style, dict):
        cue_style = srt_style
        cue_path = "srt_style"
        caption_case = "normal"
    else:
        cue_style = None
    if cue_style is not None:
        ranges = []
        for scene in scenes:
            for line in scene["lines"]:
                kept = line.get("kept") or {}
                audio_name = kept.get("audio_source")
                if not audio_name:
                    continue
                for cut in kept.get("cuts") or []:
                    if cut.get("start") is None or cut.get("end") is None:
                        continue
                    ranges.append(
                        {
                            "audio_source": audio_name,
                            "start": cut["start"],
                            "end": cut["end"],
                        }
                    )
        cues = build_caption_cues(
            {"ranges": ranges},
            plan_path.parent / "source-transcriptions",
            chars_per_line=int(cue_style.get("chars_per_line", 42)),
            num_lines=int(cue_style.get("num_lines", 2)),
            caption_case=caption_case,
        )

    #==================================================
    # Timeline markup
    #==================================================

    eye = (
        '<button type="button" class="lane-eye" aria-pressed="true" '
        'aria-label="Hide subtitles">'
        '<svg viewBox="0 0 24 24" aria-hidden="true">'
        '<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z" '
        'fill="none" stroke="currentColor" stroke-width="2"></path>'
        '<circle cx="12" cy="12" r="3" fill="none" stroke="currentColor" '
        'stroke-width="2"></circle>'
        '<path class="lane-eye-slash" d="M5 19 19 5" fill="none" '
        'stroke="currentColor" stroke-width="2"></path>'
        "</svg></button>"
    )
    gutter = [
        '    <div class="lane-gutter">',
        '      <div class="lane-gutter-spacer"></div>',
    ]
    if cues:
        gutter.append(
            '      <div class="lane-label" data-layer="subs" title="Subtitles.">'
        )
        gutter.append(f"        {eye}")
        gutter.append('        <span class="lane-role">subs</span>')
        gutter.append("      </div>")
    for column in range(max_column, 0, -1):
        if column == 1:
            role = "back"
            label = "Back layer. Plan column 1."
        elif column == max_column:
            role = "front"
            label = f"Front layer. Plan column {column}."
        else:
            role = ""
            label = f"Plan column {column}."
        role_html = (
            f'\n        <span class="lane-role">{html_lib.escape(role)}</span>'
            if role
            else ""
        )
        gutter.append(
            f'      <div class="lane-label" data-layer="{column}" '
            f'title="{html_lib.escape(label, quote=True)}">'
        )
        gutter.append(f'        <span class="lane-index">{column}</span>{role_html}')
        gutter.append("      </div>")
    gutter.append("    </div>")

    lanes = ['        <div class="lanes">']
    if cues:
        lanes.append('          <div class="lane" data-layer="subs">')
        for index, cue in enumerate(cues, start=1):
            rows = [
                " ".join(word["text"] for word in line)
                for line in cue["lines"]
            ]
            shown = "\n".join(rows)
            flat = " ".join(rows)
            start = fmt_tc(cue["start"])
            end = fmt_tc(cue["end"])
            subtitle_attr = html_lib.escape(shown, quote=True).replace("\n", "&#10;")
            lanes.append(
                f'            <div class="clip" data-type="subtitle" '
                f'data-layer="subs" data-cue="{index}" '
                f'data-edit-start="{start}" data-edit-end="{end}" '
                f'data-subtitle="{subtitle_attr}" '
                f'data-json-path="{cue_path}">'
            )
            lanes.append(
                f'              <p class="clip-name">{html_lib.escape(flat)}</p>'
            )
            lanes.append("            </div>")
        lanes.append("          </div>")
    for column in range(max_column, 0, -1):
        lanes.append(f'          <div class="lane" data-layer="{column}">')
        for card in by_column[column]:
            frame = card.get("frame")
            if card["type"] == "graphic":
                extra = (
                    f' data-graphic-name="{html_lib.escape(card["graphic"], quote=True)}"'
                    f' data-graphic-index="{card["graphic_index"]}"'
                )
            elif card["type"] == "browser":
                extra = (
                    f' data-browser-name="{html_lib.escape(card["browser"], quote=True)}"'
                    f' data-browser-index="{card["browser_index"]}"'
                )
            else:
                extra = ""
            if frame in {"full", "top", "bottom", "pip"}:
                frame_label = frame
            else:
                frame_label = "custom"
            if card.get("zoom_cut"):
                frame_label = f"{frame_label} · zoom"
                extra += ' data-zoom-cut="true"'
            kind = card.get("source_type") or ""
            if not kind:
                if card["type"] == "graphic":
                    kind = "graphic"
                elif card["type"] == "browser":
                    kind = "browser"
                else:
                    source_name = str(card.get("source") or "")
                    kind = (
                        source_name.split("-", 1)[1]
                        if "-" in source_name
                        else source_name
                    )
            name = card.get("source") or card.get("graphic") or card.get("browser") or ""
            start = fmt_tc(card["start"])
            end = fmt_tc(card["end"])
            blurb = str(card.get("description") or "").strip()
            if len(blurb) > 140:
                blurb = blurb[:137].rstrip() + "..."
            tip = " · ".join(
                part
                for part in (
                    card["scene_name"],
                    frame_label,
                    kind,
                    name,
                    f"{start}–{end}",
                    blurb,
                )
                if part
            )
            lanes.append(
                f'            <div class="clip" '
                f'data-type="{html_lib.escape(card["type"], quote=True)}" '
                f'data-layer="{column}" '
                f'data-scene-id="{html_lib.escape(card["scene_id"], quote=True)}" '
                f'data-line-id="{html_lib.escape(card["line_id"], quote=True)}" '
                f'data-line-ids="{html_lib.escape(" ".join(card["span"]), quote=True)}" '
                f'data-source="{html_lib.escape(name, quote=True)}"{extra} '
                f'data-edit-start="{start}" '
                f'data-edit-end="{end}" '
                f'data-json-path="{html_lib.escape(card["path"], quote=True)}" '
                f'title="{html_lib.escape(tip, quote=True)}">'
            )
            lanes.append(
                f'              <p class="clip-meta">{html_lib.escape(frame_label)} · {html_lib.escape(kind)}</p>'
            )
            lanes.append(
                f'              <p class="clip-name">{html_lib.escape(name)}</p>'
            )
            lanes.append("            </div>")
        lanes.append("          </div>")
    lanes.append("        </div>")

    #==================================================
    # Fill the template
    #==================================================

    page = re.sub(
        r"<title>.*?</title>",
        f"<title>{html_lib.escape(title)}</title>",
        page,
        count=1,
        flags=re.DOTALL,
    )
    page = re.sub(
        r'(<h1 class="review-title">).*?(</h1>)',
        lambda match: match.group(1) + html_lib.escape(title) + match.group(2),
        page,
        count=1,
        flags=re.DOTALL,
    )
    page = page.replace("edit-draft.mp4", video)

    for name, block in (("gutter", "\n".join(gutter)), ("lanes", "\n".join(lanes))):
        start = f"<!-- review-{name} -->"
        end = f"<!-- /review-{name} -->"
        start_at = page.find(start)
        end_at = page.find(end)
        if start_at < 0 or end_at < start_at:
            sys.exit(f"review template is missing the {name} markers")
        page = page[:start_at] + start + "\n" + block + "\n    " + end + page[end_at + len(end) :]

    if args.file is not None:
        out_path = args.file.resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        out_dir = args.out_dir.resolve()
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"review-{model['hash']}.html"
        for stale in sorted(out_dir.glob("review-*.html")):
            if stale != out_path:
                stale.unlink()
                print(f"removed stale review → {stale.name}")

    out_path.write_text(page)
    print(f"review → {out_path}")
    print(
        f"  {len(scenes)} scene(s), {len(packed)} card(s), "
        f"{max_column} lane(s), {len(cues)} subtitle cue(s), "
        f"runtime {fmt_tc(model['runtime'])}"
    )


if __name__ == "__main__":
    main()

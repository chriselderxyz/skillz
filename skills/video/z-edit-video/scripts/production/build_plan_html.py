#!/usr/bin/env python3
"""Compile edit.json into a hash-stamped review document.

Reads `edit/edit.json`, validates the edit clock against the audio-source-clock
cuts, rejects any kept_take cut edge that lands inside a spoken word and
outside every silence, and writes the whole `edit/plan-<hash>.html`. The hash
is the first 8 hex digits of the SHA-256 of `edit.json`, so a stale review
document is visible from its file name alone.

Nothing is authored for this document. Everything is read from the file that
already owns it:

  - title, description   `edit/edit.json`
  - issues               `edit/edit.json`
  - format               `edit/edit.json` video_settings
  - source properties      `edit/edit.json` source groups.<n>.sources
  - audio source          `edit/edit.json` source groups
  - sync offsets         `edit/edit.json` source groups.<n>.sync
  - grading previews     `edit/grading-previews/*.png`
  - grading selection    `edit.json` grading_style, matched against the previews
  - crop previews        `edit/<n>/<source>-<frame>-crop.png`
  - caption previews     `edit/caption-style/preview*.png`

Styles and fonts are lifted from `assets/plan.html` so the design stays
in one editable place.

Usage:
    python scripts/production/build_plan_html.py
    python scripts/production/build_plan_html.py --tolerance 0.02
    python scripts/production/build_plan_html.py --cuts-only
"""

from __future__ import annotations

import argparse
import html as html_lib
import json
import re
import sys
from pathlib import Path

from plan_model import fmt_tc, load_plan


# ==================================================
# Escaping and labels
# ==================================================


def esc(value) -> str:
    return html_lib.escape("" if value is None else str(value), quote=True)


def label_from_stem(stem: str) -> str:
    return " ".join(part.capitalize() for part in re.split(r"[-_]", str(stem)) if part)


# ==================================================
# Cut placement
# ==================================================

# Slack on Scribe word edges
WORD_EDGE_TOL_S = 0.02


def cut_placement_errors(scenes: list[dict], edit_dir: Path) -> list[str]:
    """Kept-take cut edges that land inside a spoken word and outside every silence.

    Words come from `edit/source-transcriptions/<audio_source>.json`. Silences
    come from `edit/silences.json`. An audio source with no transcript is skipped.
    """
    silences_path = edit_dir / "silences.json"
    silence_map = (
        json.loads(silences_path.read_text()).get("sources") or {}
        if silences_path.is_file()
        else {}
    )
    words_by_source: dict[str, list[dict]] = {}
    errors: list[str] = []

    for scene in scenes:
        for line in scene["lines"]:
            kept = line["kept"]
            source = kept["audio_source"]
            if source not in words_by_source:
                transcript_path = edit_dir / "source-transcriptions" / f"{source}.json"
                words_by_source[source] = (
                    [
                        w
                        for w in json.loads(transcript_path.read_text()).get("words") or []
                        if w.get("type") == "word"
                        and w.get("start") is not None
                        and w.get("end") is not None
                    ]
                    if transcript_path.is_file()
                    else []
                )
            words = words_by_source[source]
            silences = silence_map.get(source) or []

            for cut in kept["cuts"]:
                for field, t in (
                    ("audio_source_start", cut["start"]),
                    ("audio_source_end", cut["end"]),
                ):
                    if any(s["start"] <= t <= s["end"] for s in silences):
                        continue
                    word = next(
                        (
                            w
                            for w in words
                            if w["start"] + WORD_EDGE_TOL_S < t < w["end"] - WORD_EDGE_TOL_S
                        ),
                        None,
                    )
                    if word is not None:
                        errors.append(
                            f"{cut['path']}.{field}: {fmt_tc(t)} cuts into "
                            f"\"{str(word.get('text') or '').strip()}\" "
                            f"({fmt_tc(word['start'])}-{fmt_tc(word['end'])})"
                        )
    return errors

    # ==================================================
    # Main
    # ==================================================


def main() -> None:
    # ==============================
    # CLI Argument Inputs
    # ==============================
    skill_dir = Path(__file__).resolve().parent.parent.parent

    ap = argparse.ArgumentParser(
        description="Compile edit/edit.json into edit/plan-<hash>.html"
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
        default=skill_dir / "assets" / "plan.html",
        help="Example plan HTML used for styles and script",
    )
    ap.add_argument(
        "-o",
        "--out-dir",
        type=Path,
        default=Path("edit"),
        help="Directory to write plan-<hash>.html into (default: edit)",
    )
    ap.add_argument(
        "--tolerance",
        type=float,
        default=0.011,
        help="Allowed clock drift in seconds (default: 0.011)",
    )
    ap.add_argument(
        "--cuts-only",
        action="store_true",
        help="Check the cut plan before crops are planned, and write nothing",
    )
    args = ap.parse_args()

    plan_path = args.plan.resolve()

    assets_path = args.assets.resolve()
    if not assets_path.is_file():
        sys.exit(f"assets plan not found: {assets_path}")
    assets_raw = assets_path.read_text()
    if '<div class="sheet"' not in assets_raw or "<script>" not in assets_raw:
        sys.exit(
            f"{assets_path} must contain a '<div class=\"sheet\"' body and a "
            "trailing <script> block"
        )
    head_part = assets_raw[: assets_raw.index('<div class="sheet"')].rstrip()
    tail_part = assets_raw[assets_raw.rindex("<script>") :].strip()

    out_dir = args.out_dir.resolve()

    # ==================================================
    # Discover from disk
    # ==================================================

    # ==============================
    # Preview images
    # ==============================
    grading_dir = out_dir / "grading-previews"
    grading_previews: list[Path] = []
    if grading_dir.is_dir():
        found = sorted(grading_dir.glob("*.png"))
        original = [p for p in found if p.stem == "original"]
        grading_previews = original + [p for p in found if p.stem != "original"]

    crop_previews: list[dict] = []
    for crop_png in sorted(out_dir.glob("*/*-crop.png")):
        stem = crop_png.name[: -len("-crop.png")]
        source_name, sep, frame = stem.rpartition("-")
        if not sep or frame not in {"full", "pip", "top", "bottom"}:
            continue
        crop_previews.append(
            {
                "source_group": crop_png.parent.name,
                "source": source_name,
                "frame": frame,
                "path": crop_png,
            }
        )
    active_crop_previews = [p for p in crop_previews if p["frame"] != "pip"]
    pip_previews = [p for p in crop_previews if p["frame"] == "pip"]

    caption_dir = out_dir / "caption-style"
    caption_previews = (
        sorted(caption_dir.glob("preview*.png")) if caption_dir.is_dir() else []
    )

    # ==================================================
    # Pass 1 - Load and validate edit.json
    # ==================================================

    model = load_plan(
        plan_path, tolerance=args.tolerance, check_crops=not args.cuts_only
    )
    placement_errors = cut_placement_errors(model["scenes"], plan_path.parent)
    if placement_errors:
        print(f"{len(placement_errors)} problem(s) in {plan_path}:", file=sys.stderr)
        for message in placement_errors:
            print(f"  {message}", file=sys.stderr)
        sys.exit(1)
    if args.cuts_only:
        print(f"no problems in {plan_path}")
        return
    plan_hash = model["hash"]
    scenes = model["scenes"]
    graphic_count = model["graphic_count"]
    browser_count = model["browser_count"]
    runtime = fmt_tc(model["runtime"])
    issues = model["issues"]
    source_groups = model["source_groups"]
    plan_sources = model["sources"]

    # The selected grade is whichever preview's settings edit.json is now using.
    # Auto options save a sidecar next to the preview, presets live in configs.
    grading_selection = None
    chosen = model.get("grading_style")
    if isinstance(chosen, dict):
        for preview in grading_previews:
            if preview.stem == "original":
                continue
            for candidate in (
                preview.with_suffix(".json"),
                skill_dir / "configs" / "grading-styles" / f"{preview.stem}.json",
            ):
                if not candidate.is_file():
                    continue
                try:
                    if json.loads(candidate.read_text()) == chosen:
                        grading_selection = preview.stem
                except json.JSONDecodeError:
                    pass
            if grading_selection:
                break

    video_settings = model["video_settings"]
    orientation = str(video_settings.get("orientation") or "").strip().lower()
    resolution_name = str(video_settings.get("resolution") or "").strip().upper()

        # ==============================
        # Sources from edit.json
        # ==============================
    source_rows: dict[str, list[dict]] = {}
    grouped_sources: dict[str, list[tuple[str, dict]]] = {}
    for name, source in plan_sources.items():
        if not isinstance(source, dict) or source.get("type") in {"animation", "image", "browser"}:
            continue
        group_number = str(name).split("-", 1)[0]
        grouped_sources.setdefault(group_number, []).append((str(name), source))
    for source_group, named_sources in grouped_sources.items():
        info = source_groups.get(source_group)
        if not isinstance(info, dict):
            info = {}
        reference = info.get("audio_source")
        reference_stem = Path(str(reference)).stem if reference else None
        sync = info.get("sync") if isinstance(info.get("sync"), dict) else {}
        rows = []
        for name, source in named_sources:
            if not isinstance(source, dict):
                source = {}
            source_type = source.get("type")
            if not source_type and "-" in str(name):
                source_type = str(name).split("-", 1)[1]
            fps_raw = source.get("fps")
            if isinstance(fps_raw, (int, float)):
                fps = (
                    f"{fps_raw:.0f}"
                    if abs(fps_raw - round(fps_raw)) < 0.01
                    else f"{fps_raw:.2f}"
                )
            elif fps_raw:
                fps = str(fps_raw)
            else:
                fps = "—"
            offset = sync.get(name)
            if isinstance(offset, (int, float)):
                sync_offset = f"{offset:+.2f}s"
            else:
                sync_offset = "—"
            rows.append(
                {
                    "name": name,
                    "type": label_from_stem(str(source_type))
                    if source_type
                    else "—",
                    "duration": source.get("duration") or "—",
                    "resolution": source.get("resolution") or "—",
                    "fps": fps,
                    "sync_offset": sync_offset,
                    "is_audio_source": str(name) == reference_stem,
                }
            )
        if rows:
            source_rows[str(source_group)] = rows

            # ==================================================
            # Pass 2 - Render
            # ==================================================

    out: list[str] = [f'<div class="sheet" data-plan-hash="{plan_hash}">']

    # ==============================
    # Summary
    # ==============================
    out.append('  <header class="plan-header" data-type="summary">')
    out.append('    <p class="eyebrow">Editing Plan</p>')
    out.append('    <h1 class="plan-title">Summary</h1>')
    if model["description"]:
        out.append(f'    <p class="plan-description">{esc(model["description"])}</p>')

    meta_rows = [("Runtime", runtime)]
    if orientation and resolution_name:
        aspect = "16:9" if orientation == "landscape" else "9:16"
        meta_rows.append(("Format", f"{aspect} · {resolution_name}"))
    fps = video_settings.get("fps")
    if fps:
        meta_rows.append(("Frame Rate", f"{fps}fps"))
    out.append('    <dl class="plan-meta">')
    for label, value in meta_rows:
        out.append(f"      <div><dt>{esc(label)}</dt><dd>{esc(value)}</dd></div>")
    out.append("    </dl>")

    if source_rows:
        out.append('    <div class="source-groups">')
        for source_group in sorted(
            source_rows, key=lambda s: (0, int(s)) if s.isdigit() else (1, 0)
        ):
            out.append('      <div class="source-group">')
            out.append(
                f'        <h3 class="source-group-title">Source Group {esc(source_group)}</h3>'
            )
            out.append('        <div class="source-table-wrap">')
            out.append('          <table class="source-table">')
            out.append("            <colgroup>")
            for col in ("source", "type", "duration", "resolution", "fps", "sync"):
                out.append(f'              <col class="col-{col}">')
            out.append("            </colgroup>")
            out.append("            <thead>")
            out.append(
                "              <tr><th>Source</th><th>Type</th><th>Duration</th>"
                "<th>Resolution</th><th>FPS</th><th>Sync Offset</th></tr>"
            )
            out.append("            </thead>")
            out.append("            <tbody>")
            for row in source_rows[source_group]:
                tag = (
                    '<span class="source-tag">Audio Source</span>'
                    if row["is_audio_source"]
                    else ""
                )
                cells = "".join(
                    f"<td>{esc(row[key])}</td>"
                    for key in ("type", "duration", "resolution", "fps", "sync_offset")
                )
                out.append(
                    f'              <tr data-type="source-row" '
                    f'data-source="{esc(row["name"])}">'
                    f'<td class="source-name">{esc(row["name"])}{tag}</td>{cells}</tr>'
                )
            out.append("            </tbody>")
            out.append("          </table>")
            out.append("        </div>")
            out.append("      </div>")
        out.append("    </div>")
    out.append("  </header>")

    # ==============================
    # Potential issues
    # ==============================
    if issues:
        out.append('  <section class="issues-section" data-type="issues">')
        out.append('    <h1 class="section-heading">Potential Issues</h1>')
        out.append('    <ul class="issues-list">')
        for i, issue in enumerate(issues):
            out.append(
                f'      <li class="issue" data-type="issue" '
                f'data-json-path="issues[{i}]">'
                f'<span class="issue-tag">{esc(issue["tag"])}</span>'
                f"{esc(issue['text'])}</li>"
            )
        out.append("    </ul>")
        out.append("  </section>")

        # ==============================
        # Grading
        # ==============================
    if grading_previews:
        out.append('  <section class="grading-section" data-type="grading">')
        out.append('    <h1 class="section-heading">Grading</h1>')
        out.append('    <div class="grading-grid">')
        for preview in grading_previews:
            style = "" if preview.stem == "original" else preview.stem
            label = label_from_stem(preview.stem)
            selected = (
                ' data-selected="true"' if style and style == grading_selection else ""
            )
            out.append(
                f'      <figure class="grade-option" data-type="grade-option" '
                f'data-grading-style="{esc(style)}"{selected}>'
            )
            out.append(
                f'        <img src="{esc(preview.relative_to(out_dir))}" '
                f'alt="{esc(label)} grade preview">'
            )
            out.append(f"        <figcaption>{esc(label)}</figcaption>")
            out.append("      </figure>")
        out.append("    </div>")
        out.append("  </section>")

        # ==============================
        # Full-frame crops
        # ==============================
    if active_crop_previews:
        out.append('  <section class="pip-section" data-type="active-crops">')
        out.append('    <h1 class="section-heading">Framing</h1>')
        out.append('    <ul class="pip-list">')
        for preview in active_crop_previews:
            out.append(
                f'      <li class="pip-row" data-type="active-crop" '
                f'data-source="{esc(preview["source"])}" '
                f'data-frame="{esc(preview["frame"])}">'
            )
            out.append('        <div class="pip-meta">')
            out.append(
                f'          <span class="pip-source-group">Source Group '
                f"{esc(preview['source_group'])}</span>"
            )
            out.append(
                f'          <span class="pip-source">{esc(preview["source"])} '
                f'{esc(preview["frame"])}</span>'
            )
            out.append("        </div>")
            out.append(
                f'        <img class="active-crop-preview" '
                f'src="{esc(preview["path"].relative_to(out_dir))}" '
                f'alt="Crop preview for {esc(preview["source"])} {esc(preview["frame"])}">'
            )
            out.append("      </li>")
        out.append("    </ul>")
        out.append("  </section>")

        # ==============================
        # Picture-in-picture crops
        # ==============================
    pip_style = model.get("pip_style")
    if not isinstance(pip_style, dict):
        pip_style = {}
    raw_width = pip_style.get("width_fraction")
    pip_width = (
        float(raw_width)
        if isinstance(raw_width, (int, float)) and not isinstance(raw_width, bool)
        else 0.28
    )
    raw_margin = pip_style.get("margin_fraction")
    pip_margin = (
        float(raw_margin)
        if isinstance(raw_margin, (int, float)) and not isinstance(raw_margin, bool)
        else 0.025
    )
    raw_corner = pip_style.get("corner_radius_fraction")
    pip_corner = (
        float(raw_corner)
        if isinstance(raw_corner, (int, float)) and not isinstance(raw_corner, bool)
        else 0.08
    )
    pip_shape = pip_style.get("shape") if pip_style.get("shape") in {"rect", "circle", "square"} else "rect"
    pip_anchor = str(pip_style.get("anchor") or "bottom_right")
    raw_aspect = pip_style.get("aspect")
    pip_aspect = None
    if pip_shape in {"circle", "square"} or not raw_aspect:
        pip_aspect = 1.0
    else:
        parts = str(raw_aspect).split(":")
        if len(parts) == 2:
            try:
                pip_aspect = float(parts[0]) / float(parts[1])
            except ValueError:
                pip_aspect = None
    if not pip_aspect:
        pip_aspect = 16 / 9
    if pip_shape in {"circle", "square"}:
        pip_aspect_css = "1"
    else:
        pip_aspect_css = f"{pip_aspect:.6f}".rstrip("0").rstrip(".")
    pip_corner_css = (
        "0" if pip_shape == "circle" else f"{pip_corner:.4f}".rstrip("0").rstrip(".")
    )

    if pip_previews:
        out.append('  <section class="pip-section" data-type="pip-crops">')
        out.append('    <h1 class="section-heading">Picture-in-Picture</h1>')
        out.append('    <ul class="pip-list">')
        for preview in pip_previews:
            out.append(
                f'      <li class="pip-row" data-type="pip-crop" '
                f'data-source="{esc(preview["source"])}" '
                f'data-frame="pip">'
            )
            out.append('        <div class="pip-meta">')
            out.append(
                f'          <span class="pip-source-group">Source Group '
                f"{esc(preview['source_group'])}</span>"
            )
            out.append(
                f'          <span class="pip-source">{esc(preview["source"])}</span>'
            )
            out.append("        </div>")
            out.append(
                f'        <img class="pip-crop-preview {pip_shape}" '
                f'style="--pip-aspect: {pip_aspect_css}; --pip-corner: {pip_corner_css}" '
                f'src="{esc(preview["path"].relative_to(out_dir))}" '
                f'alt="PIP crop preview for {esc(preview["source"])}">'
            )
            out.append("      </li>")
        out.append("    </ul>")
        out.append("  </section>")

        # ==============================
        # Captions
        # ==============================
    if caption_previews:
        out.append('  <section class="captions-section" data-type="captions">')
        out.append('    <h1 class="section-heading">Captions</h1>')
        for preview in caption_previews:
            out.append('    <figure class="captions-preview">')
            out.append(
                f'      <img src="{esc(preview.relative_to(out_dir))}" '
                'alt="Captions over video preview">'
            )
            out.append("    </figure>")
        out.append("  </section>")

        # ==============================
        # Plan
        # ==============================
    out.append('  <h1 class="section-heading">Plan</h1>')

    frame_w, frame_h = (90, 160) if orientation == "portrait" else (160, 90)

    for scene in scenes:
        out.append(
            f'  <section class="scene" data-type="scene" '
            f'data-scene-id="{esc(scene["id"])}" '
            f'data-scene-index="{scene["index"]}" '
            f'data-json-path="{esc(scene["path"])}">'
        )
        out.append('    <h2 class="scene-heading">')
        out.append(
            f'      <span class="scene-number">Scene {scene["index"]:02d}</span>'
        )
        out.append(f'      <span class="scene-name">{esc(scene["name"])}</span>')
        out.append("    </h2>")
        out.append('    <div class="timeline-rule"></div>')
        out.append(
            f'    <div class="lines-layout" style="--line-count: {len(scene["lines"])}">'
        )
        out.append('      <ol class="lines">')

        for line in scene["lines"]:
            out.append(
                f'        <li class="line" style="grid-row: {line["index"]}" data-type="line" '
                f'data-scene-id="{esc(scene["id"])}" '
                f'data-line-id="{esc(line["id"])}" '
                f'data-line-index="{line["index"]}" '
                f'data-source="{esc(line["audio_source"])}" '
                f'data-edit-start="{fmt_tc(line["start"])}" '
                f'data-edit-end="{fmt_tc(line["end"])}" '
                f'data-json-path="{esc(line["path"])}">'
            )
            length = ""
            edit_range = ""
            if line["start"] is not None and line["end"] is not None:
                seconds = line["end"] - line["start"]
                length = f"{seconds:.2f}".rstrip("0").rstrip(".") + "s"
                edit_range = f'E:{fmt_tc(line["start"])}–{fmt_tc(line["end"])}'

            kept = [t for t in line["takes"] if t["kind"] == "kept-take"]
            rejected = [t for t in line["takes"] if t["kind"] == "cut-take"]

            hover = []
            if edit_range:
                hover.append(
                    f'<span class="line-hover-range">{esc(edit_range)}</span>'
                )
            hover_html = (
                f'<span class="line-hover">{"".join(hover)}</span>' if hover else ""
            )

            more = []
            kept_notes = [t for t in kept if t.get("reason")]
            if kept_notes:
                more.append('<span class="line-hover-block">')
                more.append('<span class="line-hover-label">Note</span>')
                for take in kept_notes:
                    more.append(
                        f'<span class="line-hover-note">{esc(take["reason"])}</span>'
                    )
                more.append("</span>")
            if rejected:
                more.append('<span class="line-hover-block">')
                plural = "" if len(rejected) == 1 else "s"
                more.append(
                    f'<span class="line-hover-label">Cut take{plural}</span>'
                )
                for take in rejected:
                    more.append(
                        '<span class="line-hover-cut" data-type="cut-take" '
                        f'data-scene-id="{esc(scene["id"])}" '
                        f'data-line-id="{esc(line["id"])}" '
                        f'data-take-id="{esc(take["id"])}" '
                        f'data-source="{esc(take["audio_source"])}" '
                        f'data-json-path="{esc(take["path"])}">'
                    )
                    if take.get("reason"):
                        more.append(
                            f'<span class="line-hover-note">{esc(take["reason"])}</span>'
                        )
                    for cut in take["cuts"]:
                        text = cut["transcript"]
                        if text is None and cut["index"] == 0:
                            text = take["transcript"]
                        if not text:
                            continue
                        more.append(
                            '<span class="line-hover-text" data-type="cut" '
                            f'data-cut-index="{cut["index"]}" '
                            f'data-seg-start="{fmt_tc(cut["start"])}" '
                            f'data-seg-end="{fmt_tc(cut["end"])}" '
                            f'data-json-path="{esc(cut["path"])}">'
                            f"{esc(text)}</span>"
                        )
                    more.append("</span>")
                more.append("</span>")
            more_html = (
                f'<div class="take-more-body">{"".join(more)}</div>' if more else ""
            )

            if kept:
                out.append('          <ul class="takes">')
                for take_index, take in enumerate(kept):
                    out.append(
                        '            <li class="take kept" '
                        f'data-type="{take["kind"]}" '
                        f'data-scene-id="{esc(scene["id"])}" '
                        f'data-line-id="{esc(line["id"])}" '
                        f'data-take-id="{esc(take["id"])}" '
                        f'data-source="{esc(take["audio_source"])}" '
                        f'data-json-path="{esc(take["path"])}">'
                    )
                    expandable = take_index == 0 and more_html
                    if expandable:
                        out.append('              <details class="take-more">')
                        out.append("                <summary>")
                    badge = f'L{line["index"]}'
                    if length:
                        badge = (
                            f'{esc(badge)}<span class="line-dash">-</span>'
                            f"{esc(length)}"
                        )
                    else:
                        badge = esc(badge)
                    extra = hover_html if take_index == 0 else ""
                    out.append(
                        f'              <span class="line-number">{badge}{extra}</span>'
                    )
                    out.append('              <ul class="take-segments">')
                    for cut in take["cuts"]:
                        text = cut["transcript"]
                        if text is None and cut["index"] == 0:
                            text = take["transcript"]
                        out.append(
                            '                <li class="take-segment" data-type="cut" '
                            f'data-cut-index="{cut["index"]}" '
                            f'data-seg-start="{fmt_tc(cut["start"])}" '
                            f'data-seg-end="{fmt_tc(cut["end"])}" '
                            f'data-json-path="{esc(cut["path"])}">'
                        )
                        if text:
                            out.append(
                                '                  <p class="take-transcript">'
                                f"{esc(text)}</p>"
                            )
                        out.append("                </li>")
                    out.append("              </ul>")
                    if expandable:
                        out.append("                </summary>")
                        out.append(f"                {more_html}")
                        out.append("              </details>")
                    out.append("            </li>")
                out.append("          </ul>")

            out.append("        </li>")

        out.append("      </ol>")

        cards_by_line: dict[str, list] = {}
        for card in scene["cards"]:
            cards_by_line.setdefault(card["line_id"], []).append(card)

        frame_rows = []
        for line in scene["lines"]:
            line_cards = cards_by_line.get(line["id"]) or []
            if not line_cards:
                continue
            shapes = []
            labels = []
            full_slots = 0
            for order, card in enumerate(line_cards, start=1):
                frame = card.get("frame")
                if card["type"] == "graphic":
                    kind_class = "graphic"
                    kind = card.get("source_type") or "graphic"
                elif card["type"] == "browser":
                    kind_class = "browser"
                    kind = card.get("source_type") or "browser"
                else:
                    kind_class = "footage"
                    source_name = str(card.get("source") or "")
                    kind = card.get("source_type") or (
                        source_name.split("-", 1)[1] if "-" in source_name else source_name
                    )
                name = card.get("source") or ""
                overlay = card["overlay"]
                if frame == "pip":
                    box_w = pip_width * frame_w
                    box_h = box_w / pip_aspect
                    gap = pip_margin * frame_w
                    if pip_anchor.endswith("left"):
                        box_x = gap
                    elif "center" in pip_anchor:
                        box_x = (frame_w - box_w) / 2
                    else:
                        box_x = frame_w - gap - box_w
                    if pip_anchor.startswith("top"):
                        box_y = gap
                    elif pip_anchor.startswith("bottom"):
                        box_y = frame_h - gap - box_h
                    else:
                        box_y = (frame_h - box_h) / 2
                    radius = 0 if pip_shape == "circle" else pip_corner * box_w
                    text_x = box_x + box_w / 2
                    text_y = box_y + box_h / 2
                    text_anchor = ' text-anchor="middle" dominant-baseline="middle"'
                    frame_words = "picture-in-picture"
                elif frame == "top":
                    box_x, box_y, box_w, box_h = 1, 1, frame_w - 2, (frame_h - 4) / 2
                    radius = 3
                    text_x = box_x + box_w / 2
                    text_y = box_y + box_h / 2
                    text_anchor = ' text-anchor="middle" dominant-baseline="middle"'
                    frame_words = "top"
                elif frame == "bottom":
                    half = (frame_h - 4) / 2
                    box_x, box_y, box_w, box_h = 1, 1 + half + 2, frame_w - 2, half
                    radius = 3
                    text_x = box_x + box_w / 2
                    text_y = box_y + box_h / 2
                    text_anchor = ' text-anchor="middle" dominant-baseline="middle"'
                    frame_words = "bottom"
                elif isinstance(frame, dict):
                    box_x = float(frame.get("x") or 0) * frame_w
                    box_y = float(frame.get("y") or 0) * frame_h
                    box_w = float(frame.get("w") or 0) * frame_w
                    box_h = float(frame.get("h") or 0) * frame_h
                    radius = min(3, box_w / 2, box_h / 2)
                    text_x = box_x + box_w / 2
                    text_y = box_y + box_h / 2
                    text_anchor = ' text-anchor="middle" dominant-baseline="middle"'
                    frame_words = "custom"
                else:
                    box_x, box_y, box_w, box_h = 1, 1, frame_w - 2, frame_h - 2
                    radius = 3
                    text_x = 10
                    text_y = 20 + full_slots * 16
                    text_anchor = ""
                    full_slots += 1
                    frame_words = "full"
                zoom = ", zoomed in" if card.get("zoom_cut") else ""
                labels.append(f"{frame_words} {kind} {name}{zoom}")
                shown = {
                    key: f"{float(value):.2f}".rstrip("0").rstrip(".")
                    for key, value in {
                        "x": box_x,
                        "y": box_y,
                        "w": box_w,
                        "h": box_h,
                        "rx": radius,
                        "tx": text_x,
                        "ty": text_y,
                        "rw": box_w / 2,
                        "rh": box_h / 2,
                    }.items()
                }
                paint = f"shape {kind_class}"
                if overlay:
                    paint += " overlay"
                if frame == "pip" and pip_shape == "circle":
                    shapes.append(
                        f'<ellipse class="{paint}" cx="{shown["tx"]}" cy="{shown["ty"]}" '
                        f'rx="{shown["rw"]}" ry="{shown["rh"]}"></ellipse>'
                    )
                else:
                    shapes.append(
                        f'<rect class="{paint}" x="{shown["x"]}" y="{shown["y"]}" '
                        f'width="{shown["w"]}" height="{shown["h"]}" rx="{shown["rx"]}"></rect>'
                    )
                shapes.append(
                    f'<text class="index {kind_class}" x="{shown["tx"]}" y="{shown["ty"]}"'
                    f'{text_anchor} aria-hidden="true">{order}</text>'
                )
            if len(labels) == 1:
                title = labels[0][:1].upper() + labels[0][1:]
            else:
                title = "Back to front: " + ", ".join(labels)
            body = "\n".join(f"            {shape}" for shape in shapes)
            frame_rows.append(
                f'        <div class="frame" style="grid-row: {line["index"]}">\n'
                f'          <svg viewBox="0 0 {frame_w} {frame_h}" role="img">\n'
                f"            <title>{esc(title)}</title>\n"
                f"{body}\n"
                f"          </svg>\n"
                f"        </div>"
            )
        if frame_rows:
            out.append('      <div class="frames">')
            out.extend(frame_rows)
            out.append("      </div>")

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

        if placed:
            layer_cols = max(column for _, column in placed)
            out.append(
                f'      <div class="layers" style="--layer-cols: {layer_cols}">'
            )
        for run, column in placed:
            card = dict(run[0])
            card["span"] = [part["line_id"] for part in run]
            card["end"] = run[-1]["end"]
            card["row_end"] = run[-1]["row_end"]
            card["column"] = column
            frame = card.get("frame")
            if card["type"] == "graphic":
                css = "active-source"
                extra = (
                    f' data-graphic-name="{esc(card["graphic"])}"'
                    f' data-graphic-index="{card["graphic_index"]}"'
                )
            elif card["type"] == "browser":
                css = "active-source"
                extra = (
                    f' data-browser-name="{esc(card["browser"])}"'
                    f' data-browser-index="{card["browser_index"]}"'
                )
            elif frame == "pip":
                css = "pip-card"
                extra = ""
            else:
                css = "active-source"
                extra = ""
            if isinstance(frame, str) and frame in {"full", "top", "bottom", "pip"}:
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
            if card["overlay_graphic_type"]:
                kind = f"{kind} · {card['overlay_graphic_type']}"
            name = card.get("source") or card.get("graphic") or card.get("browser") or ""
            described = bool(card["description"])
            tag = "details" if described else "div"
            card_class = f"{css} layer-card" if described else css
            out.append(
                f'      <{tag} class="{card_class}" '
                f'style="grid-row: {card["row_start"]} / {card["row_end"]}; '
                f'grid-column: {card["column"]}" '
                f'data-type="{card["type"]}" '
                f'data-scene-id="{esc(scene["id"])}" '
                f'data-line-id="{esc(card["line_id"])}" '
                f'data-line-ids="{esc(" ".join(card["span"]))}" '
                f'data-source="{esc(card["source"])}"{extra} '
                f'data-edit-start="{fmt_tc(card["start"])}" '
                f'data-edit-end="{fmt_tc(card["end"])}" '
                f'data-json-path="{esc(card["path"])}">'
            )
            if described:
                out.append("        <summary>")
            out.append(f'        <p class="layer-frame">{esc(frame_label)}</p>')
            out.append(f'        <p class="layer-kind">{esc(kind)}</p>')
            out.append(f'        <p class="layer-name">{esc(name)}</p>')
            if card["description"]:
                out.append(
                    f'          <p class="active-source-copy" '
                    f'data-json-path="sources.{esc(card["source"])}.description">'
                    f"{esc(card['description'])}</p>"
                )
            if described:
                out.append("        </summary>")
            extras = []
            if card.get("actions"):
                action_bits = []
                for action in card["actions"]:
                    if not isinstance(action, dict):
                        continue
                    action_type = action.get("type")
                    at = action.get("at")
                    if action_type == "open":
                        open_url = action.get("url")
                        if isinstance(open_url, str) and open_url.strip():
                            action_bits.append(f"open {open_url} at {at}")
                        else:
                            action_bits.append(f"open at {at}")
                    elif action_type == "scroll":
                        action_bits.append(f'scroll to "{action.get("to")}" at {at}')
                    elif action_type == "highlight":
                        action_bits.append(
                            f'highlight "{action.get("text")}" at {at}'
                        )
                if action_bits:
                    extras.append(
                        f'<p class="active-source-copy" '
                        f'data-json-path="sources.{esc(card["source"])}.actions">'
                        f"{esc(', '.join(action_bits))}</p>"
                    )
            if extras:
                out.append(
                    f'        <div class="layer-extra">{"".join(extras)}</div>'
                )
            out.append(f"      </{tag}>")
        if placed:
            out.append("      </div>")

        out.append("    </div>")
        out.append("  </section>")

    out.append("</div>")

    # ==================================================
    # Write
    # ==================================================

    title = model["title"] or "Editing Plan"
    head = re.sub(
        r"<title>.*?</title>",
        f"<title>{esc(title)} — plan {plan_hash}</title>",
        head_part,
        count=1,
        flags=re.DOTALL,
    )

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"plan-{plan_hash}.html"
    out_path.write_text(head + "\n\n" + "\n".join(out) + "\n\n" + tail_part + "\n")

    for stale in sorted(out_dir.glob("plan-*.html")):
        if stale != out_path:
            stale.unlink()
            print(f"removed stale plan → {stale.name}")

    line_count = sum(len(s["lines"]) for s in scenes)
    take_count = sum(len(b["takes"]) for s in scenes for b in s["lines"])
    print(f"plan → {out_path}")
    print(
        f"  {len(scenes)} scene(s), {line_count} line(s), {take_count} take(s), "
        f"{graphic_count} graphic(s), {browser_count} browser recording(s), runtime {runtime}"
    )
    print(
        f"  discovered {sum(len(v) for v in source_rows.values())} source(s), "
        f"{len(grading_previews)} grading preview(s), "
        f"{len(active_crop_previews)} active crop(s), "
        f"{len(pip_previews)} pip crop(s), "
        f"{len(caption_previews)} caption preview(s)"
    )


if __name__ == "__main__":
    main()

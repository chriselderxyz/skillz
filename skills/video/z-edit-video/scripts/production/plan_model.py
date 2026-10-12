"""Shared plan loader, validator, and timecode helpers.

Used by `build_plan_html.py`, `render.py`, and `build_srt.py` so they compile
from the same reading of `edit/edit.json` and reject the same mistakes.

`load_plan` walks `scenes` and `lines` in key order (that is play order),
checks the edit clock against the audio-source-clock cuts, and returns a resolved
model with every cut placed on the edit clock. Any problem is printed to
stderr and the process exits, so callers can assume a valid model.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sys
from pathlib import Path


# ==================================================
# Timecode
# ==================================================

_TC_RE = re.compile(r"(\d{2,}):([0-5]\d):([0-5]\d)\.(\d{2})")


def parse_tc(value, where: str, errors: list[str]) -> float | None:
    """`HH:MM:SS.ss` -> float seconds, or None with an error recorded."""
    if not isinstance(value, str):
        errors.append(f"{where}: expected a HH:MM:SS.ss string, got {value!r}")
        return None

    match = _TC_RE.fullmatch(value)
    if match is None:
        errors.append(f"{where}: expected HH:MM:SS.ss, got {value!r}")
        return None

    try:
        hours, minutes, seconds, centiseconds = (int(part) for part in match.groups())
        total = hours * 3600 + minutes * 60 + seconds + centiseconds / 100.0
    except (ValueError, OverflowError):
        errors.append(f"{where}: expected HH:MM:SS.ss, got {value!r}")
        return None

    if not math.isfinite(total):
        errors.append(f"{where}: expected HH:MM:SS.ss, got {value!r}")
        return None

    return total


def fmt_tc(seconds: float) -> str:
    total = int(round(float(seconds) * 100))
    h, rem = divmod(total, 360_000)
    m, rem = divmod(rem, 6_000)
    s, cs = divmod(rem, 100)
    return f"{h:02d}:{m:02d}:{s:02d}.{cs:02d}"


def _crop_int(value, where: str, errors: list[str]) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        errors.append(f"{where}: expected an integer")
        return None
    return value


def normalize_crop(
    raw,
    where: str,
    errors: list[str],
    source_size: tuple[int, int] | None,
    aspect: float | None,
) -> dict | None:
    """Resolve a crop rectangle of integer source pixels."""
    if not isinstance(raw, dict):
        errors.append(f"{where}: crop must be an object")
        return None

    x = _crop_int(raw.get("x"), f"{where}.x", errors)
    y = _crop_int(raw.get("y"), f"{where}.y", errors)
    w = _crop_int(raw.get("w"), f"{where}.w", errors)
    h = _crop_int(raw.get("h"), f"{where}.h", errors)
    if None in (x, y, w, h):
        return None
    if w <= 0 or h <= 0:
        errors.append(f"{where}: w and h must be positive")
        return None
    if x < 0 or y < 0:
        errors.append(f"{where}: x and y must be non-negative")
        return None
    if aspect is not None and abs((w / h) - aspect) / aspect > 0.01:
        errors.append(f"{where}: {w}x{h} does not match the frame")
        return None
    if source_size is not None and (
        x + w > source_size[0] or y + h > source_size[1]
    ):
        errors.append(
            f"{where}: crop exceeds source dimensions "
            f"{source_size[0]}x{source_size[1]}"
        )
        return None

    return {"x": x, "y": y, "w": w, "h": h}


# ==================================================
# Load and validate
# ==================================================


def load_plan(plan_path: Path, tolerance: float = 0.011) -> dict:
    """Read, validate, and resolve `edit.json`.

    Returns `{"hash", "title", "description", "issues", "runtime", "scenes",
    "source_groups", "sources", "video_settings", "caption_style", "srt_style",
    "pip_style", "grading_style"}`.
    Each scene holds `lines` in play order and `cards` (layers)
    with grid rows. Every cut carries `edit_start` / `edit_end`. A footage
    layer's resolved `start` / `end` are seeks in that source: the audio
    source clock plus that source's sync offset. Unsynced footage
    keeps the seek written on the layer.
    """
    if not plan_path.is_file():
        sys.exit(f"edit.json not found: {plan_path}")

    raw_plan = plan_path.read_bytes()
    plan_hash = hashlib.sha256(raw_plan).hexdigest()[:8]
    try:
        plan = json.loads(raw_plan)
    except json.JSONDecodeError as e:
        sys.exit(f"invalid JSON in {plan_path}: {e}")
    if not isinstance(plan, dict):
        sys.exit(f"{plan_path} must be a JSON object")

    scenes_obj = plan.get("scenes")
    if not isinstance(scenes_obj, dict) or not scenes_obj:
        sys.exit(f"{plan_path}: 'scenes' must be a non-empty object of scene ids")

    errors: list[str] = []
    scenes: list[dict] = []
    source_groups = plan.get("source_groups")
    if not isinstance(source_groups, dict):
        source_groups = {}
    for group_number, group_info in source_groups.items():
        if isinstance(group_info, dict) and "sources" in group_info:
            errors.append(
                f"source_groups.{group_number}.sources is not a field; "
                "source records belong on sources"
            )
    sources = plan.get("sources")
    if not isinstance(sources, dict):
        sources = {}
    browser_jobs: dict[str, list[dict]] = {}
    for source_name, record in sources.items():
        if not isinstance(record, dict):
            errors.append(f"sources.{source_name}: expected an object")
            continue
        if record.get("type") in {"graphic", "browser"}:
            if not str(record.get("description") or "").strip():
                errors.append(f"sources.{source_name}.description: required")
            path = record.get("path")
            if path is not None and (not isinstance(path, str) or not path.strip()):
                errors.append(f"sources.{source_name}.path: expected a path")
            if record.get("type") == "browser":
                if "url" in record:
                    errors.append(f"sources.{source_name}.url is not a field")
                raw_actions = record.get("actions")
                parsed_actions: list[dict] = []
                if not isinstance(raw_actions, list) or not raw_actions:
                    errors.append(
                        f"sources.{source_name}.actions: expected a non-empty array"
                    )
                else:
                    for action_index, action in enumerate(raw_actions):
                        action_path = f"sources.{source_name}.actions[{action_index}]"
                        if not isinstance(action, dict):
                            errors.append(f"{action_path}: expected an object")
                            continue
                        action_type = action.get("type")
                        at = parse_tc(action.get("at"), f"{action_path}.at", errors)
                        if action_type == "open":
                            raw_open_url = action.get("url")
                            open_url = ""
                            if (
                                not isinstance(raw_open_url, str)
                                or not raw_open_url.strip().startswith(
                                    ("http://", "https://")
                                )
                            ):
                                errors.append(
                                    f"{action_path}.url: expected an http or https url"
                                )
                            else:
                                open_url = raw_open_url.strip()
                            parsed_actions.append(
                                {"type": "open", "at": at, "url": open_url}
                            )
                        elif action_type == "scroll":
                            target = action.get("to")
                            if not isinstance(target, str) or not target.strip():
                                errors.append(
                                    f"{action_path}.to: expected the text to scroll to"
                                )
                                target = ""
                            parsed_actions.append(
                                {
                                    "type": "scroll",
                                    "at": at,
                                    "to": target.strip()
                                    if isinstance(target, str)
                                    else "",
                                }
                            )
                        elif action_type == "highlight":
                            text = action.get("text")
                            if not isinstance(text, str) or not text.strip():
                                errors.append(
                                    f"{action_path}.text: expected the text to highlight"
                                )
                                text = ""
                            parsed_actions.append(
                                {
                                    "type": "highlight",
                                    "at": at,
                                    "text": text.strip() if isinstance(text, str) else "",
                                }
                            )
                        else:
                            errors.append(
                                f"{action_path}.type: expected open, scroll, or highlight"
                            )
                browser_jobs[str(source_name)] = parsed_actions
            continue
        if not str(record.get("path") or "").strip():
            errors.append(f"sources.{source_name}: expected an object with path")
            continue
        base_crops = record.get("base_crops")
        if base_crops is None:
            continue
        if not isinstance(base_crops, dict):
            errors.append(f"sources.{source_name}.base_crops: must be an object")
            continue
        for frame_name in base_crops:
            if frame_name not in {"full", "pip", "top", "bottom"}:
                errors.append(
                    f"sources.{source_name}.base_crops.{frame_name}: "
                    "expected full, pip, top, or bottom"
                )
    video_settings = plan.get("video_settings")
    if not isinstance(video_settings, dict):
        video_settings = {}
    orientation = str(video_settings.get("orientation") or "").strip().lower()
    resolution_name = str(video_settings.get("resolution") or "").strip().upper()
    if orientation == "portrait":
        output_w, output_h = (2160, 3840) if resolution_name == "4K" else (1080, 1920)
        output_aspect = 9 / 16
    elif orientation == "landscape":
        output_w, output_h = (3840, 2160) if resolution_name == "4K" else (1920, 1080)
        output_aspect = 16 / 9
    else:
        output_w, output_h = 0, 0
        output_aspect = None
    video_style = plan.get("video_style")
    if not isinstance(video_style, dict):
        video_style = {}
    raw_zoom_style = video_style.get("zoom_cut", False)
    if not isinstance(raw_zoom_style, bool):
        errors.append("video_style.zoom_cut: expected true or false")
        zoom_cuts_enabled = False
    else:
        zoom_cuts_enabled = raw_zoom_style
    raw_zoom_amount = video_style.get("zoom_amount")
    zoom_amount_ok = (
        isinstance(raw_zoom_amount, (int, float))
        and not isinstance(raw_zoom_amount, bool)
        and raw_zoom_amount > 1
    )
    zoom_amount = float(raw_zoom_amount) if zoom_amount_ok else 1.0
    if zoom_cuts_enabled and not zoom_amount_ok:
        errors.append("video_style.zoom_amount: expected a number greater than 1")
    elif raw_zoom_amount is not None and not zoom_amount_ok:
        errors.append("video_style.zoom_amount: expected a number greater than 1")
    pip_style = plan.get("pip_style")
    pip_aspect = None
    if isinstance(pip_style, dict):
        shape = pip_style.get("shape")
        raw_aspect = pip_style.get("aspect")
        if shape in {"circle", "square"} or not raw_aspect:
            pip_aspect = 1.0
        else:
            parts = str(raw_aspect).split(":")
            if len(parts) == 2:
                try:
                    pip_aspect = float(parts[0]) / float(parts[1])
                except ValueError:
                    pip_aspect = None
    line_owner: dict[str, str] = {}
    take_owner: dict[str, str] = {}
    edit_clock = 0.0
    graphic_index = 0
    browser_index = 0

    issues: list[dict] = []
    raw_issues = plan.get("issues")
    if raw_issues is not None and not isinstance(raw_issues, list):
        errors.append("issues: must be an array")
    elif isinstance(raw_issues, list):
        for i, issue in enumerate(raw_issues):
            if isinstance(issue, str):
                issues.append({"tag": "Issue", "text": issue})
            elif isinstance(issue, dict) and issue.get("text"):
                issues.append(
                    {"tag": issue.get("tag") or "Issue", "text": issue["text"]}
                )
            else:
                errors.append(f"issues[{i}]: must be a string or have 'text'")

    for scene_index, (scene_id, scene) in enumerate(scenes_obj.items(), start=1):
        scene_path = f"scenes.{scene_id}"
        if not isinstance(scene, dict):
            errors.append(f"{scene_path}: scene must be an object")
            continue

        lines_obj = scene.get("lines")
        if not isinstance(lines_obj, dict) or not lines_obj:
            errors.append(f"{scene_path}: 'lines' must be a non-empty object")
            continue

        lines: list[dict] = []
        cards: list[dict] = []

        for line_index, (line_id, line) in enumerate(lines_obj.items(), start=1):
            line_path = f"{scene_path}.lines.{line_id}"
            if not isinstance(line, dict):
                errors.append(f"{line_path}: line must be an object")
                continue
            if line_id in line_owner:
                errors.append(
                    f"{line_path}: line id already used by {line_owner[line_id]}"
                )
            line_owner[line_id] = line_path

            line_start = parse_tc(
                line.get("edit_start"), f"{line_path}.edit_start", errors
            )
            line_end = parse_tc(line.get("edit_end"), f"{line_path}.edit_end", errors)

            # ==============================
            # Takes
            # ==============================
            kept = line.get("kept_take")
            if not isinstance(kept, dict):
                errors.append(f"{line_path}.kept_take: must be an object")
                kept = {}

            rejected = line.get("rejected_takes")
            if rejected is None:
                rejected = []
            if not isinstance(rejected, list):
                errors.append(f"{line_path}.rejected_takes: must be an array")
                rejected = []

            takes: list[dict] = []
            for take, kind, take_path in [
                (kept, "kept-take", f"{line_path}.kept_take"),
                *[
                    (t, "cut-take", f"{line_path}.rejected_takes[{i}]")
                    for i, t in enumerate(rejected)
                ],
            ]:
                if not isinstance(take, dict):
                    errors.append(f"{take_path}: take must be an object")
                    continue

                take_id = take.get("id")
                if not isinstance(take_id, str) or not take_id:
                    errors.append(f"{take_path}.id: required, got {take_id!r}")
                    take_id = ""
                elif take_id in take_owner:
                    errors.append(
                        f"{take_path}.id: take id {take_id} already used by "
                        f"{take_owner[take_id]}"
                    )
                if take_id:
                    take_owner[take_id] = take_path

                if not take.get("audio_source"):
                    errors.append(f"{take_path}.audio_source: required")
                if kind == "cut-take" and not take.get("reason"):
                    errors.append(f"{take_path}.reason: required on a rejected take")

                raw_cuts = take.get("cuts")
                if not isinstance(raw_cuts, list) or not raw_cuts:
                    errors.append(f"{take_path}.cuts: must be a non-empty array")
                    raw_cuts = []

                    # Kept-take cuts are laid end to end from the line's edit_start
                cuts: list[dict] = []
                playhead = line_start if line_start is not None else 0.0
                for ci, cut in enumerate(raw_cuts):
                    cut_path = f"{take_path}.cuts[{ci}]"
                    if not isinstance(cut, dict):
                        errors.append(f"{cut_path}: cut must be an object")
                        continue
                    cs = parse_tc(cut.get("audio_source_start"), f"{cut_path}.audio_source_start", errors)
                    ce = parse_tc(cut.get("audio_source_end"), f"{cut_path}.audio_source_end", errors)
                    if cs is not None and ce is not None and ce <= cs:
                        errors.append(f"{cut_path}: audio_source_end must be after audio_source_start")
                    duration = (ce - cs) if (cs is not None and ce is not None) else 0.0
                    cuts.append(
                        {
                            "index": ci,
                            "path": cut_path,
                            "start": cs,
                            "end": ce,
                            "edit_start": playhead,
                            "edit_end": playhead + duration,
                            "transcript": cut.get("transcript"),
                        }
                    )
                    playhead += duration

                takes.append(
                    {
                        "kind": kind,
                        "path": take_path,
                        "id": take_id,
                        "audio_source": take.get(
                            "audio_source"
                        )
                        or "",
                        "transcript": take.get("transcript"),
                        "reason": take.get("reason"),
                        "cuts": cuts,
                    }
                )

                # ==============================
                # Edit clock
                # ==============================
            kept_cuts = (
                takes[0]["cuts"] if takes and takes[0]["kind"] == "kept-take" else []
            )
            kept_total = sum(
                c["end"] - c["start"]
                for c in kept_cuts
                if c["start"] is not None and c["end"] is not None
            )

            if line_start is not None and abs(line_start - edit_clock) > tolerance:
                errors.append(
                    f"{line_path}.edit_start: {fmt_tc(line_start)} does not continue "
                    f"the edit clock, expected {fmt_tc(edit_clock)}"
                )
            if line_start is not None and line_end is not None:
                line_duration = line_end - line_start
                if line_duration <= 0:
                    errors.append(f"{line_path}: edit_end must be after edit_start")
                elif abs(line_duration - kept_total) > tolerance:
                    errors.append(
                        f"{line_path}: kept_take cuts total {kept_total:.2f}s but the "
                        f"line is {line_duration:.2f}s on the edit clock"
                    )
                edit_clock = line_end
            else:
                edit_clock += kept_total

            lines.append(
                {
                    "id": line_id,
                    "index": line_index,
                    "path": line_path,
                    "start": line_start,
                    "end": line_end,
                    "audio_source": (
                        takes[0]["audio_source"] if takes else ""
                    ),
                    "takes": takes,
                    "kept": takes[0] if takes else None,
                    "active": None,
                    "layers": [],
                }
            )

        line_rows = {b["id"]: b["index"] for b in lines}
        by_id = {b["id"]: b for b in lines}
        named_frames = {"full", "pip", "top", "bottom"}

        # ==============================
        # Layers
        # ==============================
        for line_id, line in lines_obj.items():
            if not isinstance(line, dict):
                continue
            this_line = by_id[line_id]
            raw_layers = line.get("layers")
            line_path = f"{scene_path}.lines.{line_id}"
            for stale in ("active_source_file", "active_source", "pip", "line_range"):
                if stale in line:
                    errors.append(f"{line_path}: {stale} is not a field; use layers")
            if not isinstance(raw_layers, list) or not raw_layers:
                errors.append(f"{line_path}.layers: must be a non-empty array")
                continue

            for layer_index, card in enumerate(raw_layers):
                card_path = f"{line_path}.layers[{layer_index}]"
                if not isinstance(card, dict):
                    errors.append(f"{card_path}: must be an object")
                    continue

                card_start = parse_tc(
                    card.get("edit_start"), f"{card_path}.edit_start", errors
                )
                card_end = parse_tc(
                    card.get("edit_end"), f"{card_path}.edit_end", errors
                )
                if (
                    card_start is not None
                    and this_line["start"] is not None
                    and card_start < this_line["start"] - tolerance
                ):
                    errors.append(
                        f"{card_path}.edit_start: {fmt_tc(card_start)} is before "
                        f"line {line_id} at {fmt_tc(this_line['start'])}"
                    )
                if (
                    card_end is not None
                    and this_line["end"] is not None
                    and card_end > this_line["end"] + tolerance
                ):
                    errors.append(
                        f"{card_path}.edit_end: {fmt_tc(card_end)} is after "
                        f"line {line_id} at {fmt_tc(this_line['end'])}"
                    )

                if "graphic" in card:
                    errors.append(f"{card_path}.graphic: is not a field; use source")
                if "description" in card:
                    errors.append(
                        f"{card_path}.description: is not a field; "
                        "description belongs on the source"
                    )
                source_name = str(card.get("source") or "").strip()
                record = sources.get(source_name) if source_name else None
                if source_name and not isinstance(record, dict):
                    errors.append(
                        f"{card_path}.source: {source_name} is missing from sources"
                    )
                    record = {}
                is_graphic = isinstance(record, dict) and record.get("type") == "graphic"
                is_browser = isinstance(record, dict) and record.get("type") == "browser"
                is_placed = is_graphic or is_browser
                frame = card.get("frame")
                if is_placed:
                    if card.get("cuts"):
                        errors.append(
                            f"{card_path}: a {record.get('type')} has no cuts"
                        )
                    if "x" in card or "y" in card:
                        errors.append(f"{card_path}: x and y belong on frame")
                    if not source_name:
                        errors.append(f"{card_path}.source: required")
                    elif not str(record.get("description") or "").strip():
                        errors.append(f"sources.{source_name}.description: required")
                    if is_graphic and frame != "full" and not isinstance(frame, dict):
                        errors.append(
                            f"{card_path}.frame: expected full, or x, y, w, and h"
                        )
                    if is_browser and frame not in {"full", "top", "bottom"} and not isinstance(
                        frame, dict
                    ):
                        errors.append(
                            f"{card_path}.frame: expected full, top, bottom, or x, y, w, and h"
                        )
                    if is_graphic:
                        graphic_index += 1
                    else:
                        browser_index += 1
                else:
                    if not card.get("source"):
                        errors.append(f"{card_path}.source: required")
                    if isinstance(frame, str) and frame not in named_frames:
                        errors.append(
                            f"{card_path}.frame: expected full, pip, top, or bottom"
                        )
                    elif not isinstance(frame, str) and not isinstance(frame, dict):
                        errors.append(f"{card_path}.frame: required")

                if isinstance(frame, dict):
                    ok = True
                    for key in ("x", "y", "w", "h"):
                        value = frame.get(key)
                        if (
                            isinstance(value, bool)
                            or not isinstance(value, (int, float))
                            or not (0 <= float(value) <= 1)
                        ):
                            ok = False
                    if (
                        not ok
                        or float(frame.get("w") or 0) <= 0
                        or float(frame.get("h") or 0) <= 0
                    ):
                        errors.append(
                            f"{card_path}.frame: x, y, w, h are fractions of the frame"
                        )

                # Cuts are laid end to end from the layer's edit_start.
                # Stored times stay on the audio source clock. The seek
                # adds the sync offset unless this footage is unsynced.
                cuts = []
                seek_offset = 0.0
                if not is_placed:
                    source_name = str(card.get("source") or "")
                    audio_ref = this_line.get("audio_source") or ""
                    if source_name and audio_ref and source_name != audio_ref:
                        source_group = source_name.split("-", 1)[0]
                        audio_group = str(audio_ref).split("-", 1)[0]
                        info = sources.get(source_name)
                        if not isinstance(info, dict):
                            info = {}
                        source_type = info.get("type")
                        if not source_type and "-" in source_name:
                            source_type = source_name.split("-", 1)[1]
                        has_audio = info.get("audio")
                        from_zero = (
                            source_type
                            in {"wide", "detail", "reaction", "cutaway", "voiceover"}
                            or has_audio is False
                            or source_group != audio_group
                        )
                        if not from_zero:
                            group_info = source_groups.get(audio_group)
                            sync = (
                                group_info.get("sync")
                                if isinstance(group_info, dict)
                                else None
                            )
                            raw_offset = (
                                sync.get(source_name) if isinstance(sync, dict) else None
                            )
                            if isinstance(raw_offset, (int, float)) and not isinstance(
                                raw_offset, bool
                            ):
                                seek_offset = float(raw_offset)
                if not is_placed:
                    raw_cuts = card.get("cuts")
                    if not isinstance(raw_cuts, list) or not raw_cuts:
                        errors.append(f"{card_path}.cuts: must be a non-empty array")
                        raw_cuts = []
                    playhead = card_start if card_start is not None else 0.0
                    for ci, cut in enumerate(raw_cuts):
                        cut_path = f"{card_path}.cuts[{ci}]"
                        if not isinstance(cut, dict):
                            errors.append(f"{cut_path}: cut must be an object")
                            continue
                        cs = parse_tc(
                            cut.get("audio_source_start"), f"{cut_path}.audio_source_start", errors
                        )
                        ce = parse_tc(cut.get("audio_source_end"), f"{cut_path}.audio_source_end", errors)
                        if cs is not None and ce is not None and ce <= cs:
                            errors.append(
                                f"{cut_path}: audio_source_end must be after audio_source_start"
                            )
                        duration = (
                            (ce - cs) if (cs is not None and ce is not None) else 0.0
                        )
                        file_start = cs + seek_offset if cs is not None else None
                        file_end = ce + seek_offset if ce is not None else None
                        if file_start is not None and file_start < -1e-6:
                            errors.append(
                                f"{cut_path}: {source_name} seek {fmt_tc(file_start)} "
                                "is before the start of the source"
                            )
                        cuts.append(
                            {
                                "index": ci,
                                "path": cut_path,
                                "start": file_start,
                                "end": file_end,
                                "clock_start": cs,
                                "clock_end": ce,
                                "edit_start": playhead,
                                "edit_end": playhead + duration,
                            }
                        )
                        playhead += duration

                    cut_total = sum(
                        c["end"] - c["start"]
                        for c in cuts
                        if c["start"] is not None and c["end"] is not None
                    )
                    if (
                        card_start is not None
                        and card_end is not None
                        and abs((card_end - card_start) - cut_total) > tolerance
                    ):
                        errors.append(
                            f"{card_path}: cuts total {cut_total:.2f}s but the window is "
                            f"{card_end - card_start:.2f}s on the edit clock"
                        )

                if is_placed and "zoom_cut" in card:
                    errors.append(
                        f"{card_path}.zoom_cut: belongs on a full-frame camera shot"
                    )

                layer_crop = None
                if not is_placed:
                    record = sources.get(str(card.get("source") or ""))
                    if not isinstance(record, dict):
                        record = {}
                    source_size = None
                    size_match = re.fullmatch(
                        r"\s*(\d+)\s*[x×]\s*(\d+)\s*",
                        str(record.get("resolution") or ""),
                    )
                    if size_match:
                        source_size = (int(size_match.group(1)), int(size_match.group(2)))
                    if (
                        isinstance(frame, dict)
                        and output_w
                        and output_h
                        and all(k in frame for k in ("x", "y", "w", "h"))
                    ):
                        frame_aspect = (float(frame["w"]) * output_w) / (
                            float(frame["h"]) * output_h
                        )
                    elif frame == "pip":
                        frame_aspect = pip_aspect
                    elif frame in {"top", "bottom"}:
                        frame_aspect = output_aspect * 2 if output_aspect else None
                    elif frame == "full":
                        frame_aspect = output_aspect
                    else:
                        frame_aspect = None
                    base_crops = record.get("base_crops")
                    base_crop = None
                    if isinstance(frame, str) and isinstance(base_crops, dict):
                        base_crop = base_crops.get(frame)
                    raw_cuts = card.get("cuts")
                    if isinstance(raw_cuts, list):
                        for cut_index, raw_cut in enumerate(raw_cuts):
                            if isinstance(raw_cut, dict) and "crop" in raw_cut:
                                errors.append(
                                    f"{card_path}.cuts[{cut_index}].crop: "
                                    "crop belongs on the layer"
                                )
                    raw_layer_crop = card.get("crop")
                    if raw_layer_crop is not None:
                        layer_crop = normalize_crop(
                            raw_layer_crop,
                            f"{card_path}.crop",
                            errors,
                            source_size,
                            frame_aspect,
                        )
                    elif base_crop is not None:
                        layer_crop = normalize_crop(
                            base_crop,
                            f"sources.{card.get('source')}.base_crops.{frame}",
                            errors,
                            source_size,
                            frame_aspect,
                        )
                    # ==============================
                    # Zoom cut
                    # ==============================
                    zoom_on = card.get("zoom_cut") is True
                    if "zoom_cut" in card and card.get("zoom_cut") is not True:
                        errors.append(
                            f"{card_path}.zoom_cut: expected true, or omit it"
                        )
                    if zoom_on and not zoom_cuts_enabled:
                        errors.append(
                            f"{card_path}.zoom_cut: video_style.zoom_cut is not true"
                        )
                    if zoom_on and (is_placed or frame != "full"):
                        errors.append(
                            f"{card_path}.zoom_cut: belongs on a full-frame camera shot"
                        )
                    source_type = record.get("type")
                    if zoom_on and source_type != "head":
                        if isinstance(source_type, str) and source_type:
                            errors.append(
                                f"{card_path}.zoom_cut: {source_type} stays at its crop"
                            )
                        else:
                            errors.append(
                                f"{card_path}.zoom_cut: belongs on a head source"
                            )
                    if (
                        zoom_on
                        and frame == "full"
                        and not is_placed
                        and source_type == "head"
                    ):
                        resting = layer_crop
                        if (
                            resting is None
                            and source_size is not None
                            and frame_aspect
                        ):
                            sw, sh = source_size
                            if sw > 0 and sh > 0 and (sw / sh) > frame_aspect:
                                ch = max(2, sh // 2 * 2)
                                cw = max(2, int(round(ch * frame_aspect)) // 2 * 2)
                                cx = max(0, (sw - cw) // 2)
                                cy = max(0, (sh - ch) // 2)
                            elif sw > 0 and sh > 0:
                                cw = max(2, sw // 2 * 2)
                                ch = max(2, int(round(cw / frame_aspect)) // 2 * 2)
                                cx = max(0, (sw - cw) // 2)
                                cy = max(0, (sh - ch) // 2)
                            else:
                                cw, ch, cx, cy = 0, 0, 0, 0
                            if (
                                cw >= 2
                                and ch >= 2
                                and cx + cw <= sw
                                and cy + ch <= sh
                            ):
                                resting = {"x": cx, "y": cy, "w": cw, "h": ch}
                        if resting is None:
                            errors.append(
                                f"{card_path}.zoom_cut: the resting frame "
                                "could not be resolved"
                            )
                        else:
                            aspect = resting["w"] / resting["h"]
                            iw = max(2, int(resting["w"] / zoom_amount) // 2 * 2)
                            ih = max(2, int(round(iw / aspect)) // 2 * 2)
                            if ih > resting["h"]:
                                ih = max(2, resting["h"] // 2 * 2)
                                iw = max(2, int(round(ih * aspect)) // 2 * 2)
                            if iw > resting["w"]:
                                iw = max(2, resting["w"] // 2 * 2)
                            ix = resting["x"] + max(0, (resting["w"] - iw) // 2)
                            iy = resting["y"] + max(0, (resting["h"] - ih) // 2)
                            if source_size is not None:
                                sw, sh = source_size
                                if ix + iw > sw:
                                    iw = max(2, (sw - ix) // 2 * 2)
                                if iy + ih > sh:
                                    ih = max(2, (sh - iy) // 2 * 2)
                            layer_crop = {"x": ix, "y": iy, "w": iw, "h": ih}
                    needs_crop = frame == "pip" or (
                        frame_aspect is not None
                        and source_size is not None
                        and source_size[1]
                        and abs((source_size[0] / source_size[1]) - frame_aspect)
                        / frame_aspect
                        > 0.01
                    )
                    for cut in cuts:
                        cut["crop"] = layer_crop
                        if layer_crop is None and needs_crop:
                            errors.append(f"{cut['path']}: crop is required")

                source_type = ""
                if isinstance(record, dict) and isinstance(record.get("type"), str):
                    source_type = record.get("type")

                resolved = {
                    "type": (
                        "browser"
                        if is_browser
                        else "graphic"
                        if is_graphic
                        else "footage"
                    ),
                    "frame": frame,
                    "z": layer_index,
                    "path": card_path,
                    "line_id": line_id,
                    "span": [line_id],
                    "row_start": line_rows[line_id],
                    "row_end": line_rows[line_id] + 1,
                    "source": card.get("source") or "",
                    "source_type": source_type,
                    "zoom_cut": card.get("zoom_cut") is True,
                    "graphic": source_name if is_graphic else "",
                    "graphic_index": graphic_index if is_graphic else None,
                    "browser": source_name if is_browser else "",
                    "browser_index": browser_index if is_browser else None,
                    "actions": record.get("actions") if is_browser else None,
                    "description": record.get("description") if is_placed else None,
                    "start": card_start,
                    "end": card_end,
                    "cuts": cuts,
                }
                cards.append(resolved)
                this_line["layers"].append(resolved)

            full_footage = [
                c
                for c in this_line["layers"]
                if c["type"] == "footage" and c["frame"] == "full"
            ]
            if len(full_footage) > 1:
                errors.append(
                    f"{line_path}: more than one layer uses frame full"
                )
            cover = [
                c
                for c in this_line["layers"]
                if c["type"] in {"graphic", "browser"} and c["frame"] == "full"
            ]
            if full_footage:
                this_line["active"] = full_footage[0]
            elif cover:
                this_line["active"] = cover[0]
            else:
                this_line["active"] = None

        scenes.append(
            {
                "id": scene_id,
                "index": scene_index,
                "path": scene_path,
                "name": scene.get("name") or scene_id,
                "lines": lines,
                "cards": cards,
            }
        )

    # ==============================
    # Browser recordings
    # ==============================
    raw_min_browser = video_style.get("min_browser_length_ms")
    raw_max_browser = video_style.get("max_browser_length_ms")
    min_browser_ms = None
    max_browser_ms = None
    if raw_min_browser is not None:
        if (
            isinstance(raw_min_browser, bool)
            or not isinstance(raw_min_browser, (int, float))
            or raw_min_browser < 0
        ):
            errors.append(
                "video_style.min_browser_length_ms: expected a number of milliseconds"
            )
        else:
            min_browser_ms = float(raw_min_browser)
    if raw_max_browser is not None:
        if (
            isinstance(raw_max_browser, bool)
            or not isinstance(raw_max_browser, (int, float))
            or raw_max_browser < 0
        ):
            errors.append(
                "video_style.max_browser_length_ms: expected a number of milliseconds"
            )
        else:
            max_browser_ms = float(raw_max_browser)
    if (
        min_browser_ms is not None
        and max_browser_ms is not None
        and max_browser_ms < min_browser_ms
    ):
        errors.append(
            "video_style.max_browser_length_ms: expected a number at or above "
            "min_browser_length_ms"
        )

    browser_layers: dict[str, list[dict]] = {}
    for scene in scenes:
        for card in scene["cards"]:
            if card["type"] != "browser":
                continue
            browser_layers.setdefault(card["source"], []).append(card)

    if browser_jobs and video_style.get("browser_enabled") is not True:
        for name in browser_jobs:
            errors.append(f"sources.{name}: video_style.browser_enabled is not true")

    for name, job in browser_jobs.items():
        group = browser_layers.get(name) or []
        if not group:
            errors.append(f"sources.{name}: a browser recording must be a layer")
            continue
        if any(card["start"] is None or card["end"] is None for card in group):
            continue
        group.sort(key=lambda card: card["start"])
        for earlier, later in zip(group, group[1:]):
            if later["start"] < earlier["end"] - tolerance:
                errors.append(f"sources.{name}: browser recording layers overlap")
            elif later["start"] - earlier["end"] > tolerance:
                errors.append(
                    f"sources.{name}: browser recording layers have a gap. "
                    "A later moment on the page is a new browser recording"
                )
            if earlier["frame"] != later["frame"]:
                errors.append(f"sources.{name}: browser recording layers use different frames")
        span = group[-1]["end"] - group[0]["start"]
        span_ms = span * 1000
        if min_browser_ms is not None and span_ms + tolerance * 1000 < min_browser_ms:
            errors.append(
                f"sources.{name}: recording is {span_ms:.0f}ms, "
                f"under min_browser_length_ms {min_browser_ms:.0f}"
            )
        if max_browser_ms is not None and span_ms - tolerance * 1000 > max_browser_ms:
            errors.append(
                f"sources.{name}: recording is {span_ms:.0f}ms, "
                f"over max_browser_length_ms {max_browser_ms:.0f}"
            )
        ordered = sorted(
            [action for action in job if action.get("at") is not None],
            key=lambda action: action["at"],
        )
        if (
            not ordered
            or ordered[0]["type"] != "open"
            or ordered[0]["at"] is None
            or abs(ordered[0]["at"]) > tolerance
        ):
            errors.append(
                f"sources.{name}.actions: the first action is open at 00:00:00.00"
            )
        for index, action in enumerate(ordered):
            if action["at"] < -tolerance or action["at"] > span + tolerance:
                errors.append(
                    f"sources.{name}.actions: {action['type']} at "
                    f"{fmt_tc(action['at'])} is outside the recording"
                )
            if index + 1 < len(ordered):
                gap = ordered[index + 1]["at"] - action["at"]
            else:
                gap = span - action["at"]
            if (
                action["type"] in {"open", "scroll"}
                and index + 1 < len(ordered)
                and gap + tolerance < 0.8
            ):
                errors.append(
                    f"sources.{name}.actions: leave 0.8s after {action['type']} "
                    "before the next action"
                )
            if action["type"] == "highlight" and gap + tolerance < 0.8:
                errors.append(
                    f"sources.{name}.actions: leave the highlight up for at least 0.8s"
                )

    if errors:
        print(f"{len(errors)} problem(s) in {plan_path}:", file=sys.stderr)
        for message in errors:
            print(f"  {message}", file=sys.stderr)
        sys.exit(1)

    source_groups = plan.get("source_groups")
    if not isinstance(source_groups, dict):
        source_groups = {}

    sources = plan.get("sources")
    if not isinstance(sources, dict):
        sources = {}

    video_settings = plan.get("video_settings")
    if not isinstance(video_settings, dict):
        video_settings = {}

    return {
        "hash": plan_hash,
        "title": plan.get("title") or "",
        "description": plan.get("description") or "",
        "issues": issues,
        "runtime": edit_clock,
        "scenes": scenes,
        "source_groups": source_groups,
        "graphic_count": graphic_index,
        "browser_count": browser_index,
        "sources": sources,
        "video_settings": video_settings,
        "caption_style": plan.get("caption_style"),
        "srt_style": plan.get("srt_style"),
        "pip_style": plan.get("pip_style"),
        "grading_style": plan.get("grading_style"),
    }

    # ==================================================
    # Compile the cut list
    # ==================================================


def compile_timeline(plan_path: Path, tolerance: float = 0.011) -> dict:
    """Resolve `edit.json` into the cut list render and captions consume.

    `ranges` is one slice of the edit clock per stretch where the audio
    reference source and the full-frame footage are both constant.
    A range with no full-frame footage layer has no `active_source`.
    `graphics` resolves each graphic or browser layer to its rendered file.
    Consecutive layers that share a source and frame, with touching times, are
    one play of that file. A gap between graphic uses starts a new play.
    `pip` copies each plan window and the crop resolved for that cut.
    Any problem is printed to stderr and the process exits.
    """
    model = load_plan(plan_path, tolerance=tolerance)
    scenes = model["scenes"]
    sources = model["sources"]
    if not sources:
        sys.exit(f"{plan_path}: sources is required")

    video_settings = model["video_settings"]
    fps = float(video_settings["fps"]) if "fps" in video_settings else 30.0
    min_slice = 0.5 / fps
    eps = 1e-6
    errors: list[str] = []

    # ==============================
    # ranges
    # ==============================
    ranges: list[dict] = []

    for scene in scenes:
        for line in scene["lines"]:
            kept = line["kept"]
            active = line["active"]
            b0, b1 = line["start"], line["end"]

            if kept["audio_source"] not in sources:
                errors.append(
                    f"{kept['path']}.audio_source: {kept['audio_source']} "
                    "is missing from sources"
                )
            picture = active if isinstance(active, dict) else None
            if (
                picture is not None
                and picture["type"] == "footage"
                and picture["source"] not in sources
            ):
                errors.append(
                    f"{picture['path']}.source: {picture['source']} is missing from sources"
                )

                # Cut every boundary that changes either the audio or the picture
            bounds = {b0, b1}
            for cut in kept["cuts"]:
                bounds.add(cut["edit_start"])
                bounds.add(cut["edit_end"])
            if picture is not None and picture["type"] == "footage":
                for cut in picture["cuts"]:
                    for edge in (cut["edit_start"], cut["edit_end"]):
                        if b0 - eps < edge < b1 + eps:
                            bounds.add(edge)

            edges = [b0]
            for t in sorted(bounds):
                if b0 - eps <= t <= b1 + eps and t - edges[-1] > min_slice:
                    edges.append(t)
            if len(edges) == 1:
                edges.append(b1)
            elif abs(edges[-1] - b1) > eps:
                edges[-1] = b1

            for t0, t1 in zip(edges, edges[1:]):
                mid = (t0 + t1) / 2

                kept_cut = next(
                    (
                        c
                        for c in kept["cuts"]
                        if c["edit_start"] - eps <= mid <= c["edit_end"] + eps
                    ),
                    None,
                )
                if kept_cut is None:
                    errors.append(
                        f"{line['path']}: no kept_take cut covers the edit clock at "
                        f"{fmt_tc(mid)}"
                    )
                    continue

                start = kept_cut["start"] + (t0 - kept_cut["edit_start"])
                entry = {
                    "audio_source": kept["audio_source"],
                    "start": round(start, 6),
                    "end": round(start + (t1 - t0), 6),
                }

                if picture is not None and picture["type"] == "footage":
                    active_cut = next(
                        (
                            c
                            for c in picture["cuts"]
                            if c["edit_start"] - eps <= mid <= c["edit_end"] + eps
                        ),
                        None,
                    )
                    if active_cut is None:
                        errors.append(
                            f"{picture['path']}: no cut covers the edit clock at "
                            f"{fmt_tc(mid)}"
                        )
                        continue
                    active_start = active_cut["start"] + (t0 - active_cut["edit_start"])
                    entry["active_source"] = picture["source"]
                    crop = active_cut.get("crop")
                    if isinstance(crop, dict):
                        entry["crop"] = {k: crop[k] for k in ("x", "y", "w", "h")}
                    if (
                        picture["source"] != kept["audio_source"]
                        or abs(active_start - start) > eps
                    ):
                        entry["active_start"] = round(active_start, 6)

                ranges.append(entry)

                # ==============================
                # graphics
                # ==============================
    graphics: list[dict] = []

    for scene in scenes:
        for card in scene["cards"]:
            if card["type"] not in {"graphic", "browser"}:
                continue
            raw_source = card.get("source")
            if not isinstance(raw_source, str) or not raw_source.strip():
                errors.append(f"{card['path']}.source: required")
                continue
            record = sources.get(raw_source)
            raw_path = record.get("path") if isinstance(record, dict) else None
            if not isinstance(raw_path, str) or not raw_path.strip():
                errors.append(f"sources.{raw_source}.path: required")
                continue
            found = Path(raw_path)
            if not found.is_file():
                errors.append(f"sources.{raw_source}.path: {raw_path} is missing")
                continue
            frame = card["frame"]
            if card["type"] == "browser" and frame == "top":
                window = {"x": 0.0, "y": 0.0, "w": 1.0, "h": 0.5}
            elif card["type"] == "browser" and frame == "bottom":
                window = {"x": 0.0, "y": 0.5, "w": 1.0, "h": 0.5}
            elif isinstance(frame, dict):
                window = frame
            else:
                window = None
            graphics.append(
                {
                    "file": os.path.relpath(found, Path.cwd()),
                    "start": round(card["start"], 6),
                    "end": round(card["end"], 6),
                    "z": card["z"],
                    "place": "box" if window else "full",
                    "x": float(window["x"]) if window else None,
                    "y": float(window["y"]) if window else None,
                    "w": float(window["w"]) if window else None,
                    "h": float(window["h"]) if window else None,
                    "kind": card["type"],
                    "source": raw_source,
                }
            )

    merged_graphics: list[dict] = []
    open_run: dict[str, dict] = {}
    for item in graphics:
        previous = open_run.get(item["source"])
        same_frame = previous is not None and item["place"] == previous["place"] and all(
            item.get(key) == previous.get(key) for key in ("x", "y", "w", "h")
        )
        overlap = previous is not None and item["start"] + tolerance < previous["end"]
        gap = previous is not None and item["start"] - previous["end"] > tolerance
        touches = previous is not None and not overlap and not gap

        if item.get("kind") == "browser":
            if previous is None:
                merged_graphics.append(item)
                open_run[item["source"]] = item
                continue
            if overlap:
                errors.append(f"sources.{item['source']}: browser recording layers overlap")
                continue
            if gap:
                errors.append(
                    f"sources.{item['source']}: browser recording layers have a gap. "
                    "A later moment on the page is a new browser recording"
                )
                continue
            if not same_frame:
                errors.append(
                    f"sources.{item['source']}: browser recording layers use different frames"
                )
                continue
            previous["end"] = item["end"]
            continue

        if touches and same_frame:
            previous["end"] = item["end"]
            continue
        merged_graphics.append(item)
        open_run[item["source"]] = item
    graphics = merged_graphics

            # ==============================
            # pip
            # ==============================
    pip: list[dict] = []
    pip_style = model.get("pip_style")
    pip_enabled = isinstance(pip_style, dict)

    for scene in scenes:
        for card in scene["cards"]:
            place = card.get("frame")
            if card["type"] != "footage" or place == "full":
                continue
            if place == "pip" and not pip_enabled:
                errors.append(
                    f"{card['path']}: edit.json has pip but pip_style is missing"
                )
                continue
            if card["source"] not in sources:
                errors.append(
                    f"{card['path']}.source: {card['source']} is missing from sources"
                )
                continue

            pip.append(
                {
                    "source": card["source"],
                    "start": round(card["start"], 6),
                    "end": round(card["end"], 6),
                    "place": place,
                    "z": card["z"],
                    "cuts": [
                        {
                            "start": round(c["start"], 6),
                            "end": round(c["end"], 6),
                            "crop": c.get("crop"),
                        }
                        for c in card["cuts"]
                    ],
                }
            )

            # ==============================
            # Verify
            # ==============================
    total = sum(r["end"] - r["start"] for r in ranges)
    if abs(total - model["runtime"]) > tolerance:
        errors.append(
            f"ranges total {fmt_tc(total)} but the edit.json runtime is "
            f"{fmt_tc(model['runtime'])}"
        )

    if errors:
        print(f"{len(errors)} problem(s) compiling {plan_path.name}:", file=sys.stderr)
        for message in errors:
            print(f"  {message}", file=sys.stderr)
        sys.exit(1)

    if isinstance(model.get("grading_style"), str):
        print(
            f"warning: {plan_path.name} grading_style is "
            f"{model['grading_style']!r}, not a grading object - no grade will render",
            file=sys.stderr,
        )

    paths = {
        name: record["path"]
        for name, record in sources.items()
        if isinstance(record, dict) and isinstance(record.get("path"), str)
    }

    return {
        "sources": paths,
        "video_settings": video_settings,
        "caption_style": model["caption_style"],
        "srt_style": model["srt_style"],
        "pip_style": model["pip_style"],
        "grading_style": model["grading_style"],
        "ranges": ranges,
        "graphics": graphics,
        "pip": pip,
    }

"""Shared EDL + transcript → edit-clock caption cues.

Used by `build_srt.py` (sidecar `.srt` from `edl.srt_style` wrap settings) and
`render.py` (burn-in cues from caption-style wrap / case settings).

Each range's words come from `range.audio_source`. Range start/end are
already on that clip, so word times are used as-is.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

PUNCT_BREAK = set(".,!?;:")
ALLOWED_CASES = {"upper", "lower", "title", "normal"}


def build_timeline_srt(
    edl: dict,
    transcripts_dir: Path,
    out_path: Path,
    *,
    edit_dir: Path,
    chars_per_line: int,
    num_lines: int,
    caption_case: str = "normal",
    include_indices: set[int] | None = None,
) -> int:
    """Remap the audio-clip transcript onto the edit clock, wrap, apply case, write `.srt`.

    Returns the number of cues written.
    """
    if chars_per_line <= 0:
        sys.exit(f"chars_per_line must be > 0, got: {chars_per_line}")
    if num_lines <= 0:
        sys.exit(f"num_lines must be > 0, got: {num_lines}")
    if caption_case not in ALLOWED_CASES:
        sys.exit(
            f"caption_case must be one of {sorted(ALLOWED_CASES)}, "
            f"got: {caption_case!r}"
        )

    entries: list[tuple[float, float, str]] = []
    seg_offset = 0.0
    capitalize_next = True

    for i, r in enumerate(edl["ranges"]):
        audio_name = r.get("audio_source")
        if not audio_name:
            sys.exit(f"range[{i}] audio_source is required")
        audio_name = Path(str(audio_name)).stem
        seg_start = float(r["start"])
        seg_end = float(r["end"])
        seg_duration = seg_end - seg_start

        if include_indices is not None and i not in include_indices:
            seg_offset += seg_duration
            continue

        src_start = seg_start
        src_end = seg_end

        tr_path = transcripts_dir / f"{audio_name}.json"
        if not tr_path.exists():
            print(
                f"  no transcript for {audio_name}, "
                "skipping captions for this range"
            )
            seg_offset += seg_duration
            continue

        transcript = json.loads(tr_path.read_text())
        words_in_seg: list[dict] = []
        for w in transcript.get("words", []):
            if w.get("type") != "word":
                continue
            ws = w.get("start")
            we = w.get("end")
            if ws is None or we is None:
                continue
            if we <= src_start or ws >= src_end:
                continue
            words_in_seg.append(w)

        # Fill lines up to chars_per_line, pack up to num_lines per cue,
        # break early on punctuation.
        buffer: list[dict] = []

        for w in words_in_seg:
            text = (w.get("text") or "").strip()
            if not text:
                continue

            candidate = buffer + [w]
            cand_words = [(x.get("text") or "").strip() for x in candidate]
            wrapped: list[str] = []
            current = ""
            for word in cand_words:
                trial = word if not current else f"{current} {word}"
                if len(trial) <= chars_per_line:
                    current = trial
                else:
                    if current:
                        wrapped.append(current)
                    current = word
            if current:
                wrapped.append(current)

            ends_in_punct = text[-1] in PUNCT_BREAK

            if len(wrapped) > num_lines and buffer:
                emit_words = buffer
                buffer = [w]
            else:
                buffer = candidate
                emit_words = buffer if ends_in_punct else []
                if ends_in_punct:
                    buffer = []

            if not emit_words:
                continue

            local_start = max(src_start, emit_words[0].get("start", src_start))
            local_end = min(src_end, emit_words[-1].get("end", src_end))
            out_start = max(0.0, local_start - src_start) + seg_offset
            out_end = max(0.0, local_end - src_start) + seg_offset
            if out_end <= out_start:
                out_end = out_start + 0.4

            cue_words = [(x.get("text") or "").strip() for x in emit_words]
            cue_lines: list[str] = []
            current = ""
            for word in cue_words:
                trial = word if not current else f"{current} {word}"
                if len(trial) <= chars_per_line:
                    current = trial
                else:
                    if current:
                        cue_lines.append(current)
                    current = word
            if current:
                cue_lines.append(current)

            text_out = "\n".join(cue_lines)
            text_out = re.sub(r"[^\S\n]+", " ", text_out).strip()
            text_out = text_out.rstrip(",;:")
            text_out, capitalize_next = _apply_case(
                text_out, caption_case, capitalize_next
            )
            entries.append((out_start, out_end, text_out))

        if buffer:
            local_start = max(src_start, buffer[0].get("start", src_start))
            local_end = min(src_end, buffer[-1].get("end", src_end))
            out_start = max(0.0, local_start - src_start) + seg_offset
            out_end = max(0.0, local_end - src_start) + seg_offset
            if out_end <= out_start:
                out_end = out_start + 0.4

            cue_words = [(x.get("text") or "").strip() for x in buffer]
            cue_lines = []
            current = ""
            for word in cue_words:
                trial = word if not current else f"{current} {word}"
                if len(trial) <= chars_per_line:
                    current = trial
                else:
                    if current:
                        cue_lines.append(current)
                    current = word
            if current:
                cue_lines.append(current)

            text_out = "\n".join(cue_lines)
            text_out = re.sub(r"[^\S\n]+", " ", text_out).strip()
            text_out = text_out.rstrip(",;:")
            text_out, capitalize_next = _apply_case(
                text_out, caption_case, capitalize_next
            )
            entries.append((out_start, out_end, text_out))

        seg_offset += seg_duration

    entries.sort(key=lambda e: e[0])
    lines: list[str] = []
    for i, (a, b, t) in enumerate(entries, start=1):
        lines.append(str(i))
        lines.append(f"{_srt_timestamp(a)} --> {_srt_timestamp(b)}")
        lines.append(t)
        lines.append("")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines))
    return len(entries)


def _apply_case(
    text: str, caption_case: str, capitalize_next: bool
) -> tuple[str, bool]:
    if caption_case == "upper":
        return text.upper(), capitalize_next
    if caption_case == "lower":
        return text.lower(), capitalize_next
    if caption_case == "title":
        return text.title(), capitalize_next

    # normal — sentence case, carrying state across cues
    chars: list[str] = []
    for ch in text.lower():
        if capitalize_next and ch.isalpha():
            chars.append(ch.upper())
            capitalize_next = False
        else:
            chars.append(ch)
            if ch in ".!?":
                capitalize_next = True
    return "".join(chars), capitalize_next


def _srt_timestamp(seconds: float) -> str:
    total_ms = int(round(seconds * 1000))
    h, rem = divmod(total_ms, 3600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

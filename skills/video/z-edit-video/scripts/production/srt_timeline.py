"""Shared plan timeline + transcript → edit-clock caption cues.

Used by `build_srt.py` (sidecar `.srt` from `edit.json srt_style` wrap settings) and
`render.py` (burn-in cues from caption-style wrap / case settings).

Each range's words come from `range.audio_source`. Range start/end
are already on that source, so word times are used as-is. Stored cue times
are seconds on the edit clock:

    edit time = (audio-source time clamped to the range − range start) + range offset

The sidecar writer emits a SubRip file. The burn writer emits an Advanced
SubStation Alpha script, `edit/burn-captions.ass`. Word highlighting recolors
the spoken word inside a cue. The sidecar file never highlights words.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PUNCT_BREAK = set(".,!?;:")
SENTENCE_END = set(".!?")
MIN_SPLIT_WORDS = 3
ALLOWED_CASES = {"upper", "lower", "title", "normal"}


#==================================================
# Cue builder
#==================================================


def _line_count(texts: list[str], chars_per_line: int) -> int:
    lines = 0
    current = ""
    for word in texts:
        trial = word if not current else f"{current} {word}"
        if len(trial) <= chars_per_line:
            current = trial
        else:
            if current:
                lines += 1
            current = word
    if current:
        lines += 1
    return lines


def build_caption_cues(
    timeline: dict,
    transcripts_dir: Path,
    *,
    chars_per_line: int,
    num_lines: int,
    caption_case: str = "normal",
    include_indices: set[int] | None = None,
) -> list[dict]:
    """Remap audio-source words onto the edit clock and wrap them into cues.

    Each cue is `{start, end, lines}`. `lines` is the on-screen rows. Each row
    is the words on that row: `{text, start, end}`, with times on the edit clock.
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

    cues: list[dict] = []
    seg_offset = 0.0
    capitalize_next = True

    for i, r in enumerate(timeline["ranges"]):
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
            print(f"  no transcript for {audio_name}, skipping captions for this range")
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
        # and break on punctuation. A one- or two-word sentence ending is
        # pulled back when three words still fit on the next cue. A spilled
        # sentence ending closes before the next sentence when only one or
        # two words of that sentence fit beside it.
        pending: list[dict] = []
        for w in words_in_seg:
            text = (w.get("text") or "").strip()
            if text:
                pending.append(w)

        batches: list[list[dict]] = []
        buffer: list[dict] = []
        index = 0
        while index < len(pending):
            w = pending[index]
            text = (w.get("text") or "").strip()

            if buffer:
                previous = (buffer[-1].get("text") or "").strip()
                if previous and previous[-1] in SENTENCE_END:
                    sentence_end = index
                    while sentence_end + 1 < len(pending):
                        end_text = (pending[sentence_end].get("text") or "").strip()
                        if end_text and end_text[-1] in SENTENCE_END:
                            break
                        sentence_end += 1
                    sentence = pending[index : sentence_end + 1]
                    buffer_texts = [(word.get("text") or "").strip() for word in buffer]
                    fit = 0
                    for count in range(1, len(sentence) + 1):
                        sentence_texts = [
                            (word.get("text") or "").strip() for word in sentence[:count]
                        ]
                        if (
                            _line_count(buffer_texts + sentence_texts, chars_per_line)
                            <= num_lines
                        ):
                            fit = count
                        else:
                            break
                    if fit < len(sentence) and fit < MIN_SPLIT_WORDS:
                        batches.append(buffer)
                        buffer = []
                        continue

            candidate = buffer + [w]
            candidate_texts = [(word.get("text") or "").strip() for word in candidate]
            if _line_count(candidate_texts, chars_per_line) > num_lines and buffer:
                sentence_end = index
                while sentence_end + 1 < len(pending):
                    end_text = (pending[sentence_end].get("text") or "").strip()
                    if end_text and end_text[-1] in SENTENCE_END:
                        break
                    sentence_end += 1
                tail = pending[index : sentence_end + 1]
                pulled = False
                if len(tail) < MIN_SPLIT_WORDS:
                    need = MIN_SPLIT_WORDS - len(tail)
                    same_sentence = 0
                    for word in reversed(buffer):
                        word_text = (word.get("text") or "").strip()
                        if word_text and word_text[-1] in SENTENCE_END:
                            break
                        same_sentence += 1
                    if same_sentence >= need and len(buffer) - need >= MIN_SPLIT_WORDS:
                        group_texts = [
                            (word.get("text") or "").strip()
                            for word in buffer[-need:] + tail
                        ]
                        if _line_count(group_texts, chars_per_line) <= num_lines:
                            batches.append(buffer[:-need])
                            buffer = buffer[-need:] + [w]
                            index += 1
                            if text[-1] in PUNCT_BREAK and text[-1] not in SENTENCE_END:
                                batches.append(buffer)
                                buffer = []
                            pulled = True
                if not pulled:
                    batches.append(buffer)
                    buffer = [w]
                    index += 1
            else:
                buffer = candidate
                if text[-1] in PUNCT_BREAK:
                    batches.append(buffer)
                    buffer = []
                index += 1

        if buffer:
            batches.append(buffer)

        for emit_words in batches:
            timed: list[dict] = []
            for w in emit_words:
                text = (w.get("text") or "").strip()
                if not text:
                    continue
                raw_start = float(w.get("start", src_start))
                raw_end = float(w.get("end", src_end))
                clamped_start = min(src_end, max(src_start, raw_start))
                clamped_end = min(src_end, max(src_start, raw_end))
                edit_start = max(0.0, clamped_start - src_start) + seg_offset
                edit_end = max(0.0, clamped_end - src_start) + seg_offset
                if edit_end < edit_start:
                    edit_end = edit_start
                timed.append({"text": text, "start": edit_start, "end": edit_end})
            if not timed:
                continue

            raw_lines: list[list[dict]] = []
            current_words: list[dict] = []
            current = ""
            for word in timed:
                trial = word["text"] if not current else f"{current} {word['text']}"
                if len(trial) <= chars_per_line:
                    current = trial
                    current_words.append(word)
                else:
                    if current_words:
                        raw_lines.append(current_words)
                    current = word["text"]
                    current_words = [word]
            if current_words:
                raw_lines.append(current_words)

            while raw_lines and raw_lines[-1]:
                raw_lines[-1][-1]["text"] = raw_lines[-1][-1]["text"].rstrip(",;:")
                if raw_lines[-1][-1]["text"]:
                    break
                raw_lines[-1].pop()
                if not raw_lines[-1]:
                    raw_lines.pop()
            if not raw_lines:
                continue

            for line in raw_lines:
                for word in line:
                    word["text"], capitalize_next = _apply_case(
                        word["text"], caption_case, capitalize_next
                    )

            out_start = timed[0]["start"]
            out_end = timed[-1]["end"]
            if out_end <= out_start:
                out_end = out_start + 0.4

            cues.append({"start": out_start, "end": out_end, "lines": raw_lines})

        seg_offset += seg_duration

    cues.sort(key=lambda cue: cue["start"])
    return cues


def build_timeline_srt(
    timeline: dict,
    transcripts_dir: Path,
    out_path: Path,
    *,
    edit_dir: Path,
    chars_per_line: int,
    num_lines: int,
    caption_case: str = "normal",
    include_indices: set[int] | None = None,
) -> int:
    """Remap the audio-source transcript onto the edit clock, wrap, apply case, write `.srt`.

    Returns the number of cues written.
    """
    cues = build_caption_cues(
        timeline,
        transcripts_dir,
        chars_per_line=chars_per_line,
        num_lines=num_lines,
        caption_case=caption_case,
        include_indices=include_indices,
    )

    lines: list[str] = []
    for i, cue in enumerate(cues, start=1):
        text = "\n".join(
            " ".join(word["text"] for word in line) for line in cue["lines"]
        )
        lines.append(str(i))
        lines.append(f"{_srt_timestamp(cue['start'])} --> {_srt_timestamp(cue['end'])}")
        lines.append(text)
        lines.append("")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines))
    return len(cues)


def _apply_case(
    text: str, caption_case: str, capitalize_next: bool
) -> tuple[str, bool]:
    if caption_case == "upper":
        return text.upper(), capitalize_next
    if caption_case == "lower":
        return text.lower(), capitalize_next
    if caption_case == "title":
        return text.title(), capitalize_next

        # normal — sentence case, carrying state across cues.
        # Keep transcript casing (AI, iPhone); only capitalize sentence starts.
    chars: list[str] = []
    for ch in text:
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


#==================================================
# Burn-in writer
#==================================================


def write_ass(
    cues: list[dict],
    out_path: Path,
    caption_style: dict,
    play_res: tuple[int, int],
    *,
    highlight_word: int | None = None,
) -> int:
    """Write an Advanced SubStation Alpha script for the burn-in.

    With `word_highlight` off, one dialogue event covers each cue.
    With it on, one event covers each spoken word and only that word uses the
    highlight fields. `highlight_word` freezes one word of each cue for a
    still preview. `play_res` is the frame the script is burned onto.

    Returns the number of cues written.
    """
    play_w, play_h = play_res
    if play_w <= 0 or play_h <= 0:
        sys.exit(f"caption play resolution must be positive, got: {play_w}x{play_h}")

    highlight = _highlight_overrides(caption_style)
    word_highlight = bool(highlight)
    style_line, base = _ass_style_line(caption_style)
    events: list[str] = []

    for cue in cues:
        words = [word for line in cue["lines"] for word in line]
        if not words:
            continue

        if word_highlight and highlight_word is None:
            bounds = [_ass_centiseconds(word["start"]) for word in words]
            bounds.append(_ass_centiseconds(cue["end"]))
            for bi in range(1, len(bounds)):
                if bounds[bi] <= bounds[bi - 1]:
                    bounds[bi] = bounds[bi - 1] + 1
            for wi in range(len(words)):
                events.append(
                    _ass_dialogue(
                        bounds[wi],
                        bounds[wi + 1],
                        _ass_cue_text(cue, wi, base, highlight),
                    )
                )
        else:
            active = None
            if word_highlight:
                active = min(max(highlight_word or 0, 0), len(words) - 1)
            start_cs = _ass_centiseconds(cue["start"])
            end_cs = _ass_centiseconds(cue["end"])
            if end_cs <= start_cs:
                end_cs = start_cs + 1
            events.append(
                _ass_dialogue(
                    start_cs, end_cs, _ass_cue_text(cue, active, base, highlight)
                )
            )

    body = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {play_w}",
        f"PlayResY: {play_h}",
        "WrapStyle: 2",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        (
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
            "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
            "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
            "Alignment, MarginL, MarginR, MarginV, Encoding"
        ),
        style_line,
        "",
        "[Events]",
        (
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, "
            "Effect, Text"
        ),
        *events,
        "",
    ]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(body))
    return len(cues)


def _ass_style_line(caption_style: dict) -> tuple[str, dict]:
    # Defaults used when a caption style omits a typography key.
    values: dict[str, object] = {
        "font_name": "Helvetica",
        "font_size": 18,
        "bold": True,
        "italic": False,
        "underline": False,
        "strike_out": False,
        "spacing": 0,
        "angle": 0,
        "text_color": "FFFFFF",
        "stroke_color": "000000",
        "back_color": "000000",
        "border_style": 1,
        "stroke_thickness": 2,
        "shadow": 0,
        "alignment": 2,
        "margin_v": 90,
    }
    for key in values:
        if key in caption_style:
            values[key] = caption_style[key]

    bold = _ass_flag(values["bold"], "bold")
    italic = _ass_flag(values["italic"], "italic")
    underline = _ass_flag(values["underline"], "underline")
    strike_out = _ass_flag(values["strike_out"], "strike_out")
    text_color = _ass_color(values["text_color"], "text_color")
    stroke_color = _ass_color(values["stroke_color"], "stroke_color")
    back_color = _ass_color(values["back_color"], "back_color")
    stroke_thickness = _ass_number(values["stroke_thickness"], "stroke_thickness")
    font_name = values["font_name"]
    if not isinstance(font_name, str) or not font_name.strip() or "," in font_name:
        sys.exit(f"caption style font_name must be a font name, got: {font_name!r}")

    fields = [
        "Caption",
        font_name,
        _ass_number(values["font_size"], "font_size"),
        text_color,
        text_color,
        stroke_color,
        back_color,
        bold,
        italic,
        underline,
        strike_out,
        "100",
        "100",
        _ass_number(values["spacing"], "spacing"),
        _ass_number(values["angle"], "angle"),
        _ass_number(values["border_style"], "border_style"),
        stroke_thickness,
        _ass_number(values["shadow"], "shadow"),
        _ass_number(values["alignment"], "alignment"),
        "10",
        "10",
        _ass_number(values["margin_v"], "margin_v"),
        "1",
    ]
    base = {
        "text_color": text_color,
        "stroke_color": stroke_color,
        "stroke_thickness": stroke_thickness,
        "bold": "1" if values["bold"] else "0",
    }
    return "Style: " + ",".join(fields), base


def _ass_flag(value: object, key: str) -> str:
    if not isinstance(value, bool):
        sys.exit(f"caption style {key} must be a boolean, got: {value!r}")
    return "-1" if value else "0"


def _ass_number(value: object, key: str) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        sys.exit(f"caption style {key} must be a number, got: {value!r}")
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _ass_color(value: object, key: str) -> str:
    if not isinstance(value, str):
        sys.exit(f"caption style {key} must be RRGGBB or &HAABBGGRR, got: {value!r}")
    if value.startswith("&H"):
        return value.upper()
    hex_rgb = value.removeprefix("#")
    if len(hex_rgb) != 6 or any(ch not in "0123456789abcdefABCDEF" for ch in hex_rgb):
        sys.exit(f"caption style {key} must be RRGGBB or &HAABBGGRR, got: {value!r}")
    return f"&H00{hex_rgb[4:6]}{hex_rgb[2:4]}{hex_rgb[0:2]}".upper()


def _ass_centiseconds(seconds: float) -> int:
    return max(0, int(round(seconds * 100)))


def _ass_timestamp(centiseconds: int) -> str:
    h, rem = divmod(centiseconds, 360_000)
    m, rem = divmod(rem, 6_000)
    s, cs = divmod(rem, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _ass_dialogue(start_cs: int, end_cs: int, text: str) -> str:
    return (
        f"Dialogue: 0,{_ass_timestamp(start_cs)},{_ass_timestamp(end_cs)},"
        f"Caption,,0,0,0,,{text}"
    )


def _highlight_overrides(caption_style: dict) -> dict:
    word_highlight = caption_style.get("word_highlight", False)
    if not isinstance(word_highlight, bool):
        sys.exit(
            f"caption style word_highlight must be a boolean, got: {word_highlight!r}"
        )
    if not word_highlight:
        return {}

    fields = (
        "highlight_text_color",
        "highlight_stroke_color",
        "highlight_stroke_thickness",
        "highlight_zoom",
        "highlight_bold",
    )
    if not any(field in caption_style for field in fields):
        sys.exit(
            "caption style word_highlight requires one of "
            "highlight_text_color, highlight_stroke_color, "
            "highlight_stroke_thickness, highlight_zoom, highlight_bold"
        )

    overrides: dict[str, str] = {}
    if "highlight_text_color" in caption_style:
        overrides["text_color"] = _ass_color(
            caption_style.get("highlight_text_color"), "highlight_text_color"
        )
    if "highlight_stroke_color" in caption_style:
        overrides["stroke_color"] = _ass_color(
            caption_style.get("highlight_stroke_color"), "highlight_stroke_color"
        )
    if "highlight_stroke_thickness" in caption_style:
        thickness = caption_style.get("highlight_stroke_thickness")
        if isinstance(thickness, bool) or not isinstance(thickness, (int, float)):
            sys.exit(
                "caption style highlight_stroke_thickness must be a number, "
                f"got: {thickness!r}"
            )
        if thickness < 0:
            sys.exit(
                "caption style highlight_stroke_thickness must be >= 0, "
                f"got: {thickness!r}"
            )
        overrides["stroke_thickness"] = _ass_number(
            thickness, "highlight_stroke_thickness"
        )
    if "highlight_bold" in caption_style:
        bold = caption_style.get("highlight_bold")
        if not isinstance(bold, bool):
            sys.exit(
                f"caption style highlight_bold must be a boolean, got: {bold!r}"
            )
        overrides["bold"] = "1" if bold else "0"
    if "highlight_zoom" in caption_style:
        zoom = caption_style.get("highlight_zoom")
        if isinstance(zoom, bool) or not isinstance(zoom, (int, float)):
            sys.exit(f"caption style highlight_zoom must be a number, got: {zoom!r}")
        if zoom <= 0:
            sys.exit(f"caption style highlight_zoom must be > 0, got: {zoom!r}")
        overrides["zoom"] = str(int(round(float(zoom) * 100)))
    return overrides


def _ass_cue_text(
    cue: dict, active: int | None, base: dict, highlight: dict
) -> str:
    open_tags: list[str] = []
    close_tags: list[str] = []
    if "text_color" in highlight:
        open_tags.append(f"\\c{highlight['text_color']}&")
        close_tags.append(f"\\c{base['text_color']}&")
    if "stroke_color" in highlight:
        open_tags.append(f"\\3c{highlight['stroke_color']}&")
        close_tags.append(f"\\3c{base['stroke_color']}&")
    if "stroke_thickness" in highlight:
        open_tags.append(f"\\bord{highlight['stroke_thickness']}")
        close_tags.append(f"\\bord{base['stroke_thickness']}")
    if "bold" in highlight:
        open_tags.append(f"\\b{highlight['bold']}")
        close_tags.append(f"\\b{base['bold']}")
    if "zoom" in highlight:
        open_tags.append(f"\\fscx{highlight['zoom']}\\fscy{highlight['zoom']}")
        close_tags.append("\\fscx100\\fscy100")
    opening = "{" + "".join(open_tags) + "}" if open_tags else ""
    closing = "{" + "".join(close_tags) + "}" if close_tags else ""

    rendered: list[str] = []
    flat_index = 0
    for line in cue["lines"]:
        pieces: list[str] = []
        for word in line:
            text = (
                word["text"]
                .replace("\\", "\\\\")
                .replace("{", "\\{")
                .replace("}", "\\}")
                .replace("\n", " ")
            )
            if active is not None and flat_index == active and opening:
                text = f"{opening}{text}{closing}"
            pieces.append(text)
            flat_index += 1
        rendered.append(" ".join(pieces))
    return "\\N".join(rendered)

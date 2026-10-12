"""Pack all Scribe transcripts in edit/source-transcriptions/ into one readable markdown.

Groups word-level entries into phrase-level lines, breaking on any silence
>= 0.5s OR speaker change. Each phrase gets a [start-end] prefix. This is
the PRIMARY artifact the editor subagent reads to pick cuts — it fits one
hour of takes in a tenth the tokens of raw Scribe JSON and gives
word-boundary precision from text alone.

Output: edit/takes-packed.md in the working directory.

Usage:
    python scripts/transcription/pack_transcripts.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# ==================================================
# Constants
# ==================================================

# Silence length threshold to separate phrases
SILENCE_THRESHOLD_S = 0.5

# ==================================================
# Main
# ==================================================


def main() -> None:
    edit_dir = Path("edit").resolve()
    transcripts_dir = edit_dir / "source-transcriptions"
    if not transcripts_dir.is_dir():
        sys.exit(f"no source-transcriptions directory at {transcripts_dir}")

    json_files = sorted(transcripts_dir.glob("*.json"))
    if not json_files:
        sys.exit(f"no .json files in {transcripts_dir}")

    entries = [pack_one_file(p) for p in json_files]
    entries.sort(key=lambda e: (e[1] is None, e[1] if e[1] is not None else 0, e[0]))
    markdown = render_markdown(entries)

    out_path = edit_dir / "takes-packed.md"
    out_path.write_text(markdown, encoding="utf-8")

    total_phrases = sum(len(e[3]) for e in entries)
    total_duration = sum(e[2] for e in entries)
    kb = out_path.stat().st_size / 1024
    print(f"packed {len(entries)} transcripts → {out_path}")
    print(f"  {total_phrases} phrases, {format_duration(total_duration)} total runtime")
    print(f"  {kb:.1f} KB")

    # ==================================================
    # Utilities
    # ==================================================


def format_time(seconds: float) -> str:
    """Format a time in seconds as "NNN.NN" with fixed 6-char width for alignment."""
    return f"{seconds:06.2f}"


def format_duration(seconds: float) -> str:
    """Format a duration as "Ms" or "Mm SSs"."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    m = int(seconds // 60)
    s = seconds - m * 60
    return f"{m}m {s:04.1f}s"


def group_into_phrases(words: list[dict]) -> list[dict]:
    """Walk a Scribe word list, break into phrases on silence >= SILENCE_THRESHOLD_S
    OR speaker change. Returns list of {start, end, text, speaker_id}.

    Scribe `words` entries have types 'word', 'spacing', or 'audio_event'.
    We keep 'word' and 'audio_event' content in phrase text. 'spacing'
    entries carry the silence information via their start/end times.
    """
    phrases: list[dict] = []
    current_words: list[dict] = []
    current_start: float | None = None
    current_speaker: str | None = None

    def flush() -> None:
        nonlocal current_words, current_start, current_speaker
        if not current_words:
            return
        text_parts: list[str] = []
        for w in current_words:
            t = w.get("type", "word")
            raw = (w.get("text") or "").strip()
            if not raw:
                continue
            if t == "audio_event":
                if not raw.startswith("("):
                    raw = f"({raw})"
            text_parts.append(raw)
        if not text_parts:
            current_words = []
            current_start = None
            current_speaker = None
            return
        text = " ".join(text_parts)
        text = (
            text.replace(" ,", ",")
            .replace(" .", ".")
            .replace(" ?", "?")
            .replace(" !", "!")
        )
        end_time = current_words[-1].get(
            "end", current_words[-1].get("start", current_start or 0.0)
        )
        phrases.append(
            {
                "start": current_start,
                "end": end_time,
                "text": text,
                "speaker_id": current_speaker,
            }
        )
        current_words = []
        current_start = None
        current_speaker = None

    prev_end: float | None = None

    for w in words:
        t = w.get("type", "word")
        if t == "spacing":
            # spacing entries mark the gaps between words; if the gap is long,
            # flush the current phrase.
            start = w.get("start")
            end = w.get("end")
            if start is not None and end is not None:
                gap = end - start
                if gap >= SILENCE_THRESHOLD_S:
                    flush()
            continue

            # 'word' or 'audio_event'
        start = w.get("start")
        if start is None:
            continue
        speaker = w.get("speaker_id")

        # Flush on speaker change
        if (
            current_speaker is not None
            and speaker is not None
            and speaker != current_speaker
        ):
            flush()

            # Flush on a long gap from the previous kept token
        if prev_end is not None and start - prev_end >= SILENCE_THRESHOLD_S:
            flush()

        if current_start is None:
            current_start = start
            current_speaker = speaker
        current_words.append(w)
        prev_end = w.get("end", start)

    flush()
    return phrases


def pack_one_file(json_path: Path) -> tuple[str, int | None, float, list[dict]]:
    """Return (header_name, source group, duration, phrases) for one transcript file."""
    data = json.loads(json_path.read_text())
    words = data.get("words", [])
    phrases = group_into_phrases(words)
    if phrases:
        duration = phrases[-1]["end"] - phrases[0]["start"]
    else:
        duration = 0.0

    prefix = json_path.stem.split("-", 1)[0]
    source_group = int(prefix) if prefix.isdigit() else None
    return json_path.stem, source_group, duration, phrases


def render_markdown(entries: list[tuple[str, int | None, float, list[dict]]]) -> str:
    lines: list[str] = []
    lines.append("# Packed transcripts")
    lines.append("")
    lines.append(
        f"Phrase-level, grouped on silences ≥ {SILENCE_THRESHOLD_S:.1f}s or speaker change."
    )
    lines.append("Use `[start-end]` ranges to address cuts in edit/edit.json.")
    lines.append("")
    for name, source_group, duration, phrases in entries:
        if source_group is not None:
            title = f"Source Group {source_group} — {name}"
        else:
            title = name

        lines.append(
            f"## {title}  (duration: {format_duration(duration)}, {len(phrases)} phrases)"
        )
        if not phrases:
            lines.append("  _no speech detected_")
            lines.append("")
            continue
        for p in phrases:
            spk = p.get("speaker_id")
            if spk is not None:
                # Scribe returns IDs like "speaker_0" — strip the prefix for readability
                spk_str = str(spk)
                if spk_str.startswith("speaker_"):
                    spk_str = spk_str[len("speaker_") :]
                spk_tag = f" S{spk_str}"
            else:
                spk_tag = ""
            lines.append(
                f"  [{format_time(p['start'])}-{format_time(p['end'])}]{spk_tag} {p['text']}"
            )
        lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    main()

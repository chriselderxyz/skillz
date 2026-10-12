"""Repair impossible word timings in each audio source's Scribe transcript.

Flags zero-length words, single words lasting seconds, and words stretching
across a silence in edit/silences.json. Each flagged stretch runs from the
last good word before it to the first good word after it. The speech in that
stretch is split at the silences inside it, each piece is re-transcribed on
its own, and the new words replace the old ones in
edit/source-transcriptions/<name>.json.

The raw transcript is kept in edit/source-transcriptions-original/<name>.json.
A repaired transcript carries `timing_repairs` and is skipped on rerun.

Usage:
    python scripts/transcription/repair_timings.py
    python scripts/transcription/repair_timings.py --workers 4
"""

from __future__ import annotations

import argparse
import bisect
import json
import subprocess
import sys
import tempfile
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from transcribe import call_scribe, load_api_key

# ==================================================
# Constants
# ==================================================

# Words shorter than this are zero-length
MIN_WORD_S = 0.02
# Single words longer than this are stretched
MAX_WORD_S = 1.5
# Silent overlap that flags a word sitting mostly in silence
SILENT_PART_S = 0.25
# Slack on silence and stretch edges
EDGE_TOL_S = 0.05
# Silence kept on each side of a snippet
SNIPPET_PAD_S = 0.25


# ==================================================
# Main
# ==================================================


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Re-transcribe stretches with impossible word timings"
    )
    ap.add_argument(
        "--workers", type=int, default=4, help="Parallel workers (default: 4)"
    )
    args = ap.parse_args()

    edit_dir = Path("edit").resolve()
    plan_path = edit_dir / "edit.json"
    if not plan_path.exists():
        sys.exit(f"edit.json not found: {plan_path}")
    silences_path = edit_dir / "silences.json"
    if not silences_path.exists():
        sys.exit(f"silences.json not found: {silences_path}")

    plan = json.loads(plan_path.read_text())
    plan_sources = plan.get("sources")
    if not isinstance(plan_sources, dict) or not plan_sources:
        sys.exit("edit.json sources is required")
    source_groups = plan.get("source_groups")
    if not isinstance(source_groups, dict) or not source_groups:
        sys.exit("edit.json source_groups is required")
    silence_map = json.loads(silences_path.read_text()).get("sources") or {}

    transcripts_dir = edit_dir / "source-transcriptions"
    originals_dir = edit_dir / "source-transcriptions-original"
    cwd = Path.cwd()

    audio_names: list[str] = []
    for group_id in sorted(
        source_groups,
        key=lambda k: (0, int(k)) if str(k).isdigit() else (1, str(k)),
    ):
        info = source_groups[group_id]
        audio_source = info.get("audio_source") if isinstance(info, dict) else None
        if not isinstance(audio_source, str) or not audio_source.strip():
            continue
        name = Path(audio_source.strip()).stem
        if name not in audio_names:
            audio_names.append(name)

    # ==============================
    # Find flagged stretches
    # ==============================

    jobs: list[dict] = []
    for name in audio_names:
        transcript_path = transcripts_dir / f"{name}.json"
        if not transcript_path.exists():
            print(f"skip {name}: no transcript", file=sys.stderr)
            continue
        raw_text = transcript_path.read_text()
        data = json.loads(raw_text)
        if "timing_repairs" in data:
            print(f"{name}: already repaired")
            continue

        record = plan_sources.get(name)
        raw_path = record.get("path") if isinstance(record, dict) else record
        if not raw_path:
            print(f"skip {name}: no path in sources", file=sys.stderr)
            continue
        source_path = Path(str(raw_path))
        if not source_path.is_absolute():
            source_path = cwd / source_path
        if not source_path.exists():
            print(f"skip missing source: {name} ({source_path})", file=sys.stderr)
            continue

        words = data.get("words") or []
        silences = sorted(
            (
                {"start": float(s["start"]), "end": float(s["end"])}
                for s in silence_map.get(name) or []
            ),
            key=lambda s: s["start"],
        )
        duration = probe_duration(source_path)
        if duration <= 0:
            duration = max((float(t["end"]) for t in words if timed(t)), default=0.0)

        stretches = find_stretches(words, silences, duration)
        windows = build_windows(stretches, speech_segments(silences, duration))
        flagged = sum(len(s["bad"]) for s in stretches)
        print(f"{name}: {flagged} flagged words in {len(windows)} stretches")
        jobs.append(
            {
                "name": name,
                "path": transcript_path,
                "raw_text": raw_text,
                "data": data,
                "source_path": source_path,
                "silences": silences,
                "windows": windows,
            }
        )

    # ==============================
    # Re-transcribe snippets
    # ==============================

    tasks = [
        (j, w, k)
        for j, job in enumerate(jobs)
        for w, window in enumerate(job["windows"])
        for k in range(len(window["snippets"]))
    ]
    results: dict[tuple[int, int, int], list[dict]] = {}
    failed: dict[int, str] = {}
    if tasks:
        api_key = load_api_key()
        print(f"re-transcribing {len(tasks)} snippets with {args.workers} workers")
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {}
            for j, w, k in tasks:
                job = jobs[j]
                start, end = job["windows"][w]["snippets"][k]
                futures[
                    pool.submit(
                        transcribe_snippet,
                        job["source_path"],
                        start,
                        end,
                        api_key,
                        job["data"].get("language_code"),
                    )
                ] = (j, w, k)
            for fut in as_completed(futures):
                j, w, k = futures[fut]
                try:
                    results[(j, w, k)] = fut.result()
                except Exception as e:
                    failed.setdefault(j, str(e))

    # ==============================
    # Splice and write
    # ==============================

    for j, job in enumerate(jobs):
        name = job["name"]
        if not job["windows"]:
            continue
        if j in failed:
            print(f"  x {name}  FAILED: {failed[j]}")
            continue

        words = job["data"].get("words") or []
        original = list(words)
        repairs: list[dict] = []
        for w, window in enumerate(job["windows"]):
            pieces = [
                map_speakers(results[(j, w, k)], original, window, snippet)
                for k, snippet in enumerate(window["snippets"])
            ]
            words, old_text, new_text = splice(words, window, pieces)
            repairs.append(
                {
                    "start": round(window["start"], 3),
                    "end": round(window["end"], 3),
                    "flags": window["flags"],
                    "snippets": len(window["snippets"]),
                    "old_text": old_text,
                    "new_text": new_text,
                }
            )

        originals_dir.mkdir(parents=True, exist_ok=True)
        (originals_dir / f"{name}.json").write_text(job["raw_text"])
        job["data"]["words"] = words
        job["data"]["text"] = "".join(t.get("text") or "" for t in words)
        job["data"]["timing_repairs"] = repairs
        job["path"].write_text(json.dumps(job["data"], indent=2))

        remaining = find_stretches(words, job["silences"], 0.0)
        left = sum(len(s["bad"]) for s in remaining)
        print(
            f"  + {name}: repaired {len(repairs)} stretches, "
            f"{left} flagged words remain"
        )

    if failed:
        sys.exit(1)


# ==================================================
# Utilities
# ==================================================


def timed(token: dict) -> bool:
    return token.get("start") is not None and token.get("end") is not None


def mid(token: dict) -> float:
    return (float(token["start"]) + float(token["end"])) / 2


def is_word(token: dict) -> bool:
    return (
        token.get("type", "word") == "word"
        and bool((token.get("text") or "").strip())
        and timed(token)
    )


def probe_duration(path: Path) -> float:
    proc = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True,
        text=True,
    )
    try:
        return float(proc.stdout.strip())
    except ValueError:
        return 0.0


def flag_word(token: dict, silences: list[dict], silence_ends: list[float]) -> list[str]:
    """Return the impossible-timing flags on one word."""
    start, end = float(token["start"]), float(token["end"])
    dur = end - start
    flags: list[str] = []
    if dur < MIN_WORD_S:
        flags.append("zero-length")
    elif dur > MAX_WORD_S:
        flags.append("too-long")

    silent = 0.0
    covers = False
    i = bisect.bisect_right(silence_ends, start)
    while i < len(silences) and silences[i]["start"] < end:
        s = silences[i]
        silent += min(end, s["end"]) - max(start, s["start"])
        if start <= s["start"] + EDGE_TOL_S and end >= s["end"] - EDGE_TOL_S:
            covers = True
        i += 1
    if covers or (silent >= SILENT_PART_S and silent > dur / 2):
        flags.append("across-silence")
    return flags


def find_stretches(
    words: list[dict], silences: list[dict], duration: float
) -> list[dict]:
    """Group consecutive flagged words, bounded by the good words around them."""
    silence_ends = [s["end"] for s in silences]
    tokens = [t for t in words if is_word(t)]
    flags = [flag_word(t, silences, silence_ends) for t in tokens]

    stretches: list[dict] = []
    k = 0
    while k < len(tokens):
        if not flags[k]:
            k += 1
            continue
        j = k
        while j + 1 < len(tokens) and flags[j + 1]:
            j += 1
        bad = tokens[k : j + 1]
        prev_end = float(tokens[k - 1]["end"]) if k > 0 else 0.0
        next_start = float(tokens[j + 1]["start"]) if j + 1 < len(tokens) else duration
        stretches.append(
            {
                "start": min([prev_end] + [float(t["start"]) for t in bad]),
                "end": max([next_start] + [float(t["end"]) for t in bad]),
                "bad": bad,
                "flags": sorted({f for m in range(k, j + 1) for f in flags[m]}),
            }
        )
        k = j + 1
    return stretches


def speech_segments(silences: list[dict], duration: float) -> list[dict]:
    """Split the source into speech segments at each silence, with snippet padding."""
    segments: list[dict] = []
    cursor = 0.0
    gap_before = 0.0
    for s in silences:
        if s["start"] > cursor:
            segments.append(
                {
                    "start": cursor,
                    "end": s["start"],
                    "pad_before": gap_before,
                    "pad_after": s["end"] - s["start"],
                }
            )
        cursor = max(cursor, s["end"])
        gap_before = s["end"] - s["start"]
    if duration > cursor:
        segments.append(
            {"start": cursor, "end": duration, "pad_before": gap_before, "pad_after": 0.0}
        )
    for seg in segments:
        seg["audio_start"] = seg["start"] - min(SNIPPET_PAD_S, seg["pad_before"] / 2)
        seg["audio_end"] = seg["end"] + min(SNIPPET_PAD_S, seg["pad_after"] / 2)
    return segments


def build_windows(stretches: list[dict], segments: list[dict]) -> list[dict]:
    """Map each stretch onto the speech segments it covers, merging shared segments."""
    spans: list[tuple[int, int, dict]] = []
    for stretch in stretches:
        a, b = stretch["start"], stretch["end"]
        hits = [
            i
            for i, seg in enumerate(segments)
            if seg["start"] < b - EDGE_TOL_S and seg["end"] > a + EDGE_TOL_S
        ]
        if not hits:
            hits = [
                i
                for i, seg in enumerate(segments)
                if seg["start"] <= b and seg["end"] >= a
            ]
        if not hits and segments:
            centre = (a + b) / 2
            hits = [
                min(
                    range(len(segments)),
                    key=lambda i: min(
                        abs(segments[i]["start"] - centre),
                        abs(segments[i]["end"] - centre),
                    ),
                )
            ]
        if hits:
            spans.append((min(hits), max(hits), stretch))

    windows: list[dict] = []
    for first, last, stretch in sorted(spans, key=lambda s: s[0]):
        if windows and first <= windows[-1]["last"]:
            window = windows[-1]
            window["last"] = max(window["last"], last)
            window["bad"].extend(stretch["bad"])
            window["flags"] = sorted(set(window["flags"]) | set(stretch["flags"]))
            continue
        windows.append(
            {
                "first": first,
                "last": last,
                "bad": list(stretch["bad"]),
                "flags": list(stretch["flags"]),
            }
        )

    for window in windows:
        segs = segments[window["first"] : window["last"] + 1]
        window["snippets"] = [(seg["audio_start"], seg["audio_end"]) for seg in segs]
        window["start"] = segs[0]["audio_start"]
        window["end"] = segs[-1]["audio_end"]
    return windows


def transcribe_snippet(
    source_path: Path,
    start: float,
    end: float,
    api_key: str,
    language: str | None,
) -> list[dict]:
    """Transcribe one snippet and return its tokens on the audio source clock."""
    with tempfile.TemporaryDirectory() as tmp:
        audio = Path(tmp) / "snippet.wav"
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-ss",
                f"{start:.3f}",
                "-t",
                f"{end - start:.3f}",
                "-i",
                str(source_path),
                "-vn",
                "-ac",
                "1",
                "-ar",
                "16000",
                "-c:a",
                "pcm_s16le",
                str(audio),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        payload = call_scribe(audio, api_key, language)

    tokens: list[dict] = []
    for raw in payload.get("words") or []:
        token = dict(raw)
        for key in ("start", "end"):
            if token.get(key) is not None:
                token[key] = round(float(token[key]) + start, 3)
        tokens.append(token)
    return strip_spacing(tokens)


def map_speakers(
    tokens: list[dict],
    original: list[dict],
    window: dict,
    snippet: tuple[float, float],
) -> list[dict]:
    """Rename a snippet's speaker ids onto the original transcript's speakers."""
    labels = [t["speaker_id"] for t in tokens if t.get("speaker_id") is not None]
    if not labels:
        return tokens

    def ranked(pool: list[dict]) -> list[str]:
        counts = Counter(
            t["speaker_id"]
            for t in pool
            if t.get("type") != "spacing" and t.get("speaker_id") is not None
        )
        return [speaker for speaker, _ in counts.most_common()]

    in_snippet = [t for t in original if timed(t) and snippet[0] <= mid(t) <= snippet[1]]
    candidates: list[str] = []
    for pool in (in_snippet, window["bad"], original):
        for speaker in ranked(pool):
            if speaker not in candidates:
                candidates.append(speaker)
    if not candidates:
        return tokens

    mapping: dict[str, str] = {}
    for i, (label, _) in enumerate(Counter(labels).most_common()):
        mapping[label] = candidates[i] if i < len(candidates) else candidates[0]
    for token in tokens:
        if token.get("speaker_id") in mapping:
            token["speaker_id"] = mapping[token["speaker_id"]]
    return tokens


def strip_spacing(
    tokens: list[dict], lead: bool = True, trail: bool = True
) -> list[dict]:
    start, end = 0, len(tokens)
    while lead and start < end and tokens[start].get("type") == "spacing":
        start += 1
    while trail and end > start and tokens[end - 1].get("type") == "spacing":
        end -= 1
    return tokens[start:end]


def join(out: list[dict], tokens: list[dict]) -> None:
    """Append tokens to out with a spacing token across the seam."""
    if out and tokens:
        prev, nxt = out[-1], tokens[0]
        seam = float(prev.get("end") or prev.get("start") or 0.0)
        out.append(
            {
                "text": " ",
                "start": seam,
                "end": max(seam, float(nxt.get("start") or seam)),
                "type": "spacing",
                "speaker_id": prev.get("speaker_id"),
            }
        )
    out.extend(tokens)


def text_of(tokens: list[dict]) -> str:
    return " ".join(
        (t.get("text") or "").strip()
        for t in tokens
        if t.get("type") != "spacing" and (t.get("text") or "").strip()
    )


def splice(
    words: list[dict], window: dict, pieces: list[list[dict]]
) -> tuple[list[dict], str, str]:
    """Replace the window's tokens with the re-transcribed pieces."""
    bad_ids = {id(t) for t in window["bad"]}
    before: list[dict] = []
    dropped: list[dict] = []
    after: list[dict] = []
    passed = False
    for token in words:
        if id(token) in bad_ids or (
            timed(token) and window["start"] <= mid(token) <= window["end"]
        ):
            dropped.append(token)
        elif passed or (timed(token) and mid(token) > window["end"]):
            passed = True
            after.append(token)
        else:
            before.append(token)

    middle: list[dict] = []
    for piece in pieces:
        join(middle, strip_spacing(piece))

    out = strip_spacing(before, lead=False)
    join(out, middle)
    join(out, strip_spacing(after, trail=False))
    return out, text_of(dropped), text_of(middle)


if __name__ == "__main__":
    main()

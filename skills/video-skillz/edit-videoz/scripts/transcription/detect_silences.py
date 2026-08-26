"""Detect silences on EDL source clips with ffmpeg silencedetect.

Writes edit/silences.json — per-clip ranges at or above
video_type.silence_cut_threshold_ms. Silences that overlap or immediately
follow a Scribe audio_event are omitted.

Usage:
    python scripts/transcription/detect_silences.py
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

#==================================================
# Constants
#==================================================

NOISE_DB = -30
HOLD_AFTER_EVENT_S = 0.25

SILENCE_START_RE = re.compile(r"silence_start:\s*([0-9.]+)")
SILENCE_END_RE = re.compile(r"silence_end:\s*([0-9.]+)")


#==================================================
# Main
#==================================================

def main() -> None:
    edl_path = Path("edit").resolve() / "edl.json"
    if not edl_path.exists():
        sys.exit(f"edl not found: {edl_path}")

    edl = json.loads(edl_path.read_text())
    sources = edl.get("sources")
    if not isinstance(sources, dict) or not sources:
        sys.exit("edl.sources is required")

    video_type = edl.get("video_type")
    if not isinstance(video_type, dict):
        sys.exit("edl.video_type must be an object")
    if "silence_cut_threshold_ms" not in video_type:
        sys.exit("edl.video_type.silence_cut_threshold_ms is missing")

    threshold_s = int(video_type["silence_cut_threshold_ms"]) / 1000.0
    transcripts_dir = edl_path.parent / "clip_transcriptions"
    cwd = Path.cwd()
    clips: dict[str, list[dict]] = {}
    total = 0
    total_dur = 0.0

    for name, raw_path in sources.items():
        clip_path = Path(str(raw_path))
        if not clip_path.is_absolute():
            clip_path = cwd / clip_path
        if not clip_path.exists():
            print(f"skip missing source: {name} ({clip_path})", file=sys.stderr)
            continue

        proc = subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-nostats",
                "-i",
                str(clip_path),
                "-af",
                f"silencedetect=noise={NOISE_DB}dB:d={threshold_s}",
                "-vn",
                "-f",
                "null",
                "-",
            ],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            err = (proc.stderr or "").strip().splitlines()
            tail = err[-1] if err else f"exit {proc.returncode}"
            print(f"skip {name}: ffmpeg silencedetect failed ({tail})", file=sys.stderr)
            continue

        probe = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(clip_path),
            ],
            capture_output=True,
            text=True,
        )
        try:
            duration = float((probe.stdout or "").strip() or "0")
        except ValueError:
            duration = 0.0

        #==============================
        # Parse silencedetect + hold audio events
        #==============================
        events: list[tuple[float, float]] = []
        transcript_path = transcripts_dir / f"{name}.json"
        if transcript_path.exists():
            words = json.loads(transcript_path.read_text()).get("words") or []
            for w in words:
                if w.get("type") != "audio_event":
                    continue
                ws, we = w.get("start"), w.get("end")
                if ws is None or we is None:
                    continue
                events.append((float(ws), float(we)))

        silences: list[dict] = []
        start: float | None = None
        for line in (proc.stderr or "").splitlines():
            m_start = SILENCE_START_RE.search(line)
            if m_start:
                start = float(m_start.group(1))
                continue
            m_end = SILENCE_END_RE.search(line)
            if m_end and start is not None:
                end = float(m_end.group(1))
                silences.append({"start": start, "end": end, "duration": end - start})
                start = None
        if start is not None and duration > start:
            silences.append(
                {"start": start, "end": duration, "duration": duration - start}
            )

        kept: list[dict] = []
        for s in silences:
            if s["duration"] + 1e-9 < threshold_s:
                continue
            held = False
            for es, ee in events:
                if s["end"] > es and s["start"] < ee:
                    held = True
                    break
                if es <= s["start"] <= ee + HOLD_AFTER_EVENT_S:
                    held = True
                    break
            if held:
                continue
            kept.append(
                {
                    "start": round(s["start"], 3),
                    "end": round(s["end"], 3),
                    "duration": round(s["duration"], 3),
                }
            )

        clips[name] = kept
        total += len(kept)
        total_dur += sum(s["duration"] for s in kept)

    out_path = edl_path.parent / "silences.json"
    payload = {
        "noise_db": NOISE_DB,
        "threshold_ms": int(video_type["silence_cut_threshold_ms"]),
        "clips": clips,
    }
    out_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"silences ≥ {threshold_s:.3f}s → {out_path}")
    print(f"  {total} silences, {total_dur:.1f}s total")


if __name__ == "__main__":
    main()

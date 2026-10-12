"""Detect silences on each source group's audio source with ffmpeg silencedetect.

Probes each audio source and sets that source's silence floor from its levels.
Writes edit/silences.json. Each list is that audio source's own clock, at or
above video_style.silence_cut_threshold_ms. Silences that overlap or
immediately follow a Scribe audio_event are omitted.

Usage:
    python scripts/transcription/detect_silences.py
"""

from __future__ import annotations

import json
import math
import re
import subprocess
import sys
from pathlib import Path

# ==================================================
# Constants
# ==================================================

HOLD_AFTER_EVENT_S = 0.25
PROBE_WINDOW_S = 0.02

SILENCE_START_RE = re.compile(r"silence_start:\s*([0-9.]+)")
SILENCE_END_RE = re.compile(r"silence_end:\s*([0-9.]+)")
PEAK_RE = re.compile(r"Overall\.Peak_level=(-?inf|[+-]?\d+(?:\.\d+)?)", re.I)


# ==================================================
# Main
# ==================================================


def main() -> None:
    plan_path = Path("edit").resolve() / "edit.json"
    if not plan_path.exists():
        sys.exit(f"edit.json not found: {plan_path}")

    plan = json.loads(plan_path.read_text())
    plan_sources = plan.get("sources")
    if not isinstance(plan_sources, dict) or not plan_sources:
        sys.exit("edit.json sources is required")

    video_style = plan.get("video_style")
    if not isinstance(video_style, dict):
        sys.exit("edit.json video_style must be an object")
    if "silence_cut_threshold_ms" not in video_style:
        sys.exit("edit.json video_style.silence_cut_threshold_ms is missing")

    threshold_s = int(video_style["silence_cut_threshold_ms"]) / 1000.0
    transcripts_dir = plan_path.parent / "source-transcriptions"
    cwd = Path.cwd()
    silence_sources: dict[str, list[dict]] = {}
    noise_floors: dict[str, int] = {}
    total = 0
    total_dur = 0.0

    source_groups = plan.get("source_groups")
    if not isinstance(source_groups, dict) or not source_groups:
        sys.exit("edit.json source_groups is required")

    audio_names: list[str] = []
    for group_id in sorted(
        source_groups,
        key=lambda k: (0, int(k)) if str(k).isdigit() else (1, str(k)),
    ):
        info = source_groups[group_id]
        if not isinstance(info, dict):
            sys.exit(f"source group {group_id}: must be an object")
        audio_source = info.get("audio_source")
        if not isinstance(audio_source, str) or not audio_source.strip():
            print(f"skip source group {group_id}: no audio_source", file=sys.stderr)
            continue
        name = Path(audio_source.strip()).stem
        if name not in plan_sources:
            sys.exit(
                f"source group {group_id}: audio_source '{audio_source}' "
                "is missing from sources"
            )
        if name not in audio_names:
            audio_names.append(name)

    for name in audio_names:
        record = plan_sources[name]
        raw_path = record.get("path") if isinstance(record, dict) else record
        if not raw_path:
            continue
        source_path = Path(str(raw_path))
        if not source_path.is_absolute():
            source_path = cwd / source_path
        if not source_path.exists():
            print(f"skip missing source: {name} ({source_path})", file=sys.stderr)
            continue

        # ==============================
        # Probe silence floor
        # ==============================

        # 20ms peak levels across every channel. The floor sits just above a
        # room-tone cluster when one is separated from speech, and just under
        # the speech hump when the take has no separate room tone.
        probe = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "stream=codec_type,sample_rate",
                "-show_entries",
                "format=duration",
                "-of",
                "json",
                str(source_path),
            ],
            capture_output=True,
            text=True,
        )
        try:
            probed = json.loads(probe.stdout or "{}")
        except json.JSONDecodeError:
            probed = {}
        sample_rate = 0
        for stream in probed.get("streams") or []:
            if stream.get("codec_type") != "audio":
                continue
            try:
                sample_rate = int(stream.get("sample_rate") or 0)
            except (TypeError, ValueError):
                sample_rate = 0
            if sample_rate > 0:
                break
        try:
            duration = float((probed.get("format") or {}).get("duration") or 0)
        except (TypeError, ValueError):
            duration = 0.0
        if sample_rate <= 0:
            print(f"skip {name}: no audio stream to probe", file=sys.stderr)
            continue

        hop = max(1, int(round(sample_rate * PROBE_WINDOW_S)))
        level_proc = subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-nostats",
                "-i",
                str(source_path),
                "-vn",
                "-af",
                (
                    f"asetnsamples=n={hop}:p=0,"
                    "astats=metadata=1:reset=1:measure_perchannel=none:measure_overall=Peak_level,"
                    "ametadata=print:key=lavfi.astats.Overall.Peak_level:file=-"
                ),
                "-f",
                "null",
                "-",
            ],
            capture_output=True,
            text=True,
        )
        if level_proc.returncode != 0:
            err = (level_proc.stderr or "").strip().splitlines()
            tail = err[-1] if err else f"exit {level_proc.returncode}"
            print(f"skip {name}: audio probe failed ({tail})", file=sys.stderr)
            continue

        level_text = level_proc.stdout or ""
        if "Peak_level" not in level_text:
            level_text = level_proc.stderr or ""
        peaks: list[float] = []
        for line in level_text.splitlines():
            matched = PEAK_RE.search(line)
            if not matched:
                continue
            token = matched.group(1).lower()
            peaks.append(float("-inf") if token.endswith("inf") else float(token))

        finite = [level for level in peaks if math.isfinite(level) and level > -120]
        if len(finite) < 5:
            noise_db = -60
        else:
            bin_lo = -96
            nbins = 96
            hist = [0] * nbins
            for level in finite:
                idx = math.floor(level) - bin_lo
                if idx < 0:
                    idx = 0
                elif idx >= nbins:
                    idx = nbins - 1
                hist[idx] += 1

            kernel = (1, 2, 3, 2, 1)
            smooth = [0.0] * nbins
            for i in range(nbins):
                acc = 0.0
                weight = 0
                for k, kv in enumerate(kernel):
                    j = i + k - 2
                    if 0 <= j < nbins:
                        acc += hist[j] * kv
                        weight += kv
                smooth[i] = acc / weight if weight else 0.0

            min_mass = max(4, int(math.ceil(0.005 * len(finite))))
            maxima: list[int] = []
            i = 1
            while i < nbins - 1:
                if smooth[i] < smooth[i - 1] or smooth[i] < smooth[i + 1]:
                    i += 1
                    continue
                j = i
                while (
                    j + 1 < nbins - 1
                    and smooth[j + 1] == smooth[i]
                    and smooth[j + 1] >= smooth[j + 2]
                ):
                    j += 1
                mass = sum(hist[max(0, i - 2) : min(nbins, j + 3)])
                if mass >= min_mass:
                    maxima.append((i + j) // 2)
                i = j + 1

            if not maxima:
                speech_i = max(range(nbins), key=lambda k: smooth[k])
            else:
                speech_i = max(maxima)
            speech_db = bin_lo + speech_i + 0.5

            accepted: list[int] = []
            for candidate in maxima:
                if speech_i - candidate < 6:
                    continue
                rights = [m for m in maxima if m > candidate]
                nxt = min(rights) if rights else speech_i
                if nxt - candidate < 6:
                    continue
                if nxt <= candidate + 1:
                    valley_h = smooth[candidate]
                else:
                    valley_h = min(smooth[candidate + 1 : nxt])
                smaller = min(smooth[candidate], smooth[nxt])
                if smaller > 0 and valley_h <= 0.25 * smaller:
                    accepted.append(candidate)

            if not accepted:
                mode_h = smooth[speech_i]
                edge = 0
                for k in range(speech_i, -1, -1):
                    if smooth[k] < 0.10 * mode_h:
                        edge = k
                        break
                threshold = (bin_lo + edge) - 2.0
            else:
                noise_i = max(accepted)
                room_db = bin_lo + noise_i + 0.5
                cluster = [
                    level for level in finite if room_db - 6 <= level <= room_db + 6
                ]
                if len(cluster) < 4:
                    cluster = [level for level in finite if level <= room_db + 3]
                ordered = sorted(cluster)
                rank = (len(ordered) - 1) * 0.98
                lo = math.floor(rank)
                hi = math.ceil(rank)
                if lo == hi:
                    cover = ordered[lo]
                else:
                    frac = rank - lo
                    cover = ordered[lo] * (1 - frac) + ordered[hi] * frac
                cover += 2.5
                speech_windows = [
                    level for level in finite if level >= speech_db - 8
                ]
                ordered = sorted(speech_windows)
                rank = (len(ordered) - 1) * 0.10
                lo = math.floor(rank)
                hi = math.ceil(rank)
                if lo == hi:
                    speech_quiet = ordered[lo]
                else:
                    frac = rank - lo
                    speech_quiet = ordered[lo] * (1 - frac) + ordered[hi] * frac
                threshold = min(cover, speech_quiet - 6.0)

            speech_limit = speech_db - 8.0
            threshold = min(max(threshold, -60.0), speech_limit)
            noise_db = int(math.floor(threshold + 0.5))
            if noise_db > speech_limit:
                noise_db = int(math.floor(speech_limit))

        print(f"{name}: silence floor {noise_db} dB")

        proc = subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-nostats",
                "-i",
                str(source_path),
                "-af",
                f"silencedetect=noise={noise_db}dB:d={threshold_s}",
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

        # ==============================
        # Parse silencedetect + hold audio events
        # ==============================

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

        silence_sources[name] = kept
        noise_floors[name] = noise_db
        total += len(kept)
        total_dur += sum(s["duration"] for s in kept)

    out_path = plan_path.parent / "silences.json"
    payload = {
        "noise_db": noise_floors,
        "threshold_ms": int(video_style["silence_cut_threshold_ms"]),
        "sources": silence_sources,
    }
    out_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"silences ≥ {threshold_s:.3f}s → {out_path}")
    print(f"  {total} silences, {total_dur:.1f}s total")


if __name__ == "__main__":
    main()

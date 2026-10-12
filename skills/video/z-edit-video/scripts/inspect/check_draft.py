"""Check a rendered video for problems at its joins and across the whole file.

Reads `edit/edit.json` and the rendered video. Prints one line per problem
with its edit clock time and the kept_take cut it falls in. Exits 1 when
anything is flagged.

  - duration   video and audio stream lengths against the edit.json runtime,
               and the audio start against the video start
  - click      a peak or sample jump at a join louder than anything near it
  - flash      1-2 frames that differ from both neighbors while the
               neighbors match each other
  - black      black frames with no graphic or browser layer up
  - freeze     frozen frames on a head layer with no graphic or browser up
  - dead air   silence longer than the cut padding and line gap allow

Joins are the range boundaries render.py splices, frame-snapped the same way.

Usage:
    python scripts/inspect/check_draft.py
    python scripts/inspect/check_draft.py edit/edit.mov
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "production"))

from plan_model import compile_timeline, fmt_tc, load_plan  # noqa: E402

# ==================================================
# Constants
# ==================================================

AUDIO_RATE = 48000
# Audio either side of a join that covers the render fades and frame snap
JOIN_WINDOW_S = 0.05
# Audio either side of a join the join is compared against
NEAR_WINDOW_S = 1.0
# A join peak this far over the loudest nearby audio is a click
CLICK_RATIO = 1.0
# Join peaks under this are too quiet to hear
CLICK_FLOOR = 0.001
# Frame size the flash check compares
FLASH_SIZE = (64, 36)
# Mean gray-level change into and out of a flash frame
FLASH_MIN_DIFF = 8.0
# The frames around a flash differ by under this share of the flash change
FLASH_RATIO = 0.5
BLACK_PIX_TH = 0.10
# Share of black pixels that makes a black frame, low enough to count a PIP over black
BLACK_PIC_TH = 0.90
FREEZE_NOISE_DB = -60
FREEZE_MIN_S = 0.5
# Silence allowed past the line gap and both cut paddings
DEAD_AIR_SLACK_S = 0.25
DEFAULT_NOISE_DB = -50

BLACK_RE = re.compile(r"black_start:([0-9.]+) black_end:([0-9.]+)")
FREEZE_START_RE = re.compile(r"freeze_start:\s*([0-9.]+)")
FREEZE_END_RE = re.compile(r"freeze_end:\s*([0-9.]+)")
SILENCE_START_RE = re.compile(r"silence_start:\s*(-?[0-9.]+)")
SILENCE_END_RE = re.compile(r"silence_end:\s*([0-9.]+)")


# ==================================================
# Main
# ==================================================


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Check a rendered video against edit/edit.json"
    )
    ap.add_argument(
        "video",
        nargs="?",
        type=Path,
        default=Path("edit/edit-draft.mp4"),
        help="Rendered video (default: edit/edit-draft.mp4)",
    )
    args = ap.parse_args()

    video = args.video
    if not video.is_file():
        sys.exit(f"video not found: {video}")
    edit_dir = Path("edit").resolve()
    plan_path = edit_dir / "edit.json"

    model = load_plan(plan_path)
    timeline = compile_timeline(plan_path)
    video_settings = model["video_settings"]
    fps = float(video_settings["fps"]) if "fps" in video_settings else 30.0
    video_style = json.loads(plan_path.read_text()).get("video_style") or {}

    cuts = [
        cut
        for scene in model["scenes"]
        for line in scene["lines"]
        for cut in line["kept"]["cuts"]
    ]
    cards = [
        card
        for scene in model["scenes"]
        for card in scene["cards"]
        if card["start"] is not None and card["end"] is not None
    ]

    def locate(t: float) -> str:
        for cut in cuts:
            if cut["edit_start"] <= t < cut["edit_end"]:
                return cut["path"]
        return cuts[-1]["path"] if cuts else ""

    def locate_span(t0: float, t1: float) -> str:
        first, last = locate(t0), locate(t1)
        return first if first == last else f"{first} → {last}"

    def unplaced(t0: float, t1: float) -> list[tuple[float, float]]:
        """Pieces of [t0, t1] with no graphic or browser layer up."""
        pieces = [(t0, t1)]
        for card in cards:
            if card["type"] not in {"graphic", "browser"}:
                continue
            kept: list[tuple[float, float]] = []
            for p0, p1 in pieces:
                if card["end"] <= p0 or card["start"] >= p1:
                    kept.append((p0, p1))
                    continue
                if p0 < card["start"]:
                    kept.append((p0, card["start"]))
                if card["end"] < p1:
                    kept.append((card["end"], p1))
            pieces = kept
        return [(p0, p1) for p0, p1 in pieces if p1 - p0 > 0.5 / fps]

    def head_up(t: float) -> bool:
        return any(
            card["type"] == "footage"
            and card["frame"] == "full"
            and card["source_type"] == "head"
            and card["start"] <= t < card["end"]
            for card in cards
        )

    # ==============================
    # Joins on the rendered clock
    # ==============================
    joins: list[float] = []
    accum_edit = 0.0
    accum_frames = 0
    for r in timeline["ranges"]:
        accum_edit += float(r["end"]) - float(r["start"])
        n_frames = max(1, int(round(accum_edit * fps)) - accum_frames)
        accum_frames += n_frames
        joins.append(accum_frames / fps)
    expected_s = joins.pop() if joins else 0.0

    problems: list[tuple[float, str]] = []

    # ==================================================
    # Duration and sync
    # ==================================================
    streams = probe_streams(video)
    v = next((s for s in streams if s.get("codec_type") == "video"), None)
    a = next((s for s in streams if s.get("codec_type") == "audio"), None)
    frame_s = 1.0 / fps
    if v is None:
        problems.append((0.0, "duration  no video stream"))
    else:
        v_dur = float(v.get("duration") or 0)
        if abs(v_dur - expected_s) > 1.5 * frame_s:
            problems.append(
                (
                    0.0,
                    f"duration  video is {v_dur:.3f}s, edit.json expects "
                    f"{expected_s:.3f}s",
                )
            )
    if a is None:
        problems.append((0.0, "duration  no audio stream"))
    elif v is not None:
        a_dur = float(a.get("duration") or 0)
        if abs(a_dur - v_dur) > 1.5 * frame_s:
            problems.append(
                (0.0, f"sync      audio is {a_dur:.3f}s, video is {v_dur:.3f}s")
            )
        a_start = float(a.get("start_time") or 0)
        v_start = float(v.get("start_time") or 0)
        if abs(a_start - v_start) > frame_s:
            problems.append(
                (
                    0.0,
                    f"sync      audio starts at {a_start:.3f}s, video starts at "
                    f"{v_start:.3f}s",
                )
            )

    # ==================================================
    # Video pass: black, freeze, flash
    # ==================================================
    w, h = FLASH_SIZE
    video_proc = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-nostats",
            "-i",
            str(video),
            "-an",
            "-filter_complex",
            (
                f"[0:v]split[a][b];"
                f"[a]blackdetect=d=0:pic_th={BLACK_PIC_TH}:pix_th={BLACK_PIX_TH},"
                f"freezedetect=n={FREEZE_NOISE_DB}dB:d={FREEZE_MIN_S},nullsink;"
                f"[b]scale={w}:{h}:flags=area,format=gray[v]"
            ),
            "-map",
            "[v]",
            "-f",
            "rawvideo",
            "-",
        ],
        capture_output=True,
    )
    if video_proc.returncode != 0:
        tail = video_proc.stderr.decode(errors="replace").strip().splitlines()[-1:]
        sys.exit(f"video pass failed: {tail}")
    video_log = video_proc.stderr.decode(errors="replace")

    for m in BLACK_RE.finditer(video_log):
        for t0, t1 in unplaced(float(m.group(1)), float(m.group(2))):
            problems.append(
                (t0, f"black     {t1 - t0:.2f}s  {locate_span(t0, t1 - 1e-3)}")
            )

    freeze_start: float | None = None
    for log_line in video_log.splitlines():
        m_start = FREEZE_START_RE.search(log_line)
        if m_start:
            freeze_start = float(m_start.group(1))
            continue
        m_end = FREEZE_END_RE.search(log_line)
        if m_end and freeze_start is not None:
            for t0, t1 in unplaced(freeze_start, float(m_end.group(1))):
                if t1 - t0 < FREEZE_MIN_S or not head_up((t0 + t1) / 2):
                    continue
                problems.append(
                    (t0, f"freeze    {t1 - t0:.2f}s  {locate_span(t0, t1 - 1e-3)}")
                )
            freeze_start = None

    frames = np.frombuffer(video_proc.stdout, dtype=np.uint8)
    n = frames.size // (w * h)
    frames = frames[: n * w * h].reshape(n, w * h).astype(np.int16)

    def diff(step: int) -> np.ndarray:
        return np.abs(frames[step:] - frames[:-step]).mean(axis=1)

    if n >= 4:
        d1 = diff(1)
        for run in (1, 2):
            # Change into the run's first frame and out of its last frame
            change = np.minimum(d1[: n - run - 1], d1[run : n - 1])
            across = diff(run + 1)
            flashes = (change > FLASH_MIN_DIFF) & (across < FLASH_RATIO * change)
            for i in np.flatnonzero(flashes) + 1:
                t = i / fps
                problems.append((t, f"flash     {run} frame(s)  {locate(t)}"))

    # ==================================================
    # Audio pass: dead air, click
    # ==================================================
    noise_db = DEFAULT_NOISE_DB
    silences_path = edit_dir / "silences.json"
    if silences_path.is_file():
        floors = json.loads(silences_path.read_text()).get("noise_db")
        if isinstance(floors, dict) and floors:
            noise_db = max(int(x) for x in floors.values())
        elif isinstance(floors, (int, float)):
            noise_db = int(floors)
    dead_air_s = (
        max(
            int(video_style.get("silence_cut_threshold_ms", 0)),
            int(video_style.get("line_gap_ms", 0)),
        )
        + 2 * int(video_style.get("cut_padding_ms", 0))
    ) / 1000.0 + DEAD_AIR_SLACK_S

    audio_proc = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-nostats",
            "-i",
            str(video),
            "-vn",
            "-af",
            f"silencedetect=n={noise_db}dB:d={dead_air_s:.3f}",
            "-ac",
            "1",
            "-ar",
            str(AUDIO_RATE),
            "-f",
            "s16le",
            "-",
        ],
        capture_output=True,
    )
    if audio_proc.returncode != 0 and a is not None:
        tail = audio_proc.stderr.decode(errors="replace").strip().splitlines()[-1:]
        sys.exit(f"audio pass failed: {tail}")
    audio_log = audio_proc.stderr.decode(errors="replace")

    silence_start: float | None = None
    for log_line in audio_log.splitlines():
        m_start = SILENCE_START_RE.search(log_line)
        if m_start:
            silence_start = max(0.0, float(m_start.group(1)))
            continue
        m_end = SILENCE_END_RE.search(log_line)
        if m_end and silence_start is not None:
            t0, t1 = silence_start, float(m_end.group(1))
            silence_start = None
            problems.append(
                (t0, f"dead air  {t1 - t0:.2f}s  {locate_span(t0, t1 - 1e-3)}")
            )

    samples = np.frombuffer(audio_proc.stdout, dtype=np.int16) / 32768.0
    for t in joins:
        j0 = int((t - JOIN_WINDOW_S) * AUDIO_RATE)
        j1 = int((t + JOIN_WINDOW_S) * AUDIO_RATE)
        n0 = max(0, int((t - NEAR_WINDOW_S) * AUDIO_RATE))
        n1 = min(samples.size, int((t + NEAR_WINDOW_S) * AUDIO_RATE))
        if j0 - n0 < 2 or n1 - j1 < 2:
            continue
        before, join, after = samples[n0:j0], samples[j0:j1], samples[j1:n1]
        join_peak = np.abs(join).max()
        if join_peak < CLICK_FLOOR:
            continue
        near_peak = max(np.abs(before).max(), np.abs(after).max())
        join_step = np.abs(np.diff(join)).max()
        near_step = max(np.abs(np.diff(before)).max(), np.abs(np.diff(after)).max())
        ratio = max(join_peak / max(near_peak, 1e-9), join_step / max(near_step, 1e-9))
        if ratio > CLICK_RATIO:
            problems.append(
                (
                    t,
                    f"click     {20 * np.log10(ratio):+.1f}dB over nearby audio  "
                    f"{locate_span(t - 0.02, t + 0.02)}",
                )
            )

    # ==================================================
    # Report
    # ==================================================
    if not problems:
        print(f"no problems in {video}")
        return
    problems.sort(key=lambda p: p[0])
    print(f"{len(problems)} problem(s) in {video}:")
    for t, message in problems:
        print(f"  {fmt_tc(t)}  {message}")
    sys.exit(1)


# ==================================================
# Utilities
# ==================================================


def probe_streams(path: Path) -> list[dict]:
    proc = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "stream=codec_type,duration,start_time",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        text=True,
    )
    try:
        return json.loads(proc.stdout or "{}").get("streams") or []
    except json.JSONDecodeError:
        return []


if __name__ == "__main__":
    main()

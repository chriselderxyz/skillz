"""Batch-transcribe one source per source group with 4 parallel workers.

Walks <videos_dir> for video and audio files named <n>-<type>.
Files without a number are skipped. One source per source group:
`audio_source` from that source group in `edit/edit.json`. Writes
transcripts to `edit/source-transcriptions/<name>.json` in the working
directory.

Cached per-file: any source that already has a transcript is skipped.

Usage:
    python scripts/transcription/transcribe_batch.py <videos_dir>
    python scripts/transcription/transcribe_batch.py <videos_dir> --workers 4
    python scripts/transcription/transcribe_batch.py <videos_dir> --num-speakers 2
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from transcribe import load_api_key, transcribe_one


# ==================================================
# Constants
# ==================================================

SOURCE_EXTS = {
    ".mp4",
    ".mov",
    ".mkv",
    ".avi",
    ".m4v",
    ".wav",
    ".mp3",
    ".m4a",
    ".aac",
    ".flac",
    ".aiff",
    ".aif",
    ".ogg",
    ".opus",
}


# ==================================================
# Main
# ==================================================


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Parallel transcription of one source per source group"
    )
    ap.add_argument(
        "videos_dir", type=Path, help="Directory containing the sources"
    )
    ap.add_argument(
        "--workers", type=int, default=4, help="Parallel workers (default: 4)"
    )
    ap.add_argument(
        "--language",
        type=str,
        default=None,
        help="Optional ISO language code. Omit to auto-detect per file.",
    )
    ap.add_argument(
        "--num-speakers",
        type=int,
        default=None,
        help="Optional number of speakers. Improves diarization when known.",
    )
    args = ap.parse_args()

    videos_dir = args.videos_dir.resolve()
    if not videos_dir.is_dir():
        sys.exit(f"not a directory: {videos_dir}")

    edit_dir = Path("edit").resolve()
    (edit_dir / "source-transcriptions").mkdir(parents=True, exist_ok=True)

    sources = sorted(
        p
        for p in videos_dir.iterdir()
        if p.is_file() and p.suffix.lower() in SOURCE_EXTS
    )
    if not sources:
        sys.exit(f"no video or audio files found in {videos_dir}")

    by_source_group: dict[int, list[Path]] = {}
    unnumbered: list[Path] = []
    for source in sources:
        prefix = source.stem.split("-", 1)[0]
        if not prefix.isdigit():
            unnumbered.append(source)
            continue

        by_source_group.setdefault(int(prefix), []).append(source)

    if unnumbered:
        names = ", ".join(p.name for p in unnumbered)
        print(f"skip unnumbered sources: {names}")

    if not by_source_group:
        sys.exit(f"no numbered sources (expected <n>-<type>) in {videos_dir}")

    plan_path = edit_dir / "edit.json"
    if not plan_path.is_file():
        sys.exit(f"edit.json not found: {plan_path}")
    try:
        plan = json.loads(plan_path.read_text())
    except json.JSONDecodeError as e:
        sys.exit(f"invalid JSON in {plan_path}: {e}")
    if not isinstance(plan, dict):
        sys.exit(f"{plan_path} must be a JSON object")

    source_groups = plan.get("source_groups")
    if not isinstance(source_groups, dict) or not source_groups:
        sys.exit(f"{plan_path}: source_groups is required")

    selected: list[Path] = []
    select_errors: list[str] = []
    for n in sorted(by_source_group):
        group = by_source_group[n]
        info = source_groups.get(str(n))
        if not isinstance(info, dict):
            select_errors.append(f"source group {n}: missing from {plan_path}")
            continue

        audio_source = info.get("audio_source")
        if not audio_source:
            print(f"  source group {n}: skipped (no audio_source)")
            continue

        reference_stem = Path(str(audio_source)).stem
        matches = [c for c in group if c.stem == reference_stem]
        if not matches:
            have = ", ".join(c.stem for c in group)
            select_errors.append(
                f"source group {n}: audio_source '{audio_source}' "
                f"has no matching source (have: {have})"
            )
            continue

        if len(matches) > 1:
            names = ", ".join(c.name for c in matches)
            select_errors.append(
                f"source group {n}: audio_source '{audio_source}' "
                f"matches more than one source: {names}"
            )
            continue

        chosen = matches[0]
        print(f"  source group {n}: {chosen.name} (audio source)")
        selected.append(chosen)

    if select_errors:
        sys.exit("\n".join(select_errors))

    already_cached = [
        v
        for v in selected
        if (edit_dir / "source-transcriptions" / f"{v.stem}.json").exists()
    ]
    pending = [v for v in selected if v not in already_cached]

    print(
        f"found {len(selected)} sources "
        f"({len(already_cached)} cached, {len(pending)} to transcribe)"
    )
    if not pending:
        print("nothing to do")
        return

    api_key = load_api_key()

    print(f"transcribing {len(pending)} files with {args.workers} parallel workers")
    t0 = time.time()

    errors: list[tuple[Path, str]] = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(
                transcribe_one,
                video=v,
                edit_dir=edit_dir,
                api_key=api_key,
                language=args.language,
                num_speakers=args.num_speakers,
                verbose=False,
            ): v
            for v in pending
        }
        for fut in as_completed(futures):
            v = futures[fut]
            try:
                out = fut.result()
                print(f"  + {v.stem}  →  {out.name}")
            except Exception as e:
                errors.append((v, str(e)))
                print(f"  x {v.stem}  FAILED: {e}")

    dt = time.time() - t0
    print(f"\ndone in {dt:.1f}s")
    if errors:
        print(f"{len(errors)} failures:")
        for v, msg in errors:
            print(f"  {v.name}: {msg}")
        sys.exit(1)


if __name__ == "__main__":
    main()

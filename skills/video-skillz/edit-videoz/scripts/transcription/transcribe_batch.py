"""Batch-transcribe one clip per segment with 4 parallel workers.

Walks <videos_dir> for video and audio files named <n>-<type>.
One clip per segment: the only clip, or `audio_reference_clip` from
`edit/<n>/sync.json` when a segment has several. Writes transcripts to
`edit/clip_transcriptions/<name>.json` in the working directory.

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

CLIP_EXTS = {
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
        description="Parallel transcription of one clip per segment"
    )
    ap.add_argument("videos_dir", type=Path, help="Directory containing source clips")
    ap.add_argument("--workers", type=int, default=4, help="Parallel workers (default: 4)")
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
    (edit_dir / "clip_transcriptions").mkdir(parents=True, exist_ok=True)

    clips = sorted(
        p
        for p in videos_dir.iterdir()
        if p.is_file() and p.suffix.lower() in CLIP_EXTS
    )
    if not clips:
        sys.exit(f"no video or audio files found in {videos_dir}")

    by_segment: dict[int, list[Path]] = {}
    unnumbered: list[Path] = []
    for clip in clips:
        prefix = clip.stem.split("-", 1)[0]
        if not prefix.isdigit():
            unnumbered.append(clip)
            continue

        by_segment.setdefault(int(prefix), []).append(clip)

    if unnumbered:
        names = ", ".join(p.name for p in unnumbered)
        sys.exit(f"unnumbered clips (expected <n>-<type>): {names}")

    selected: list[Path] = []
    select_errors: list[str] = []
    for n in sorted(by_segment):
        group = by_segment[n]
        if len(group) == 1:
            chosen = group[0]
            print(f"  segment {n}: {chosen.name} (only clip)")
            selected.append(chosen)
            continue

        sync_path = edit_dir / str(n) / "sync.json"
        if not sync_path.is_file():
            select_errors.append(
                f"segment {n}: {len(group)} clips but no sync.json at {sync_path}"
            )
            continue

        try:
            sync_data = json.loads(sync_path.read_text())
        except json.JSONDecodeError as e:
            select_errors.append(f"segment {n}: invalid JSON in {sync_path}: {e}")
            continue

        if not isinstance(sync_data, dict):
            select_errors.append(f"segment {n}: {sync_path} must be a JSON object")
            continue

        audio_reference_clip = sync_data.get("audio_reference_clip")
        if not audio_reference_clip:
            select_errors.append(
                f"segment {n}: sync.json missing audio_reference_clip ({sync_path})"
            )
            continue

        reference_stem = Path(str(audio_reference_clip)).stem
        matches = [c for c in group if c.stem == reference_stem]
        if not matches:
            have = ", ".join(c.stem for c in group)
            select_errors.append(
                f"segment {n}: audio_reference_clip '{audio_reference_clip}' "
                f"has no matching clip (have: {have})"
            )
            continue

        if len(matches) > 1:
            names = ", ".join(c.name for c in matches)
            select_errors.append(
                f"segment {n}: audio_reference_clip '{audio_reference_clip}' "
                f"matches more than one clip: {names}"
            )
            continue

        chosen = matches[0]
        print(f"  segment {n}: {chosen.name} (audio reference clip)")
        selected.append(chosen)

    if select_errors:
        sys.exit("\n".join(select_errors))

    already_cached = [
        v
        for v in selected
        if (edit_dir / "clip_transcriptions" / f"{v.stem}.json").exists()
    ]
    pending = [v for v in selected if v not in already_cached]

    print(
        f"found {len(selected)} clips "
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

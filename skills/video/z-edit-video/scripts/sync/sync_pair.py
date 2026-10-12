#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy>=2,<3"]
# ///
"""Align sources onto each source group's audio source by envelope correlation.

Walks <videos_dir> for files named <n>-<type>, reads `audio` and
`audio_source` from `edit/edit.json`, and writes offsets onto
that source group's `sync` only when more than one source has audio.

    uv run scripts/sync/sync_pair.py <videos_dir>

Each offset is that source's time minus the audio source's time for
the same instant. Positive means the other source started first.

Requires ffmpeg on PATH. `uv` resolves numpy from the header above.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

ENVELOPE_RATE = 100  # envelope samples per second; 10ms resolution
SAMPLE_RATE = 16000

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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "videos_dir",
        type=Path,
        help="Directory containing the sources",
    )
    parser.add_argument(
        "--plan",
        type=Path,
        default=Path("edit/edit.json"),
        help="edit.json to write sync offsets onto (default: edit/edit.json)",
    )
    parser.add_argument(
        "--window",
        type=float,
        default=180.0,
        help="seconds of audio to analyse from the start of each source (default 180)",
    )
    parser.add_argument(
        "--max-offset",
        type=float,
        default=60.0,
        help="largest offset to consider, in seconds (default 60)",
    )
    args = parser.parse_args()

    videos_dir = args.videos_dir.resolve()
    if not videos_dir.is_dir():
        sys.exit(f"not a directory: {videos_dir}")

    by_stem: dict[str, Path] = {}
    for path in sorted(videos_dir.iterdir()):
        if not path.is_file() or path.suffix.lower() not in SOURCE_EXTS:
            continue
        if path.stem in by_stem:
            sys.exit(
                f"duplicate source stem {path.stem!r}: {by_stem[path.stem].name} "
                f"and {path.name}"
            )
        by_stem[path.stem] = path

    plan_path = args.plan.resolve()
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

    wrote = False
    errors: list[str] = []

    for n in sorted(
        source_groups,
        key=lambda k: (0, int(str(k))) if str(k).isdigit() else (1, str(k)),
    ):
        info = source_groups[n]
        if not isinstance(info, dict):
            errors.append(f"source group {n}: must be an object")
            continue

        plan_sources = plan.get("sources")
        if not isinstance(plan_sources, dict):
            plan_sources = {}
        sources_obj = {
            name: record
            for name, record in plan_sources.items()
            if (
                str(name).split("-", 1)[0] == str(n)
                and isinstance(record, dict)
                and record.get("type") not in {"graphic", "browser"}
            )
        }
        if not sources_obj:
            errors.append(f"source group {n}: no sources")
            continue

        with_audio = [
            name
            for name, source in sources_obj.items()
            if isinstance(source, dict) and source.get("audio")
        ]
        if len(with_audio) < 2:
            print(f"  source group {n}: skipped ({len(with_audio)} audio source)")
            continue

        reference_name = info.get("audio_source")
        if not reference_name:
            errors.append(f"source group {n}: audio_source is required")
            continue

        reference_stem = Path(str(reference_name)).stem
        audio_stems = [Path(str(name)).stem for name in with_audio]
        if reference_stem not in audio_stems:
            have = ", ".join(audio_stems)
            errors.append(
                f"source group {n}: audio_source '{reference_name}' "
                f"is not an audio source (have: {have})"
            )
            continue

        reference_path = by_stem.get(reference_stem)
        if reference_path is None:
            errors.append(
                f"source group {n}: no file for audio_source "
                f"'{reference_name}' in {videos_dir}"
            )
            continue

        others: list[Path] = []
        missing = False
        for name in with_audio:
            stem = Path(str(name)).stem
            if stem == reference_stem:
                continue
            path = by_stem.get(stem)
            if path is None:
                errors.append(f"source group {n}: no file for '{name}' in {videos_dir}")
                missing = True
                continue
            others.append(path)
        if missing:
            continue

        print(
            f"  source group {n}: {reference_path.name} <- "
            + ", ".join(p.name for p in others)
        )

        # ==================================================
        # Envelopes
        # ==================================================

        # Decode to mono 16k PCM, then take per-frame RMS. RMS tracks speech
        # energy, which survives the two sources having different mics, gain, and
        # room position -- raw waveforms would not correlate across those.
        sources = [reference_path, *others]
        envelopes = {}
        envelope_failed = False
        for path in sources:
            proc = subprocess.run(
                [
                    "ffmpeg",
                    "-v",
                    "error",
                    "-nostdin",
                    "-t",
                    str(args.window),
                    "-i",
                    str(path),
                    "-vn",
                    "-ac",
                    "1",
                    "-ar",
                    str(SAMPLE_RATE),
                    "-f",
                    "s16le",
                    "-",
                ],
                capture_output=True,
            )
            if proc.returncode != 0:
                errors.append(
                    f"ffmpeg failed decoding {path}:\n"
                    f"{proc.stderr.decode(errors='replace')}"
                )
                envelope_failed = True
                break
            pcm = np.frombuffer(proc.stdout, dtype="<i2").astype(np.float32) / 32768.0
            if pcm.size == 0:
                errors.append(
                    f"{path} has no audio stream; sync it by hand or use offset 0"
                )
                envelope_failed = True
                break

            hop = SAMPLE_RATE // ENVELOPE_RATE
            frames = pcm[: (pcm.size // hop) * hop].reshape(-1, hop)
            env = np.sqrt((frames**2).mean(axis=1))
            # Compress the dynamic range so a single loud transient cannot dominate
            # the correlation, then zero-mean and unit-norm so the peak reads as a
            # correlation coefficient rather than an arbitrary magnitude.
            env = np.log1p(env * 1000.0)
            env -= env.mean()
            norm = np.linalg.norm(env)
            if norm == 0:
                errors.append(
                    f"{path} is silent for the analysed window; sync it by hand"
                )
                envelope_failed = True
                break
            envelopes[path] = env / norm
        if envelope_failed:
            continue

            # ==================================================
            # Offsets
            # ==================================================

        reference = envelopes[reference_path]
        result = {}
        offset_failed = False

        for other in others:
            other_env = envelopes[other]

            # FFT cross-correlation, matching np.correlate(other, reference, "full"):
            # index k holds lag k - (len(reference) - 1), and lag L means
            # other[n+L] ~ reference[n].
            size = other_env.size + reference.size - 1
            nfft = 1 << (size - 1).bit_length()
            cc = np.fft.irfft(
                np.fft.rfft(other_env, nfft) * np.conj(np.fft.rfft(reference, nfft)),
                nfft,
            )
            cc = np.concatenate((cc[-(reference.size - 1) :], cc[: other_env.size]))
            lags = np.arange(cc.size) - (reference.size - 1)

            limit = int(args.max_offset * ENVELOPE_RATE)
            searchable = np.abs(lags) <= limit
            if not searchable.any():
                errors.append(
                    f"source group {n}: --max-offset is smaller than the envelope resolution"
                )
                offset_failed = True
                break
            cc_searched = np.where(searchable, cc, -np.inf)

            peak = int(np.argmax(cc_searched))
            offset = float(lags[peak]) / ENVELOPE_RATE
            score = float(cc[peak])

            # A true sync produces one peak that clearly beats everything outside its
            # own shoulder. A flat field of similar peaks means the sources share no
            # common audio and the answer is noise.
            shoulder = int(0.5 * ENVELOPE_RATE)
            masked = cc_searched.copy()
            masked[max(0, peak - shoulder) : peak + shoulder + 1] = -np.inf
            runner_up = float(masked.max())
            margin = score / runner_up if runner_up > 0 else float("inf")
            confident = score > 0.05 and margin > 1.5
            if not confident:
                print(f"  source group {n}: Flag to user at next gate", file=sys.stderr)

            result[other.stem] = round(offset, 3)

        if offset_failed:
            continue

        info["sync"] = result
        wrote = True
        print(json.dumps(result, indent=2))

    if errors:
        sys.exit("\n".join(errors))

    if not wrote:
        print("nothing to sync")
        return 0

    plan_path.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())

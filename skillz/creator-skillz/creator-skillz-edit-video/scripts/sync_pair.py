#!/usr/bin/env python3
"""Find the audio offset between a segment's cam and screen clips.

Both clips record the same room, so their loudness envelopes line up when
shifted by the recording offset. Cross-correlating the envelopes finds that
shift without needing a clap or any other visible sync point.

    python sync_pair.py 1-cam.mp4 1-screen.mp4 -o edit/1/sync.json

Writes {"offset_seconds": ...}, where offset is the screen clip's time minus
the cam clip's time for the same instant. Positive means the screen recording
started first. Feed it to ffmpeg as `-ss <offset>` on the screen input, or as
`tpad=start_duration=<-offset>` when negative.

Requires ffmpeg on PATH and numpy.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

ENVELOPE_RATE = 100  # envelope samples per second; 10ms resolution
SAMPLE_RATE = 16000


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cam", type=Path, help="the cam clip")
    parser.add_argument("screen", type=Path, help="the screen clip")
    parser.add_argument("-o", "--out", type=Path, help="write JSON here instead of stdout")
    parser.add_argument(
        "--window",
        type=float,
        default=180.0,
        help="seconds of audio to analyse from the start of each clip (default 180)",
    )
    parser.add_argument(
        "--max-offset",
        type=float,
        default=60.0,
        help="largest offset to consider, in seconds (default 60)",
    )
    args = parser.parse_args()

    for path in (args.cam, args.screen):
        if not path.exists():
            sys.exit(f"no such file: {path}")

    # Both envelopes: decode to mono 16k PCM, then take per-frame RMS. RMS
    # tracks speech energy, which survives the two clips having different mics,
    # gain, and room position -- raw waveforms would not correlate across those.
    envelopes = {}
    for name, path in (("cam", args.cam), ("screen", args.screen)):
        proc = subprocess.run(
            [
                "ffmpeg", "-v", "error", "-nostdin",
                "-t", str(args.window),
                "-i", str(path),
                "-vn", "-ac", "1", "-ar", str(SAMPLE_RATE),
                "-f", "s16le", "-",
            ],
            capture_output=True,
        )
        if proc.returncode != 0:
            sys.exit(f"ffmpeg failed decoding {path}:\n{proc.stderr.decode(errors='replace')}")
        pcm = np.frombuffer(proc.stdout, dtype="<i2").astype(np.float32) / 32768.0
        if pcm.size == 0:
            sys.exit(f"{path} has no audio stream; sync it by hand or use offset 0")

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
            sys.exit(f"{path} is silent for the analysed window; sync it by hand")
        envelopes[name] = env / norm

    cam, screen = envelopes["cam"], envelopes["screen"]

    # FFT cross-correlation, matching np.correlate(screen, cam, "full"):
    # index k holds lag k - (len(cam) - 1), and lag L means screen[n+L] ~ cam[n].
    size = screen.size + cam.size - 1
    nfft = 1 << (size - 1).bit_length()
    cc = np.fft.irfft(np.fft.rfft(screen, nfft) * np.conj(np.fft.rfft(cam, nfft)), nfft)
    cc = np.concatenate((cc[-(cam.size - 1):], cc[: screen.size]))
    lags = np.arange(cc.size) - (cam.size - 1)

    limit = int(args.max_offset * ENVELOPE_RATE)
    searchable = np.abs(lags) <= limit
    if not searchable.any():
        sys.exit("--max-offset is smaller than the envelope resolution")
    cc_searched = np.where(searchable, cc, -np.inf)

    peak = int(np.argmax(cc_searched))
    offset = float(lags[peak]) / ENVELOPE_RATE
    score = float(cc[peak])

    # A true sync produces one peak that clearly beats everything outside its
    # own shoulder. A flat field of similar peaks means the clips share no
    # common audio and the answer is noise.
    shoulder = int(0.5 * ENVELOPE_RATE)
    masked = cc_searched.copy()
    masked[max(0, peak - shoulder) : peak + shoulder + 1] = -np.inf
    runner_up = float(masked.max())
    margin = score / runner_up if runner_up > 0 else float("inf")
    confident = score > 0.05 and margin > 1.5

    result = {
        "cam": str(args.cam),
        "screen": str(args.screen),
        "offset_seconds": round(offset, 3),
        "peak_correlation": round(score, 4),
        "peak_margin": round(margin, 2) if np.isfinite(margin) else None,
        "confident": confident,
        "note": (
            "apply as -ss <offset_seconds> on the screen input when positive, "
            "tpad=start_duration=<-offset_seconds> when negative"
            if confident
            else "LOW CONFIDENCE: verify against a visible sync point before compositing"
        ),
    }

    text = json.dumps(result, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n")
    print(text)
    return 0 if confident else 1


if __name__ == "__main__":
    sys.exit(main())

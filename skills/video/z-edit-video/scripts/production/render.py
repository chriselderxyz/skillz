"""Render a video from `edit/edit.json`.

Pipeline:

  1. Per-range extract. Picture comes from `range.active_source` when that
     range has a full-frame footage layer. A range with no picture gets a
     black frame. Audio comes from `range.audio_source`. Color grade applies
     to `head` sources only, with 30ms audio fades. Video and audio are
     extracted in separate ffmpeg runs, then muxed, so the video frame
     count cannot cut the audio short. Video is a whole-frame duration.
     Audio is sample-accurate PCM.
  2. Lossless -c copy concat into base.mp4
  3. Optional PIP pieces (edit clock windows and authored source cuts),
     color graded only when the PIP source is `head`
  4. Final filter graph on the edit clock:
     picture → graphics and browser → PIP inset → subtitles LAST
     Draft audio is AAC. A finalized render writes PCM.

The cut list is compiled from `edit/edit.json`.
The audio source is `range.audio_source`.
`range.start` / `range.end` are seeks on the audio source.
`range.active_source` is the full-frame footage for that range, when it
has one. `range.active_start` is the seek in that source. Compiling the
cut list adds that source's sync offset. Unsynced footage keeps the
seek written on its layer.
`range.crop`, when present, is the approved full-frame crop in active-source
pixels. Without it, mismatched footage uses a centered cover crop.

Usage:
    python scripts/production/render.py -o edit/edit.mov
    python scripts/production/render.py -o draft.mp4 --draft
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from plan_model import compile_timeline

try:
    from grading.json_to_grade_vf import json_to_grade_vf_string
except Exception:

    def json_to_grade_vf_string(data):  # type: ignore
        sys.exit("json_to_grade_vf.py is required for color grading")


try:
    from srt_timeline import build_caption_cues, write_ass, _highlight_overrides
except Exception:

    def build_caption_cues(*args, **kwargs):  # type: ignore
        sys.exit("srt_timeline.py is required for burn-in captions")

    def write_ass(*args, **kwargs):  # type: ignore
        sys.exit("srt_timeline.py is required for burn-in captions")

    def _highlight_overrides(*args, **kwargs):  # type: ignore
        sys.exit("srt_timeline.py is required for burn-in captions")


def main() -> None:
    # ==================================================
    # CLI Argument Inputs
    # ==================================================
    ap = argparse.ArgumentParser(description="Render a video from edit/edit.json")
    ap.add_argument(
        "-o", "--output", type=Path, required=True, help="Output video path"
    )
    ap.add_argument(
        "--draft",
        action="store_true",
        help="Draft mode: 720p, ultrafast, CRF 28 — cut-point verification only.",
    )
    ap.add_argument(
        "--transcripts-dir",
        type=Path,
        default=None,
        help=(
            "Directory of <source>.json transcripts for burn-in "
            "(default: edit/source-transcriptions)."
        ),
    )
    args = ap.parse_args()

    plan_path = Path("edit").resolve() / "edit.json"
    timeline = compile_timeline(plan_path)
    edit_dir = plan_path.parent
    out_path = args.output.resolve()

    if not timeline["ranges"]:
        sys.exit(f"{plan_path}: no ranges to render")
    for i, r in enumerate(timeline["ranges"]):
        if not r.get("audio_source"):
            sys.exit(f"range[{i}] audio_source is required")

            ############################################################
            # Video Settings
            ############################################################

    video_settings = timeline.get("video_settings") or {}
    if video_settings and not isinstance(video_settings, dict):
        sys.exit(
            "edit.json video_settings must be an object (copy the video-settings JSON into edit.json)"
        )

    fps = float(video_settings["fps"]) if "fps" in video_settings else 30.0
    orientation = str(video_settings.get("orientation") or "").strip().lower()
    resolution = str(video_settings.get("resolution") or "").strip().upper()

    out_size: tuple[int, int] | None = None
    if orientation or resolution:
        if orientation not in ("landscape", "portrait"):
            sys.exit(
                "edit.json video_settings.orientation must be landscape or portrait, "
                f"got: {video_settings.get('orientation')!r}"
            )
        if resolution not in ("HD", "4K"):
            sys.exit(
                "edit.json video_settings.resolution must be HD or 4K, "
                f"got: {video_settings.get('resolution')!r}"
            )
        sizes = {
            ("landscape", "HD"): (1920, 1080),
            ("landscape", "4K"): (3840, 2160),
            ("portrait", "HD"): (1080, 1920),
            ("portrait", "4K"): (2160, 3840),
        }
        out_size = sizes[(orientation, resolution)]

    print(
        f"edit.json video_settings → fps={fps} orientation={orientation or None} "
        f"resolution={resolution or None} out_size={out_size}"
    )

    # ==================================================
    # Caption burn
    # ==================================================

    subtitle_layers: list[Path] = []

    caption_style = timeline.get("caption_style")
    if caption_style is None or caption_style == "none":
        caption_style = None
    elif not isinstance(caption_style, dict):
        sys.exit('caption_style must be an object, omitted, or "none"')

    burn_cues: list[dict] | None = None
    if caption_style:
        transcripts_dir = (
            args.transcripts_dir.resolve()
            if args.transcripts_dir is not None
            else edit_dir / "source-transcriptions"
        )
        if not transcripts_dir.is_dir():
            sys.exit(f"caption_style requires transcripts at {transcripts_dir}")

        caption_case = str(caption_style.get("case", "upper"))
        chars_per_line = int(caption_style.get("chars_per_line", 42))
        num_lines = int(caption_style.get("num_lines", 2))
        word_highlight = bool(_highlight_overrides(caption_style))
        print(
            f"caption_style → case={caption_case} "
            f"chars_per_line={chars_per_line} num_lines={num_lines} "
            f"word_highlight={word_highlight}"
        )

        burn_cues = build_caption_cues(
            timeline,
            transcripts_dir,
            chars_per_line=chars_per_line,
            num_lines=num_lines,
            caption_case=caption_case,
        )

        # Effective frame size after draft scaling (matches extract_segment)
    frame_size = out_size
    if args.draft and out_size is not None:
        ow, oh = out_size
        if ow >= oh:
            frame_size = (1280, max(2, int(round(1280 * oh / ow / 2) * 2)))
        else:
            frame_size = (max(2, int(round(1280 * ow / oh / 2) * 2)), 1280)

            # 1. Extract per-range (audio source + grade on head sources)
    segment_paths, range_frames = extract_all_segments(
        timeline,
        edit_dir,
        draft=args.draft,
        fps=fps,
        out_size=out_size,
    )

    # 2. Concat → base
    base_name = "base-draft.mp4" if args.draft else "base.mp4"
    base_path = edit_dir / base_name
    concat_segments(segment_paths, base_path, edit_dir)

    if burn_cues is not None and caption_style is not None:
        play_w, play_h = probe_wh(base_path)
        burn_path = edit_dir / "burn-captions.ass"
        write_ass(burn_cues, burn_path, caption_style, (play_w, play_h))
        subtitle_layers.append(burn_path)
        print(f"burn captions → {burn_path.name} ({len(burn_cues)} cues)")

    # 3. Optional PIP pieces (edit clock, grade if source is head)
    pip_pieces = extract_pip_track(
        timeline,
        edit_dir,
        draft=args.draft,
        fps=fps,
        frame_size=frame_size,
        range_frames=range_frames,
    )

    # 4. Composite on the edit clock: base picture, then layers, captions last
    graphics = timeline.get("graphics") or []
    build_final_composite(
        base_path,
        graphics,
        subtitle_layers,
        out_path,
        pip_pieces=pip_pieces,
        frame_size=frame_size,
        draft=args.draft,
    )

    size_mb = out_path.stat().st_size / (1024 * 1024)
    print(f"\ndone: {out_path} ({size_mb:.1f} MB)")

    # ==================================================
    # Utilities
    # ==================================================


def run(cmd: list[str], quiet: bool = False) -> None:
    if not quiet:
        print(f"  $ {' '.join(str(c) for c in cmd[:6])}{' …' if len(cmd) > 6 else ''}")
    subprocess.run(cmd, check=True)

    # -------- HDR → SDR tone mapping (HLG / PQ sources) --------------------------
    #
    # iPhone defaults to HLG HDR in Rec.2020 (and many mirrorless cameras ship PQ).
    # If the source is HDR and we only downconvert bit depth (yuv420p10le → yuv420p)
    # without tone-mapping, the output is 8-bit but still carries HLG/PQ transfer
    # metadata. Players that honor the metadata (screen recorders, most social
    # upload re-encodes) interpret 8-bit values in an HDR container and the result
    # looks oversaturated / blown out. QuickTime on macOS can hide this locally —
    # screen recording and uploaded renders cannot.
    #
    # Fix: detect HDR via color_transfer and prepend a zscale+tonemap chain to the
    # vf graph so the output is clean Rec.709 SDR.


HDR_TRANSFERS = {"smpte2084", "arib-std-b67"}  # PQ (HDR10) and HLG

TONEMAP_CHAIN = (
    "zscale=t=linear:npl=100,"
    "format=gbrpf32le,"
    "zscale=p=bt709,"
    "tonemap=tonemap=hable:desat=0,"
    "zscale=t=bt709:m=bt709:r=tv,"
    "format=yuv420p"
)


def probe_streams(path: Path) -> list[dict]:
    """Return each file stream once.

    ffmpeg 9 repeats a program's streams next to the file streams in the
    flat writers. The JSON `streams` array is the file listing. A repeated
    index in that array is kept once.
    """
    out = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "stream=index,codec_type,width,height,color_transfer:stream_disposition=attached_pic",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(out.stdout or "{}")
    streams = data.get("streams") or []
    seen: set[int] = set()
    unique: list[dict] = []
    for stream in streams:
        if not isinstance(stream, dict):
            continue
        index = stream.get("index")
        if isinstance(index, int):
            if index in seen:
                continue
            seen.add(index)
        unique.append(stream)
    return unique


def real_video_stream(streams: list[dict]) -> dict | None:
    """First video stream that is not attached cover art."""
    for stream in streams:
        if stream.get("codec_type") != "video":
            continue
        disposition = stream.get("disposition") or {}
        if disposition.get("attached_pic"):
            continue
        return stream
    return None


def is_hdr_source(video: Path) -> bool:
    """Return True if the source uses a PQ or HLG transfer function."""
    try:
        video_stream = real_video_stream(probe_streams(video))
    except Exception:
        return False
    if video_stream is None:
        return False
    return str(video_stream.get("color_transfer") or "") in HDR_TRANSFERS


def is_portrait_source(video: Path) -> bool:
    """Return True if the video's height > width (portrait / vertical)."""
    try:
        video_stream = real_video_stream(probe_streams(video))
        if video_stream is None:
            return False
        return int(video_stream["height"]) > int(video_stream["width"])
    except Exception:
        return False


def probe_wh(video: Path) -> tuple[int, int]:
    video_stream = real_video_stream(probe_streams(video))
    if video_stream is None:
        sys.exit(f"{video.name} has no video stream")
    return int(video_stream["width"]), int(video_stream["height"])


def has_audio_stream(path: Path) -> bool:
    try:
        return any(
            stream.get("codec_type") == "audio" for stream in probe_streams(path)
        )
    except Exception:
        return False


def even(n: int) -> int:
    return max(2, int(n) // 2 * 2)


def range_settings(
    timeline: dict,
    r: dict,
) -> dict:
    """Load plan styles for one range.

    `grading_style` and `pip_style` come from `edit/edit.json`.
    """
    audio_key = Path(str(r["audio_source"])).stem
    active_raw = r.get("active_source")
    active_key = Path(str(active_raw)).stem if active_raw else ""

    grading_style = timeline.get("grading_style")
    if (
        grading_style is None
        or grading_style == "none"
        or not isinstance(grading_style, dict)
    ):
        grading_style = None

    pip_style = timeline.get("pip_style")
    if pip_style is None or pip_style == "none" or not isinstance(pip_style, dict):
        pip_style = None
    else:
        pip_style = dict(pip_style)

    return {
        "audio_source": audio_key,
        "active_source": active_key,
        "grading_style": grading_style,
        "pip_style": pip_style,
    }


    # ==================================================
    # PIP geometry
    # ==================================================


def resolve_pip_geometry(
    style: dict,
    out_size: tuple[int, int] | None,
) -> tuple[dict, str]:
    """Return ({x,y,w,h} on the output frame, shape) from pip_style."""
    if out_size is None:
        sys.exit(
            "pip requires edit.json video_settings.orientation and "
            "edit.json video_settings.resolution (HD or 4K)"
        )

    ow, oh = out_size
    frac = float(style.get("width_fraction") or 0.23)
    margin_frac = float(style.get("margin_fraction") or 0.025)
    pw = even(int(round(ow * frac)))
    shape = str(style.get("shape") or "rect")
    ph = pw
    aspect = style.get("aspect")
    if shape not in ("circle", "square") and aspect:
        parts = str(aspect).split(":")
        if len(parts) != 2:
            sys.exit(f"pip_style.aspect must be W:H, got: {aspect!r}")
        try:
            aw, ah = float(parts[0]), float(parts[1])
        except ValueError:
            sys.exit(f"pip_style.aspect must be W:H, got: {aspect!r}")
        if aw <= 0 or ah <= 0:
            sys.exit(
                f"pip_style.aspect must be W:H with positive numbers, got: {aspect!r}"
            )
        ph = even(int(round(pw * ah / aw)))
    margin = int(round(ow * margin_frac))
    anchor = str(style.get("anchor") or "bottom_right")

    if anchor == "bottom_right":
        x, y = ow - pw - margin, oh - ph - margin
    elif anchor == "bottom_left":
        x, y = margin, oh - ph - margin
    elif anchor == "top_right":
        x, y = ow - pw - margin, margin
    elif anchor == "top_left":
        x, y = margin, margin
    elif anchor == "bottom_center":
        x, y = (ow - pw) // 2, oh - ph - margin
    elif anchor == "top_center":
        x, y = (ow - pw) // 2, margin
    else:
        sys.exit(f"unknown pip anchor: {anchor!r}")

    return {"x": x, "y": y, "w": pw, "h": ph}, shape


def require_pip_crop(crop: dict) -> dict:
    """Required face crop: {x, y, w, h} in source pixels."""
    if not isinstance(crop, dict) or not all(k in crop for k in ("x", "y", "w", "h")):
        sys.exit("pip crop is required with x, y, w, h in source pixels")
    out: dict[str, int] = {}
    for key in ("x", "y", "w", "h"):
        value = crop[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            sys.exit(f"pip crop {key} must be a number, got: {crop!r}")
        out[key] = int(value)
    if out["w"] <= 0 or out["h"] <= 0:
        sys.exit(f"pip crop w and h must be positive, got: {crop!r}")
    return out

    # -------- Per-segment extraction (Rule 2 + Rule 3) --------------------------


def extract_segment(
    source: Path | None,
    seg_start: float,
    n_frames: int,
    grade_filter: str,
    out_path: Path,
    draft: bool = False,
    fps: float = 30,
    out_size: tuple[int, int] | None = None,
    audio_source: Path | None = None,
    audio_start: float | None = None,
    source_crop: dict | None = None,
) -> None:
    """Extract a cut range as its own MP4 with optional grade and fades.

    Optional `source_crop` is the approved `{x, y, w, h}` rectangle in source
    pixels. Optional `out_size` is `(width, height)` from video settings
    orientation + resolution (HD/4K). Footage is aspect-preserving
    cover-scaled after the approved crop; without one, excess is center-cropped.
    Without `out_size`, scale to 1920 (or 1280 in draft) on the long axis.

    Picture comes from `source` at `seg_start` when that file has a real video
    stream. Cover art is not a picture. With no picture, the range is a black
    frame at the output size. Audio comes from `audio_source` at `audio_start`.
    Both seeks are source time (already remapped from the audio source clock).

    Video and audio are separate ffmpeg runs, then muxed. Duration is an
    integer frame count. Audio is trimmed by sample count and stored as PCM
    (Pulse Code Modulation) so AAC priming is not baked into each source.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if audio_source is None or audio_start is None:
        sys.exit(f"{out_path.name}: audio source is required")
    if not has_audio_stream(audio_source):
        sys.exit(f"{audio_source.name} has no audio stream")

    audio_rate = 48000
    preroll = 0.25
    duration = n_frames / fps
    n_samples = int(round(n_frames * audio_rate / fps))

    video_stream = None
    if source is not None:
        video_stream = real_video_stream(probe_streams(source))

    if draft:
        preset, crf = "ultrafast", "28"
    else:
        preset, crf = "fast", "20"

    frame_w: int | None = None
    frame_h: int | None = None
    if out_size is not None:
        frame_w, frame_h = out_size
        if draft:
            if frame_w >= frame_h:
                frame_w, frame_h = (
                    1280,
                    max(2, int(round(1280 * frame_h / frame_w / 2) * 2)),
                )
            else:
                frame_w, frame_h = (
                    max(2, int(round(1280 * frame_w / frame_h / 2) * 2)),
                    1280,
                )

    vf_parts: list[str] = []
    if video_stream is not None:
        if str(video_stream.get("color_transfer") or "") in HDR_TRANSFERS:
            vf_parts.append(TONEMAP_CHAIN)

        if source_crop is not None:
            if not isinstance(source_crop, dict):
                sys.exit(f"source crop must be an object, got: {source_crop!r}")
            if not all(
                isinstance(source_crop.get(k), int)
                and not isinstance(source_crop.get(k), bool)
                for k in ("x", "y", "w", "h")
            ):
                sys.exit(
                    f"source crop requires integer x, y, w, h, got: {source_crop!r}"
                )
            cx, cy, cw, ch = (int(source_crop[k]) for k in ("x", "y", "w", "h"))
            if cx < 0 or cy < 0 or cw <= 0 or ch <= 0:
                sys.exit(f"invalid source crop: {source_crop!r}")
            source_w = int(video_stream["width"])
            source_h = int(video_stream["height"])
            if cx + cw > source_w or cy + ch > source_h:
                sys.exit(
                    f"source crop {source_crop!r} exceeds {source.name} "
                    f"dimensions {source_w}x{source_h}"
                )
            vf_parts.append(f"crop={cw}:{ch}:{cx}:{cy}")

        if frame_w is not None and frame_h is not None:
            vf_parts.append(
                f"scale={frame_w}:{frame_h}:force_original_aspect_ratio=increase,"
                f"crop={frame_w}:{frame_h},setsar=1"
            )
        else:
            if source_crop is not None:
                portrait = source_crop["h"] > source_crop["w"]
            else:
                portrait = int(video_stream["height"]) > int(video_stream["width"])
            if draft:
                scale = "scale=-2:1280" if portrait else "scale=1280:-2"
            else:
                scale = "scale=-2:1920" if portrait else "scale=1920:-2"
            vf_parts.append(scale)

        if grade_filter:
            vf_parts.append(grade_filter)
    elif source_crop is not None:
        name = source.name if source is not None else out_path.name
        sys.exit(f"source crop is set but {name} has no video stream")

    if video_stream is None:
        if frame_w is None or frame_h is None:
            frame_w, frame_h = (1280, 720) if draft else (1920, 1080)
        if source is None:
            print("    no picture, black frame")
        else:
            print(f"    {source.name}: no video stream, black frame")

    # 30ms audio fades at both edges (Rule 3) — prevent pops
    fade_out_start = max(0.0, duration - 0.03)
    af = f"afade=t=in:st=0:d=0.03,afade=t=out:st={fade_out_start:.3f}:d=0.03"

    a_origin = float(audio_start)
    v_seek = max(0.0, seg_start - preroll)
    a_seek = max(0.0, a_origin - preroll)
    v_end = seg_start + duration
    a_end = a_origin + duration

    # Fast input seek, then trim on original timestamps (-copyts) so packet
    # boundaries cannot shift the cut. -start_at_zero puts the file's first
    # sample at 0, the origin transcripts and sync offsets use. Video stops on
    # n_frames. Audio stops on n_samples. They are muxed afterwards so one
    # cannot cut the other short.
    vf = ",".join(vf_parts)
    v_chain = (
        f"trim=start={seg_start:.9f}:end={v_end:.9f},"
        f"setpts=PTS-STARTPTS,"
        f"fps={fps},"
        f"{vf},"
        f"tpad=stop_mode=clone:stop=-1"
    )
    a_chain = (
        f"atrim=start={a_origin:.9f}:end={a_end:.9f},"
        f"asetpts=PTS-STARTPTS,"
        f"{af},"
        f"aresample={audio_rate},"
        f"apad,"
        f"atrim=end_sample={n_samples},"
        f"asetpts=PTS-STARTPTS"
    )

    video_path = out_path.with_name(out_path.stem + ".video.mp4")
    audio_path = out_path.with_name(out_path.stem + ".audio.wav")
    video_encode = [
        "-frames:v",
        str(n_frames),
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        preset,
        "-crf",
        crf,
        "-pix_fmt",
        "yuv420p",
        "-r",
        str(fps),
    ]

    if video_stream is None:
        video_cmd = [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c=black:s={frame_w}x{frame_h}:r={fps}",
            *video_encode,
            str(video_path),
        ]
    else:
        video_cmd = [
            "ffmpeg",
            "-y",
            "-copyts",
            "-start_at_zero",
            "-ss",
            f"{v_seek:.6f}",
            "-i",
            str(source),
            "-filter_complex",
            f"[0:V:0]{v_chain}[v]",
            "-map",
            "[v]",
            *video_encode,
            str(video_path),
        ]

    audio_cmd = [
        "ffmpeg",
        "-y",
        "-copyts",
        "-start_at_zero",
        "-ss",
        f"{a_seek:.6f}",
        "-i",
        str(audio_source),
        "-filter_complex",
        f"[0:a:0]{a_chain}[a]",
        "-map",
        "[a]",
        "-c:a",
        "pcm_s16le",
        "-ar",
        str(audio_rate),
        str(audio_path),
    ]
    mux_cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-i",
        str(audio_path),
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-c",
        "copy",
        "-movflags",
        "+faststart",
        str(out_path),
    ]

    for label, cmd in (("video", video_cmd), ("audio", audio_cmd), ("mux", mux_cmd)):
        proc = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        if proc.returncode != 0:
            video_path.unlink(missing_ok=True)
            audio_path.unlink(missing_ok=True)
            err = proc.stderr.decode("utf-8", errors="replace")
            sys.exit(
                f"ffmpeg {label} extract failed ({out_path.name}):\n{err[-4000:]}"
            )

    video_path.unlink(missing_ok=True)
    audio_path.unlink(missing_ok=True)


def extract_all_segments(
    timeline: dict,
    edit_dir: Path,
    draft: bool = False,
    fps: float = 24,
    out_size: tuple[int, int] | None = None,
) -> tuple[list[Path], list[int]]:
    """Extract every range into edit_dir/range-cuts/seg-NN.mp4.

    Range start/end are seeks on `range.audio_source`.
    `range.active_source` is the full-frame picture, when the range has one.
    `range.active_start` is the seek in that source. `grading_style` applies
    only when that source is `head`.

    Returns (segment paths, per-range frame counts). Frame counts are
    error-diffused so the cumulative edit clock stays within half a frame
    of the edit.json times used by graphics and PIP.
    """
    sources_dir = edit_dir / ("range-cuts-draft" if draft else "range-cuts")
    sources_dir.mkdir(parents=True, exist_ok=True)

    ranges = timeline["ranges"]
    sources = timeline["sources"]

    seg_paths: list[Path] = []
    range_frames: list[int] = []
    accum_edit = 0.0
    accum_frames = 0
    print(f"extracting {len(ranges)} range(s) → {sources_dir.name}/")

    for i, r in enumerate(ranges):
        settings = range_settings(timeline, r)
        audio_key = settings["audio_source"]
        active_key = settings["active_source"]
        if audio_key not in sources:
            sys.exit(
                f"range[{i}] audio_source {audio_key!r} missing from sources"
            )
        src_path: Path | None = None
        if active_key:
            if active_key not in sources:
                sys.exit(
                    f"range[{i}] active_source {active_key!r} missing from sources"
                )
            src_path = Path(sources[active_key])
        seg_start = float(r["start"])
        seg_end = float(r["end"])
        duration = seg_end - seg_start
        accum_edit += duration
        n_frames = int(round(accum_edit * fps)) - accum_frames

        if n_frames < 1:
            n_frames = 1

        accum_frames += n_frames
        range_frames.append(n_frames)

        # `active_start` is the file seek. Compiling added the sync offset when
        # this source is synced to the audio source.
        video_start = seg_start
        if src_path is not None:
            if r.get("active_start") is not None:
                video_start = float(r["active_start"])
            elif active_key != audio_key:
                sys.exit(
                    f"range[{i}] active_start is required when active_source "
                    f"{active_key!r} is not the audio source"
                )
        name = active_key or "black"
        out_path = sources_dir / f"seg-{i:02d}-{name}.mp4"
        source_type = active_key.split("-", 1)[-1] if active_key else ""
        grade_filter = (
            json_to_grade_vf_string(settings["grading_style"])
            if source_type == "head"
            else ""
        )

        audio_source = Path(sources[audio_key])
        source_crop = r.get("crop")

        sync_note = ""
        if src_path is not None and abs(video_start - seg_start) > 0.0005:
            sync_note = f"  v@{video_start:.2f}"
        if active_key != audio_key:
            sync_note += f"  a={audio_key}"
        if source_crop is not None:
            sync_note += (
                f"  crop={source_crop.get('x')},{source_crop.get('y')},"
                f"{source_crop.get('w')},{source_crop.get('h')}"
            )
        grade_note = "  grade" if grade_filter else ""
        print(
            f"  [{i:02d}] {name}  {seg_start:7.2f}-{seg_end:7.2f}  "
            f"({duration:5.2f}s){sync_note}{grade_note}"
        )
        extract_segment(
            src_path,
            video_start,
            n_frames,
            grade_filter,
            out_path,
            draft=draft,
            fps=fps,
            out_size=out_size,
            audio_source=audio_source,
            audio_start=seg_start,
            source_crop=source_crop,
        )
        seg_paths.append(out_path)

    return seg_paths, range_frames

    # ==================================================
    # PIP track — edit clock windows, source seeks from authored cuts
    # ==================================================


def extract_pip_track(
    timeline: dict,
    edit_dir: Path,
    draft: bool = False,
    fps: float = 30,
    frame_size: tuple[int, int] | None = None,
    range_frames: list[int] | None = None,
) -> list[dict]:
    """Extract PIP sources from the compiled pip windows.

    Each entry is `{source, start, end, crop, cuts}`. `start` / `end`
    are the edit clock window. `cuts` are source times in `source`, as
    written, laid end to end across that window. A piece is emitted for
    every overlap of a PIP cut with a range. `grading_style`
    applies only when the PIP source is `head`. Returns
    `{path, start, duration, layout, style}` on the snapped edit frame
    clock for compositing.
    """
    pip_entries = timeline.get("pip") or []
    if not isinstance(pip_entries, list) or not pip_entries:
        return []

    if frame_size is None:
        sys.exit(
            "pip requires edit.json video_settings.orientation and "
            "edit.json video_settings.resolution (HD or 4K)"
        )

    sources = timeline["sources"]
    ranges = timeline["ranges"]
    if range_frames is None or len(range_frames) != len(ranges):
        sys.exit("extract_pip_track requires range_frames from extract_all_segments")

        # Snap PIP windows onto the encoded edit frame clock. Overlay start
        # and duration both come from these frame numbers so adjacent pieces
        # of the same window cannot leave a sub-frame hole.
    edit_starts = [0.0]
    frame_starts = [0]
    accum_edit = 0.0
    accum_frames = 0
    for i, r in enumerate(ranges):
        accum_edit += float(r["end"]) - float(r["start"])
        accum_frames += range_frames[i]
        edit_starts.append(accum_edit)
        frame_starts.append(accum_frames)

    def edit_time_to_frame(t: float) -> int:
        frame = frame_starts[-1]
        if t <= edit_starts[0]:
            return 0
        if t >= edit_starts[-1]:
            return frame_starts[-1]
        for ri in range(len(ranges)):
            a = edit_starts[ri]
            b = edit_starts[ri + 1]
            if t < b or ri == len(ranges) - 1:
                dur = b - a
                n = range_frames[ri]
                lo = frame_starts[ri]
                hi = lo + n
                if dur <= 0:
                    return lo
                frame = lo + int(round((t - a) / dur * n))
                if frame < lo:
                    return lo
                if frame > hi:
                    return hi
                return frame
        return frame

    pip_cuts: list[list[dict]] = []
    for pip_i, pip in enumerate(pip_entries):
        if not isinstance(pip, dict):
            sys.exit(f"pip entries must be objects, got: {pip!r}")
        raw_cuts = pip.get("cuts")
        if not isinstance(raw_cuts, list) or not raw_cuts:
            sys.exit(f"pip[{pip_i}].cuts is required")
        pip_start = float(pip["start"])
        pip_end = float(pip["end"])
        if pip_end < pip_start:
            sys.exit(f"pip[{pip_i}] end is before start")
        playhead = pip_start
        laid: list[dict] = []
        for ci, cut in enumerate(raw_cuts):
            if not isinstance(cut, dict):
                sys.exit(f"pip[{pip_i}].cuts[{ci}] must be an object")
            cs = float(cut["start"])
            ce = float(cut["end"])
            if ce <= cs:
                sys.exit(f"pip[{pip_i}].cuts[{ci}] end is before start")
            dur = ce - cs
            laid.append(
                {
                    "source_start": cs,
                    "edit_start": playhead,
                    "edit_end": playhead + dur,
                    "crop": cut.get("crop"),
                }
            )
            playhead += dur
        if abs(playhead - pip_end) > 0.05:
            sys.exit(
                f"pip[{pip_i}].cuts total {playhead - pip_start:.2f}s but the "
                f"window is {pip_end - pip_start:.2f}s on the edit clock"
            )
        pip_cuts.append(laid)

    sources_dir = edit_dir / ("sources-pip-draft" if draft else "sources-pip")
    sources_dir.mkdir(parents=True, exist_ok=True)
    pieces: list[dict] = []
    used = [False] * len(pip_entries)
    piece_i = 0
    preroll = 0.25

    for i, r in enumerate(ranges):
        range_edit_start = edit_starts[i]
        range_edit_end = edit_starts[i + 1]
        range_n = range_frames[i]
        range_frame_start = frame_starts[i]
        settings = range_settings(timeline, r)

        for pip_i, pip in enumerate(pip_entries):
            pip_source = pip.get("source")
            if not pip_source:
                sys.exit("pip.source is required")
            if pip_source not in sources:
                sys.exit(f"pip.source {pip_source!r} missing from sources")

            for cut in pip_cuts[pip_i]:
                t0 = max(range_edit_start, cut["edit_start"])
                t1 = min(range_edit_end, cut["edit_end"])
                if t1 <= t0:
                    continue

                ov_start = edit_time_to_frame(t0)
                ov_end = edit_time_to_frame(t1)
                if ov_end <= ov_start:
                    continue

                n_frames_pip = ov_end - ov_start
                duration = n_frames_pip / fps
                if range_n > 0 and range_edit_end > range_edit_start:
                    edit_t = range_edit_start + (
                        (ov_start - range_frame_start)
                        / range_n
                        * (range_edit_end - range_edit_start)
                    )
                else:
                    edit_t = t0
                video_start = cut["source_start"] + (edit_t - cut["edit_start"])
                pip_style = settings["pip_style"]
                place = pip.get("place") or "pip"
                if frame_size is None:
                    sys.exit(
                        "a layer frame requires edit.json video_settings.orientation and "
                        "edit.json video_settings.resolution (HD or 4K)"
                    )
                ow, oh = frame_size
                face_crop = cut.get("crop") if isinstance(cut.get("crop"), dict) else None
                piece_style = pip_style or {"shape": "plain"}
                if place == "pip":
                    if pip_style is None:
                        sys.exit("pip requires pip_style on edit/edit.json")
                    layout, shape = resolve_pip_geometry(pip_style, frame_size)
                    if not isinstance(face_crop, dict):
                        sys.exit(f"pip crop is required for {pip_source}")
                    face_crop = require_pip_crop(face_crop)
                    piece_style = pip_style
                elif place == "top":
                    half = even(oh // 2)
                    layout = {"x": 0, "y": 0, "w": ow, "h": half}
                    shape = "plain"
                    piece_style = {"shape": "plain"}
                elif place == "bottom":
                    half = even(oh // 2)
                    layout = {"x": 0, "y": oh - half, "w": ow, "h": half}
                    shape = "plain"
                    piece_style = {"shape": "plain"}
                elif isinstance(place, dict):
                    layout = {
                        "x": even(int(round(ow * float(place["x"])))),
                        "y": even(int(round(oh * float(place["y"])))),
                        "w": even(max(2, int(round(ow * float(place["w"]))))),
                        "h": even(max(2, int(round(oh * float(place["h"]))))),
                    }
                    shape = "plain"
                    piece_style = {"shape": "plain"}
                else:
                    sys.exit(f"unknown layer frame: {place!r}")
                pw, ph = int(layout["w"]), int(layout["h"])
                pip_source_path = Path(sources[pip_source])
                place_at = ov_start / fps
                video_end = video_start + duration
                v_seek = max(0.0, video_start - preroll)

                vf_parts: list[str] = []
                if is_hdr_source(pip_source_path):
                    vf_parts.append(TONEMAP_CHAIN)
                if isinstance(face_crop, dict):
                    vf_parts.append(
                        f"crop={face_crop['w']}:{face_crop['h']}:"
                        f"{face_crop['x']}:{face_crop['y']}"
                    )
                vf_parts.append(f"scale={pw}:{ph}:force_original_aspect_ratio=increase")
                vf_parts.append(f"crop={pw}:{ph}")
                pip_type = Path(str(pip_source)).stem.split("-", 1)[-1]
                grade_filter = (
                    json_to_grade_vf_string(settings["grading_style"])
                    if pip_type == "head"
                    else ""
                )
                if grade_filter:
                    vf_parts.append(grade_filter)
                vf = ",".join(vf_parts)
                v_chain = (
                    f"trim=start={video_start:.9f}:end={video_end:.9f},"
                    f"setpts=PTS-STARTPTS,"
                    f"fps={fps},"
                    f"{vf},"
                    f"tpad=stop_mode=clone:stop=-1"
                )

                out_path = sources_dir / f"pip-{piece_i:02d}.mp4"
                grade_note = "  grade" if grade_filter else ""
                print(
                    f"  pip [{piece_i:02d}] {pip_source}  "
                    f"edit {place_at:.2f}-{place_at + duration:.2f}  "
                    f"frames {ov_start}-{ov_end}  src@{video_start:.2f}  "
                    f"layout={pw}x{ph} @ ({layout['x']},{layout['y']}) shape={shape}{grade_note}"
                )
                cmd = [
                    "ffmpeg",
                    "-y",
                    "-copyts",
                    "-start_at_zero",
                    "-ss",
                    f"{v_seek:.6f}",
                    "-i",
                    str(pip_source_path),
                    "-filter_complex",
                    f"[0:v]{v_chain}[v]",
                    "-map",
                    "[v]",
                    "-frames:v",
                    str(n_frames_pip),
                    "-an",
                    "-c:v",
                    "libx264",
                    "-preset",
                    "ultrafast" if draft else "fast",
                    "-crf",
                    "28" if draft else "18",
                    "-pix_fmt",
                    "yuv420p",
                    "-r",
                    str(fps),
                    "-movflags",
                    "+faststart",
                    str(out_path),
                ]
                proc = subprocess.run(
                    cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE
                )
                if proc.returncode != 0:
                    err = proc.stderr.decode("utf-8", errors="replace")
                    sys.exit(
                        f"ffmpeg pip extract failed ({out_path.name}):\n{err[-4000:]}"
                    )
                pieces.append(
                    {
                        "path": out_path,
                        "start": place_at,
                        "duration": duration,
                        "start_frame": ov_start,
                        "n_frames": n_frames_pip,
                        "pip_i": pip_i,
                        "layout": layout,
                        "style": piece_style,
                        "z": pip.get("z", pip_i),
                    }
                )
                used[pip_i] = True
                piece_i += 1

    by_pip: dict[int, list[dict]] = {}
    for p in pieces:
        by_pip.setdefault(p["pip_i"], []).append(p)

    for pip_i, group in by_pip.items():
        group.sort(key=lambda p: p["start_frame"])

        for a, b in zip(group, group[1:]):
            a_end = a["start_frame"] + a["n_frames"]
            gap = b["start_frame"] - a_end

            if gap < 0:
                sys.exit(
                    f"pip[{pip_i}] pieces overlap by {-gap} frame(s) at frame {a_end}"
                )

            if gap > 0:
                sys.exit(
                    f"pip[{pip_i}] {gap}-frame hole between pieces at frame {a_end}"
                )

    for i, pip in enumerate(pip_entries):
        if used[i]:
            continue
        src = pip.get("source") if isinstance(pip, dict) else pip
        start = pip.get("start") if isinstance(pip, dict) else "?"
        end = pip.get("end") if isinstance(pip, dict) else "?"
        print(f"warning: pip[{i}] {src} {start}-{end} overlapped no range")

    if pieces:
        print(f"extracted {len(pieces)} PIP piece(s) → {sources_dir.name}/")

    return pieces

    # -------- Lossless concat ----------------------------------------------------


def concat_segments(segment_paths: list[Path], out_path: Path, edit_dir: Path) -> None:
    """Lossless concat via the concat demuxer. No re-encode."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    concat_list = edit_dir / "_concat.txt"
    concat_list.write_text("".join(f"file '{p.resolve()}'\n" for p in segment_paths))

    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_list),
        "-c",
        "copy",
        "-movflags",
        "+faststart",
        str(out_path),
    ]
    print(f"concat → {out_path.name}")
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    concat_list.unlink(missing_ok=True)


def parse_hex_color(color: str) -> str:
    """Return ffmpeg 0xRRGGBB from #RRGGBB or RRGGBB."""
    raw = str(color or "#FFFFFF").strip().removeprefix("#")
    if len(raw) != 6:
        sys.exit(f"pip_style.border_color must be #RRGGBB, got: {color!r}")
    return f"0x{raw.upper()}"


def build_pip_overlay_filters(
    src_label: str,
    layout: dict,
    style: dict,
    tag: str,
) -> tuple[list[str], str]:
    """Build filter graph pieces that produce a labeled RGBA PIP stream.

    Returns (filter_parts, output_label) ex. (`...`, `[pipa0]`).
    """
    pw, ph = int(layout["w"]), int(layout["h"])
    shape = str(style.get("shape") or "rect")
    if shape == "plain":
        out_label = f"[pipa{tag}]"
        return [f"{src_label}format=rgba{out_label}"], out_label

    border_px = max(0, int(style.get("border_px") or 0))
    border_color = parse_hex_color(str(style.get("border_color") or "#FFFFFF"))
    radius_frac = float(style.get("corner_radius_fraction") or 0.0)
    radius = int(round(min(pw, ph) * radius_frac)) if shape != "circle" else 0

    parts: list[str] = []
    src = src_label
    pad_label = f"[pippad{tag}]"
    out_label = f"[pipa{tag}]"

    # Circle: paint the stroke as an annulus in geq. Do not pad a square
    # ring and then source it — an inscribed circle only keeps the stroke on
    # the four axes (ragged white at compass points, no border on diagonals).
    if shape == "circle":
        dist = f"hypot(X-{pw}/2\\,Y-{ph}/2)"
        r_outer = min(pw, ph) / 2
        alpha = f"min(max(({r_outer}-({dist})+0.5)*255\\,0)\\,255)"
        r_expr = "r(X\\,Y)"
        g_expr = "g(X\\,Y)"
        b_expr = "b(X\\,Y)"
        if border_px > 0:
            rgb = int(border_color[2:], 16)
            br = (rgb >> 16) & 255
            bg = (rgb >> 8) & 255
            bb = rgb & 255
            r_inner = max(0.0, r_outer - border_px)
            r_expr = f"if(gt({dist}\\,{r_inner})\\,{br}\\,{r_expr})"
            g_expr = f"if(gt({dist}\\,{r_inner})\\,{bg}\\,{g_expr})"
            b_expr = f"if(gt({dist}\\,{r_inner})\\,{bb}\\,{b_expr})"
        parts.append(
            f"{src}format=rgba,"
            f"geq=r='{r_expr}':g='{g_expr}':b='{b_expr}':a='{alpha}'{out_label}"
        )
        return parts, out_label

        # Rounded rect: paint the stroke along the rounded-box signed
        # distance. Do not pad a square ring then source — the rounded mask
        # cuts through the stroke at the corners.
    r = max(0, min(radius, min(pw, ph) // 2))
    if r > 0:
        dx = f"abs(X-{pw}/2)-({pw}/2-{r})"
        dy = f"abs(Y-{ph}/2)-({ph}/2-{r})"
        dist = f"hypot(max({dx}\\,0)\\,max({dy}\\,0))+min(max({dx}\\,{dy})\\,0)-{r}"
        alpha = f"min(max((0.5-({dist}))*255\\,0)\\,255)"
        r_expr = "r(X\\,Y)"
        g_expr = "g(X\\,Y)"
        b_expr = "b(X\\,Y)"
        if border_px > 0:
            rgb = int(border_color[2:], 16)
            br = (rgb >> 16) & 255
            bg = (rgb >> 8) & 255
            bb = rgb & 255
            r_expr = f"if(gt({dist}\\,{-border_px})\\,{br}\\,{r_expr})"
            g_expr = f"if(gt({dist}\\,{-border_px})\\,{bg}\\,{g_expr})"
            b_expr = f"if(gt({dist}\\,{-border_px})\\,{bb}\\,{b_expr})"
        parts.append(
            f"{src}format=rgba,"
            f"geq=r='{r_expr}':g='{g_expr}':b='{b_expr}':a='{alpha}'{out_label}"
        )
        return parts, out_label

    if border_px > 0:
        inner_w = even(max(2, pw - 2 * border_px))
        inner_h = even(max(2, ph - 2 * border_px))
        # Keep content inside the stroke, pad with border color to full PIP box
        parts.append(
            f"{src}scale={inner_w}:{inner_h}:force_original_aspect_ratio=increase,"
            f"crop={inner_w}:{inner_h},"
            f"pad={pw}:{ph}:{border_px}:{border_px}:{border_color}{pad_label}"
        )
        src = pad_label
        parts.append(f"{src}format=rgba{out_label}")
        return parts, out_label

    return parts, src

    # -------- Final compositing (Rule 1 + Rule 4) -------------------------------


def build_final_composite(
    base_path: Path,
    graphics: list[dict],
    subtitle_layers: list[Path],
    out_path: Path,
    pip_pieces: list[dict] | None = None,
    frame_size: tuple[int, int] | None = None,
    draft: bool = False,
) -> None:
    """Final pass on the edit clock: base picture, then layers in order, captions last."""
    pieces = pip_pieces or []
    has_graphics = bool(graphics)
    has_pip = bool(pieces)
    has_subs = bool(subtitle_layers)
    if draft:
        audio_codec = ["-c:a", "aac", "-b:a", "192k", "-ar", "48000"]
    else:
        audio_codec = ["-c:a", "pcm_s16le", "-ar", "48000"]

    if not has_graphics and not has_pip and not has_subs:
        run(
            [
                "ffmpeg",
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                str(base_path),
                "-c:v",
                "copy",
                *audio_codec,
                "-movflags",
                "+faststart",
                str(out_path),
            ],
            quiet=True,
        )
        return

    inputs: list[str] = ["-i", str(base_path)]
    for graphic in graphics:
        t = float(graphic["start"])
        end = float(graphic["end"])
        if end <= t:
            sys.exit(f"graphics start ({t}) must be before end ({end})")
            # Limit the read so a longer file cannot outlast the overlay window
            # (overlay keeps going until every input is exhausted).
        graphic_path = Path(graphic["file"])
        graphic_input = ["-t", f"{end - t:.3f}"]
        # A still repeats its one frame for the whole window.
        if graphic_path.suffix.lower() == ".png":
            graphic_input = ["-loop", "1", *graphic_input]
        # Native vp9 drops the WebM Matroska alpha sidecar (yuv420p), so a
        # transparent graphic becomes an opaque rectangle. libvpx-vp9 keeps
        # yuva420p. This -c:v must sit immediately before this -i.
        if graphic_path.suffix.lower() == ".webm":
            graphic_input += ["-c:v", "libvpx-vp9"]
        inputs += [*graphic_input, "-i", str(graphic_path)]
    pip_input_start = 1 + len(graphics)
    for piece in pieces:
        inputs += ["-i", str(piece["path"])]

    filter_parts: list[str] = []
    frame_w, frame_h = frame_size if frame_size is not None else probe_wh(base_path)

    for idx, graphic in enumerate(graphics, start=1):
        t = float(graphic["start"])
        place = graphic.get("place") or "full"
        if place == "full":
            # Full-frame renders are the video size. Draft and 4K frames differ,
            # so scale the file to the composite frame and overlay at 0,0.
            sw, sh = frame_w, frame_h
        else:
            sw = even(max(2, int(round(float(graphic["w"]) * frame_w))))
            sh = even(max(2, int(round(float(graphic["h"]) * frame_h))))
        filter_parts.append(
            f"[{idx}:v]scale={sw}:{sh},setpts=PTS-STARTPTS+{t}/TB[a{idx}]"
        )

    overlays: list[tuple] = []
    for idx, graphic in enumerate(graphics, start=1):
        overlays.append((graphic.get("z", idx), idx, "graphic", graphic))
    for pi, piece in enumerate(pieces):
        overlays.append((piece.get("z", 10_000 + pi), pi, "region", piece))
    overlays.sort(key=lambda item: (item[0], 0 if item[2] == "graphic" else 1))

    current = "[0:v]"
    step = 0
    for _z, idx, kind, payload in overlays:
        step += 1
        next_label = f"[v{step}]"
        if kind == "graphic":
            t = float(payload["start"])
            end = float(payload["end"])
            place = payload.get("place") or "full"
            if place == "full":
                filter_parts.append(
                    f"{current}[a{idx}]overlay=enable='between(t,{t:.3f},{end:.3f})'{next_label}"
                )
            else:
                x = int(round(float(payload.get("x") or 0) * frame_w))
                y = int(round(float(payload.get("y") or 0) * frame_h))
                filter_parts.append(
                    f"{current}[a{idx}]overlay={x}:{y}:enable='between(t,{t:.3f},{end:.3f})'"
                    f"{next_label}"
                )
        else:
            t = float(payload["start"])
            end = t + float(payload["duration"])
            layout = payload["layout"]
            style = payload["style"] or {}
            inp = pip_input_start + idx
            shifted = f"[pips{idx}]"
            filter_parts.append(f"[{inp}:v]setpts=PTS-STARTPTS+{t}/TB{shifted}")
            pip_filters, pip_label = build_pip_overlay_filters(
                shifted, layout, style, str(idx)
            )
            filter_parts.extend(pip_filters)
            x, y = int(layout["x"]), int(layout["y"])
            filter_parts.append(
                f"{current}{pip_label}overlay={x}:{y}:enable='between(t,{t:.9f},{end:.9f})'"
                f"{next_label}"
            )
        current = next_label

    if has_subs:
        for si, subs_path in enumerate(subtitle_layers):
            subs_abs = str(subs_path.resolve()).replace(":", r"\:").replace("'", r"\'")
            next_label = "[outv]" if si == len(subtitle_layers) - 1 else f"[vs{si}]"
            filter_parts.append(f"{current}subtitles='{subs_abs}'{next_label}")
            current = next_label
        out_label = "[outv]"
    else:
        filter_parts.append(f"{current}null[outv]")
        out_label = "[outv]"

    filter_complex = ";".join(filter_parts)

    if draft:
        preset, crf = "ultrafast", "28"
    else:
        preset, crf = "fast", "18"

    cmd = [
        "ffmpeg",
        "-y",
        *inputs,
        "-filter_complex",
        filter_complex,
        "-map",
        out_label,
        "-map",
        "0:a",
        "-c:v",
        "libx264",
        "-preset",
        preset,
        "-crf",
        crf,
        "-pix_fmt",
        "yuv420p",
        *audio_codec,
        "-movflags",
        "+faststart",
        str(out_path),
    ]
    print(f"compositing → {out_path.name}")
    print(
        f"  graphics: {len(graphics)}, pip: {len(pieces)}, "
        f"subtitles: {len(subtitle_layers)}"
    )
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


if __name__ == "__main__":
    main()

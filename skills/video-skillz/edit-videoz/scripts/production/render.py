"""Render a video from the top-level EDL.

Pipeline:

  1. Per-range extract with sync-adjusted seeks: video from
     `range.active_clip`, audio from `range.audio_source`, color grade,
     and 30ms audio fades. Video is snapped to a whole-frame duration;
     audio is sample-accurate PCM so Advanced Audio Coding (AAC) encoder
     priming cannot accumulate.
  2. Lossless -c copy concat into base.mp4 (A-roll on the edit clock)
  3. Optional PIP pieces from top-level `edl.pip` (edit clock windows),
     with the same segment color grade as A-roll
  4. Final filter graph on the edit clock:
     A-roll → graphics → PIP inset → subtitles LAST
     AAC is encoded once here, not per clip

The cut list is `edit/edl.json`. Segment `edit/<n>/edl.json` may set
`caption_style`, `grading_style`, and `pip_style`. Caption and PIP styles
merge onto the top-level object (segment keys win). Grading replaces.
Audio reference clip name and clip offsets live in `edit/<n>/sync.json`.

Usage:
    python scripts/production/render.py -o edit/edit.mp4
    python scripts/production/render.py -o draft.mp4 --draft
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from grading.json_to_grade_vf import json_to_grade_vf_string
except Exception:
    def json_to_grade_vf_string(data):  # type: ignore
        sys.exit("json_to_grade_vf.py is required for color grading")

try:
    from srt_timeline import build_timeline_srt
except Exception:
    def build_timeline_srt(*args, **kwargs):  # type: ignore
        sys.exit("srt_timeline.py is required for burn-in captions")


def main() -> None:
    #==================================================
    # CLI Argument Inputs
    #==================================================
    ap = argparse.ArgumentParser(description="Render a video from an EDL")
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
            "(default: <edit>/clip_transcriptions next to the top-level EDL)."
        ),
    )
    args = ap.parse_args()

    edl_path = Path("edit").resolve() / "edl.json"
    if not edl_path.exists():
        sys.exit(f"edl not found: {edl_path}")

    edl = json.loads(edl_path.read_text())
    if not isinstance(edl.get("ranges"), list) or not edl["ranges"]:
        sys.exit("edl.ranges is required (edit/edl.json must be the top-level cut list)")
    if not isinstance(edl.get("sources"), dict) or not edl["sources"]:
        sys.exit("edl.sources is required")
    for i, r in enumerate(edl["ranges"]):
        if not r.get("audio_source"):
            sys.exit(f"range[{i}] audio_source is required")
        if not r.get("active_clip"):
            sys.exit(f"range[{i}] active_clip is required")

    edit_dir = edl_path.parent
    out_path = args.output.resolve()
    segment_cache: dict[int, dict] = {}

    ############################################################
    # Video Type Settings (from EDL)
    ############################################################

    video_type = edl.get("video_type") or {}
    if video_type and not isinstance(video_type, dict):
        sys.exit("edl.video_type must be an object (copy the video-type JSON into the EDL)")

    fps = int(video_type["fps"]) if "fps" in video_type else 30
    orientation = str(video_type.get("orientation") or "").strip().lower()
    resolution = str(video_type.get("resolution") or "").strip().upper()

    out_size: tuple[int, int] | None = None
    if orientation or resolution:
        if orientation not in ("landscape", "portrait"):
            sys.exit(
                "edl.video_type.orientation must be landscape or portrait, "
                f"got: {video_type.get('orientation')!r}"
            )
        if resolution not in ("HD", "4K"):
            sys.exit(
                "edl.video_type.resolution must be HD or 4K, "
                f"got: {video_type.get('resolution')!r}"
            )
        sizes = {
            ("landscape", "HD"): (1920, 1080),
            ("landscape", "4K"): (3840, 2160),
            ("portrait", "HD"): (1080, 1920),
            ("portrait", "4K"): (2160, 3840),
        }
        out_size = sizes[(orientation, resolution)]

    print(
        f"edl.video_type → fps={fps} orientation={orientation or None} "
        f"resolution={resolution or None} out_size={out_size}"
    )

    #==================================================
    # Caption burn (top-level caption_style, segment keys merged on)
    #==================================================

    subtitle_layers: list[tuple[Path, str]] = []
    skill_style_keys = {"case", "chars_per_line", "num_lines"}

    caption_groups: dict[str, dict] = {}
    for i, r in enumerate(edl["ranges"]):
        settings = range_settings(edit_dir, edl, r, segment_cache)
        caption_style = settings["caption_style"]
        if not caption_style:
            continue

        if not isinstance(caption_style, dict):
            sys.exit('caption_style must be an object, omitted, or "none"')

        key = json.dumps(caption_style, sort_keys=True)
        if key not in caption_groups:
            caption_groups[key] = {"style": caption_style, "indices": []}
        caption_groups[key]["indices"].append(i)

    if caption_groups:
        transcripts_dir = (
            args.transcripts_dir.resolve()
            if args.transcripts_dir is not None
            else edit_dir / "clip_transcriptions"
        )
        if not transcripts_dir.is_dir():
            sys.exit(
                f"caption_style requires transcripts at {transcripts_dir}"
            )

        for gi, group in enumerate(caption_groups.values()):
            caption_style = group["style"]
            caption_case = str(caption_style.get("case", "upper"))
            chars_per_line = int(caption_style.get("chars_per_line", 42))
            num_lines = int(caption_style.get("num_lines", 2))
            force_style_string = get_caption_force_style_string(
                caption_style, skill_style_keys
            )
            print(
                f"caption_style → case={caption_case} "
                f"chars_per_line={chars_per_line} num_lines={num_lines} "
                f"ranges={group['indices']}"
            )
            print(f"  force_style: {force_style_string}")

            burn_path = edit_dir / (
                "_burn_captions.srt"
                if len(caption_groups) == 1
                else f"_burn_captions_{gi}.srt"
            )
            n = build_timeline_srt(
                edl,
                transcripts_dir,
                burn_path,
                edit_dir=edit_dir,
                chars_per_line=chars_per_line,
                num_lines=num_lines,
                caption_case=caption_case,
                include_indices=set(group["indices"]),
            )
            subtitle_layers.append((burn_path, force_style_string))
            print(f"burn captions → {burn_path.name} ({n} cues)")

    # Effective frame size after draft scaling (matches extract_segment)
    frame_size = out_size
    if args.draft and out_size is not None:
        ow, oh = out_size
        if ow >= oh:
            frame_size = (1280, max(2, int(round(1280 * oh / ow / 2) * 2)))
        else:
            frame_size = (max(2, int(round(1280 * ow / oh / 2) * 2)), 1280)

    # 1. Extract per-range (sync + audio reference clip + segment grade)
    segment_paths, range_frames = extract_all_segments(
        edl,
        edit_dir,
        draft=args.draft,
        fps=fps,
        out_size=out_size,
        segment_cache=segment_cache,
    )

    # 2. Concat → base
    base_name = "base_draft.mp4" if args.draft else "base.mp4"
    base_path = edit_dir / base_name
    concat_segments(segment_paths, base_path, edit_dir)

    # 3. Optional PIP pieces (top-level edl.pip, edit clock, same grade as A-roll)
    pip_pieces = extract_pip_track(
        edl,
        edit_dir,
        draft=args.draft,
        fps=fps,
        frame_size=frame_size,
        segment_cache=segment_cache,
        range_frames=range_frames,
    )

    # 4. Composite on the edit clock: A-roll → graphics → PIP → captions LAST
    graphics = edl.get("graphics") or []
    build_final_composite(
        base_path,
        graphics,
        subtitle_layers,
        out_path,
        pip_pieces=pip_pieces,
        frame_size=frame_size,
    )

    size_mb = out_path.stat().st_size / (1024 * 1024)
    print(f"\ndone: {out_path} ({size_mb:.1f} MB)")


#==================================================
# Utilities
#==================================================

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

def is_hdr_source(video: Path) -> bool:
    """Return True if the source uses a PQ or HLG transfer function."""
    try:
        out = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=color_transfer",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(video),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        return out.stdout.strip() in HDR_TRANSFERS
    except subprocess.CalledProcessError:
        return False


def is_portrait_source(video: Path) -> bool:
    """Return True if the video's height > width (portrait / vertical)."""
    try:
        out = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=width,height",
                "-of",
                "csv=p=0",
                str(video),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        w, h = map(int, out.stdout.strip().split(","))
        return h > w
    except Exception:
        return False


def probe_wh(video: Path) -> tuple[int, int]:
    out = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "csv=p=0",
            str(video),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    w, h = map(int, out.stdout.strip().split(","))
    return w, h


def has_audio_stream(path: Path) -> bool:
    try:
        out = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-select_streams", "a:0",
                "-show_entries", "stream=index",
                "-of", "csv=p=0",
                str(path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        return bool(out.stdout.strip())
    except Exception:
        return False


def even(n: int) -> int:
    return max(2, int(n) // 2 * 2)


#==================================================
# Sync — segment clock → source time
#==================================================

def sync_offset_seconds(sync: dict | None, source_key: str) -> float:
    """offset = source_time − segment_clock_time for the same instant."""
    entry = (sync or {}).get(source_key)
    if entry is None:
        return 0.0
    return float(entry)


def segment_clock_to_source_time(
    sync: dict | None, source_key: str, segment_t: float
) -> float:
    return segment_t + sync_offset_seconds(sync, source_key)


def source_segment_number(source_key: str) -> int | None:
    prefix = str(source_key).split("-", 1)[0]
    if prefix.isdigit():
        return int(prefix)
    return None


def range_settings(
    edit_dir: Path,
    edl: dict,
    r: dict,
    cache: dict[int, dict],
) -> dict:
    """Merge top-level EDL with `edit/<n>/edl.json` and `sync.json` for one range.

    Segment `caption_style` and `pip_style` merge onto the top-level object
    (segment keys win). `"none"` on the segment disables that style.
    Segment `grading_style` replaces the top-level value when the key is
    present. Audio reference clip name and clip offsets live in
    `edit/<n>/sync.json`. `pip` windows live on the top-level EDL.
    """
    audio_key = Path(str(r["audio_source"])).stem
    active_key = Path(str(r["active_clip"])).stem
    n = source_segment_number(audio_key)
    if n is not None and n not in cache:
        edl_path = edit_dir / str(n) / "edl.json"
        if edl_path.is_file():
            try:
                seg_edl = json.loads(edl_path.read_text())
            except json.JSONDecodeError as e:
                sys.exit(f"invalid JSON in {edl_path}: {e}")
        else:
            seg_edl = {}

        sync_path = edit_dir / str(n) / "sync.json"
        if sync_path.is_file():
            try:
                sync_data = json.loads(sync_path.read_text())
            except json.JSONDecodeError as e:
                sys.exit(f"invalid JSON in {sync_path}: {e}")
            if not isinstance(sync_data, dict):
                sys.exit(f"{sync_path} must be a JSON object")
        else:
            sync_data = {}

        audio_reference_from_sync = sync_data.get("audio_reference_clip")
        offsets = {
            k: v
            for k, v in sync_data.items()
            if k != "audio_reference_clip" and isinstance(v, (int, float))
        }
        cache[n] = {
            "edl": seg_edl,
            "sync": offsets,
            "audio_reference_clip": audio_reference_from_sync,
        }

    packed = (
        cache[n]
        if n is not None
        else {"edl": {}, "sync": {}, "audio_reference_clip": None}
    )
    seg = packed["edl"] if isinstance(packed.get("edl"), dict) else {}

    grading_style = seg["grading_style"] if "grading_style" in seg else edl.get("grading_style")
    if grading_style is None or grading_style == "none" or not isinstance(grading_style, dict):
        grading_style = None

    styles: dict[str, dict | None] = {}
    for key in ("caption_style", "pip_style"):
        base = edl.get(key)
        over = seg[key] if key in seg else None
        if over == "none":
            styles[key] = None
        elif over is None:
            if base is None or base == "none" or not isinstance(base, dict):
                styles[key] = None
            else:
                styles[key] = dict(base)
        elif not isinstance(over, dict):
            sys.exit(f'{key} must be an object, omitted, or "none"')
        else:
            merged = dict(base) if isinstance(base, dict) else {}
            merged.update(over)
            styles[key] = merged
    caption_style = styles["caption_style"]
    pip_style = styles["pip_style"]

    audio_reference_clip = packed.get("audio_reference_clip")
    if audio_reference_clip is not None and audio_reference_clip != "":
        audio_reference_clip = Path(str(audio_reference_clip)).stem
    else:
        audio_reference_clip = None

    sync = packed["sync"] if isinstance(packed.get("sync"), dict) else {}

    return {
        "n": n,
        "audio_source": audio_key,
        "active_clip": active_key,
        "grading_style": grading_style,
        "caption_style": caption_style,
        "pip_style": pip_style,
        "audio_reference_clip": audio_reference_clip,
        "sync": sync,
    }


def get_caption_force_style_string(
    caption_style: dict, skill_style_keys: set[str]
) -> str:
    force_style_string = (
        "FontName=Helvetica,FontSize=18,Bold=1,"
        "PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BackColour=&H00000000,"
        "BorderStyle=1,Outline=2,Shadow=0,"
        "Alignment=2,MarginV=90"
    )

    parts: list[str] = []
    bool_style_keys = {"bold", "italic", "underline", "strike_out"}
    for key, value in caption_style.items():
        if key in skill_style_keys:
            continue

        # snake_case → ASS PascalCase (font_name → FontName, primary_color → PrimaryColour)
        ass_key = "".join(
            "Colour" if p == "color" else p.capitalize()
            for p in key.split("_")
        )

        # ASS toggles are -1 on / 0 off
        if key in bool_style_keys:
            if not isinstance(value, bool):
                sys.exit(
                    f"caption style {key} must be a boolean, got: {value!r}"
                )
            value = -1 if value else 0
        elif (
            isinstance(value, str)
            and key.endswith("_color")
            and not value.startswith("&H")
        ):
            hex_rgb = value.removeprefix("#")
            if len(hex_rgb) != 6:
                sys.exit(
                    f"caption style {key} must be RRGGBB or &HAABBGGRR, "
                    f"got: {value!r}"
                )
            value = f"&H00{hex_rgb[4:6]}{hex_rgb[2:4]}{hex_rgb[0:2]}".upper()
        parts.append(f"{ass_key}={value}")

    if parts:
        force_style_string = ",".join(parts)
    return force_style_string


#==================================================
# PIP geometry
#==================================================

def resolve_pip_geometry(
    style: dict,
    out_size: tuple[int, int] | None,
) -> tuple[dict, str]:
    """Return ({x,y,w,h} on the output frame, shape) from pip_style."""
    if out_size is None:
        sys.exit(
            "pip requires edl.video_type.orientation and "
            "edl.video_type.resolution (HD or 4K)"
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
            sys.exit(f"pip_style.aspect must be W:H with positive numbers, got: {aspect!r}")
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


def require_pip_crop(edl: dict) -> dict:
    """Required face crop on the pip source: {x, y, w, h} in source pixels."""
    pip = edl.get("pip") or {}
    crop = pip.get("crop")
    if not crop or not all(k in crop for k in ("x", "y", "w", "h")):
        sys.exit("edl.pip.crop is required with x, y, w, h in source pixels")
    out = {k: int(crop[k]) for k in ("x", "y", "w", "h")}
    if out["w"] <= 0 or out["h"] <= 0:
        sys.exit(f"edl.pip.crop w and h must be positive, got: {crop!r}")
    return out


# -------- Per-segment extraction (Rule 2 + Rule 3) --------------------------


def extract_segment(
    source: Path,
    seg_start: float,
    n_frames: int,
    grade_filter: str,
    out_path: Path,
    draft: bool = False,
    fps: int = 30,
    out_size: tuple[int, int] | None = None,
    audio_source: Path | None = None,
    audio_start: float | None = None,
) -> None:
    """Extract a cut range as its own MP4 with optional grade and fades.

    Optional `out_size` is `(width, height)` from video-type orientation +
    resolution (HD/4K). Without `out_size`, scale to 1920 (or 1280 in draft)
    on the long axis.

    When `audio_source` is set, video is taken from `source` at `seg_start` and
    audio from `audio_source` at `audio_start`. Both seeks are source time
    (already remapped from the segment clock).

    Duration is an integer frame count so video cannot round up past audio.
    Audio is trimmed by sample count and stored as PCM (Pulse Code Modulation)
    so AAC priming is not baked into each clip.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)

    audio_rate = 48000
    preroll = 0.25
    duration = n_frames / fps
    n_samples = int(round(n_frames * audio_rate / fps))

    vf_parts: list[str] = []
    if is_hdr_source(source):
        vf_parts.append(TONEMAP_CHAIN)

    if out_size is not None:
        ow, oh = out_size
        if draft:
            if ow >= oh:
                ow, oh = 1280, max(2, int(round(1280 * oh / ow / 2) * 2))
            else:
                ow, oh = max(2, int(round(1280 * ow / oh / 2) * 2)), 1280
        vf_parts.append(f"scale={ow}:{oh}")
    else:
        portrait = is_portrait_source(source)
        if draft:
            scale = "scale=-2:1280" if portrait else "scale=1280:-2"
        else:
            scale = "scale=-2:1920" if portrait else "scale=1920:-2"
        vf_parts.append(scale)

    if grade_filter:
        vf_parts.append(grade_filter)
    vf = ",".join(vf_parts)

    # 30ms audio fades at both edges (Rule 3) — prevent pops
    fade_out_start = max(0.0, duration - 0.03)
    af = f"afade=t=in:st=0:d=0.03,afade=t=out:st={fade_out_start:.3f}:d=0.03"

    if draft:
        preset, crf = "ultrafast", "28"
    else:
        preset, crf = "fast", "20"

    use_separate_audio = (
        audio_source is not None
        and audio_start is not None
        and has_audio_stream(audio_source)
    )

    a_origin = float(audio_start) if use_separate_audio else seg_start
    v_seek = max(0.0, seg_start - preroll)
    a_seek = max(0.0, a_origin - preroll)
    v_end = seg_start + duration
    a_end = a_origin + duration

    # Fast input seek, then trim on original timestamps (-copyts) so AAC
    # packet boundaries cannot shift the cut. Pad/trim audio to n_samples
    # and video to n_frames so concat cannot drift.
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

    cmd: list[str] = ["ffmpeg", "-y", "-copyts"]
    if use_separate_audio:
        cmd += [
            "-ss", f"{v_seek:.6f}", "-i", str(source),
            "-ss", f"{a_seek:.6f}", "-i", str(audio_source),
            "-filter_complex",
            f"[0:v]{v_chain}[v];[1:a]{a_chain}[a]",
            "-map", "[v]",
            "-map", "[a]",
        ]
    else:
        cmd += [
            "-ss", f"{v_seek:.6f}",
            "-i", str(source),
            "-filter_complex",
            f"[0:v]{v_chain}[v];[0:a]{a_chain}[a]",
            "-map", "[v]",
            "-map", "[a]",
        ]

    cmd += [
        "-frames:v", str(n_frames),
        "-c:v", "libx264",
        "-preset", preset,
        "-crf", crf,
        "-pix_fmt", "yuv420p",
        "-r", str(fps),
        "-c:a", "pcm_s16le",
        "-ar", str(audio_rate),
        "-movflags", "+faststart",
        str(out_path),
    ]
    proc = subprocess.run(
        cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE
    )
    if proc.returncode != 0:
        err = proc.stderr.decode("utf-8", errors="replace")
        sys.exit(f"ffmpeg extract failed ({out_path.name}):\n{err[-4000:]}")


def extract_all_segments(
    edl: dict,
    edit_dir: Path,
    draft: bool = False,
    fps: int = 24,
    out_size: tuple[int, int] | None = None,
    segment_cache: dict[int, dict] | None = None,
) -> tuple[list[Path], list[int]]:
    """Extract every EDL range into edit_dir/clips_graded/seg_NN.mp4.

    Range start/end are already on `range.audio_source`. Sync remaps the
    video seek onto `range.active_clip` only. Grade comes from the
    segment EDL when set, else the top-level EDL.

    Returns (segment paths, per-range frame counts). Frame counts are
    error-diffused so the cumulative edit clock stays within half a frame
    of the Edit Decision List (EDL) times used by graphics and PIP.
    """
    if segment_cache is None:
        segment_cache = {}

    clips_dir = edit_dir / ("clips_draft" if draft else "clips_graded")
    clips_dir.mkdir(parents=True, exist_ok=True)

    ranges = edl["ranges"]
    sources = edl["sources"]

    seg_paths: list[Path] = []
    range_frames: list[int] = []
    accum_edl = 0.0
    accum_frames = 0
    print(f"extracting {len(ranges)} range(s) → {clips_dir.name}/")

    for i, r in enumerate(ranges):
        settings = range_settings(edit_dir, edl, r, segment_cache)
        audio_key = settings["audio_source"]
        active_key = settings["active_clip"]
        if audio_key not in sources:
            sys.exit(f"range[{i}] audio_source {audio_key!r} missing from sources")
        if active_key not in sources:
            sys.exit(f"range[{i}] active_clip {active_key!r} missing from sources")
        src_path = Path(sources[active_key])
        seg_start = float(r["start"])
        seg_end = float(r["end"])
        duration = seg_end - seg_start
        accum_edl += duration
        n_frames = int(round(accum_edl * fps)) - accum_frames

        if n_frames < 1:
            n_frames = 1

        accum_frames += n_frames
        range_frames.append(n_frames)
        video_start = (
            seg_start
            if active_key == audio_key
            else segment_clock_to_source_time(
                settings["sync"], active_key, seg_start
            )
        )
        out_path = clips_dir / f"seg_{i:02d}_{active_key}.mp4"
        grade_filter = json_to_grade_vf_string(settings["grading_style"])

        split_audio = audio_key != active_key
        audio_source = Path(sources[audio_key]) if split_audio else None
        audio_seek = seg_start if split_audio else None

        sync_note = ""
        if abs(video_start - seg_start) > 0.0005:
            sync_note = f"  v@{video_start:.2f}"
        if split_audio:
            sync_note += f"  a={audio_key}"
        grade_note = "  grade" if grade_filter else ""
        print(
            f"  [{i:02d}] {active_key}  {seg_start:7.2f}-{seg_end:7.2f}  "
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
            audio_start=audio_seek,
        )
        seg_paths.append(out_path)

    return seg_paths, range_frames


#==================================================
# PIP track — edit clock windows, source seeks via A-roll ranges
#==================================================

def extract_pip_track(
    edl: dict,
    edit_dir: Path,
    draft: bool = False,
    fps: int = 30,
    frame_size: tuple[int, int] | None = None,
    segment_cache: dict[int, dict] | None = None,
    range_frames: list[int] | None = None,
) -> list[dict]:
    """Extract PIP clips from top-level `edl.pip`.

    Each EDL entry is `{source, start, end, crop}` on the edit clock (same
    as graphics). A piece is emitted for every overlap with an A-roll range
    from the same segment; that overlap is mapped back to the segment clock
    for the source seek. Grade comes from the overlapping range's segment
    EDL when set, else the top-level EDL. Returns `{path, start, duration,
    layout, style}` on the snapped A-roll frame clock for compositing.
    """
    pip_entries = edl.get("pip") or []
    if not isinstance(pip_entries, list) or not pip_entries:
        return []

    if frame_size is None:
        sys.exit(
            "pip requires edl.video_type.orientation and "
            "edl.video_type.resolution (HD or 4K)"
        )

    if segment_cache is None:
        segment_cache = {}

    sources = edl["sources"]
    ranges = edl["ranges"]
    if range_frames is None or len(range_frames) != len(ranges):
        sys.exit("extract_pip_track requires range_frames from extract_all_segments")

    # Snap PIP windows onto the encoded A-roll frame clock. Overlay start
    # and duration both come from these frame numbers so adjacent pieces
    # of the same window cannot leave a sub-frame hole.
    edl_starts = [0.0]
    frame_starts = [0]
    accum_edl = 0.0
    accum_frames = 0
    for i, r in enumerate(ranges):
        accum_edl += float(r["end"]) - float(r["start"])
        accum_frames += range_frames[i]
        edl_starts.append(accum_edl)
        frame_starts.append(accum_frames)

    pip_span_frames: list[tuple[int, int]] = []
    for pip_i, pip in enumerate(pip_entries):
        if not isinstance(pip, dict):
            sys.exit(f"edl.pip entries must be objects, got: {pip!r}")

        pair: list[int] = []
        for key in ("start", "end"):
            t = float(pip[key])
            frame = frame_starts[-1]
            if t <= edl_starts[0]:
                frame = 0
            elif t < edl_starts[-1]:
                for ri in range(len(ranges)):
                    a = edl_starts[ri]
                    b = edl_starts[ri + 1]
                    if t < b or ri == len(ranges) - 1:
                        dur = b - a
                        n = range_frames[ri]
                        lo = frame_starts[ri]
                        hi = lo + n
                        if dur <= 0:
                            frame = lo
                        else:
                            frame = lo + int(round((t - a) / dur * n))
                        if frame < lo:
                            frame = lo
                        if frame > hi:
                            frame = hi
                        break
            pair.append(frame)

        if pair[1] < pair[0]:
            sys.exit(f"edl.pip[{pip_i}] end is before start")
        pip_span_frames.append((pair[0], pair[1]))

    clips_dir = edit_dir / ("clips_pip_draft" if draft else "clips_pip")
    clips_dir.mkdir(parents=True, exist_ok=True)
    pieces: list[dict] = []
    used = [False] * len(pip_entries)
    piece_i = 0
    preroll = 0.25

    for i, r in enumerate(ranges):
        range_start = float(r["start"])
        range_end = float(r["end"])
        edl_dur = range_end - range_start
        range_n = range_frames[i]
        range_frame_start = frame_starts[i]
        range_frame_end = range_frame_start + range_n
        settings = range_settings(edit_dir, edl, r, segment_cache)
        n = settings["n"]

        for pip_i, pip in enumerate(pip_entries):
            pip_source = pip.get("source")
            if not pip_source:
                sys.exit("edl.pip.source is required")
            if pip_source not in sources:
                sys.exit(f"edl.pip.source {pip_source!r} missing from sources")
            if source_segment_number(pip_source) != n:
                continue

            pip_sf, pip_ef = pip_span_frames[pip_i]
            ov_start = max(range_frame_start, pip_sf)
            ov_end = min(range_frame_end, pip_ef)
            if ov_end <= ov_start:
                continue

            n_frames_pip = ov_end - ov_start
            duration = n_frames_pip / fps
            if range_n > 0 and edl_dur > 0:
                segment_t = range_start + (
                    (ov_start - range_frame_start) / range_n * edl_dur
                )
            else:
                segment_t = range_start
            pip_style = settings["pip_style"]
            if pip_style is None:
                sys.exit(
                    "edl.pip requires pip_style on edit/edl.json or "
                    f"edit/{n}/edl.json"
                )
            layout, shape = resolve_pip_geometry(pip_style, frame_size)
            pw, ph = int(layout["w"]), int(layout["h"])
            face_crop = require_pip_crop({"pip": pip})
            pip_source_path = Path(sources[pip_source])
            video_start = segment_clock_to_source_time(
                settings["sync"], pip_source, segment_t
            )
            place_at = ov_start / fps
            video_end = video_start + duration
            v_seek = max(0.0, video_start - preroll)

            vf_parts: list[str] = []
            if is_hdr_source(pip_source_path):
                vf_parts.append(TONEMAP_CHAIN)
            vf_parts.append(
                f"crop={face_crop['w']}:{face_crop['h']}:{face_crop['x']}:{face_crop['y']}"
            )
            vf_parts.append(f"scale={pw}:{ph}:force_original_aspect_ratio=increase")
            vf_parts.append(f"crop={pw}:{ph}")
            grade_filter = json_to_grade_vf_string(settings["grading_style"])
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

            out_path = clips_dir / f"pip_{piece_i:02d}.mp4"
            grade_note = "  grade" if grade_filter else ""
            print(
                f"  pip [{piece_i:02d}] {pip_source}  "
                f"edit {place_at:.2f}-{place_at + duration:.2f}  "
                f"frames {ov_start}-{ov_end}  src@{video_start:.2f}  "
                f"layout={pw}x{ph} @ ({layout['x']},{layout['y']}) shape={shape}{grade_note}"
            )
            cmd = [
                "ffmpeg", "-y", "-copyts",
                "-ss", f"{v_seek:.6f}", "-i", str(pip_source_path),
                "-filter_complex", f"[0:v]{v_chain}[v]",
                "-map", "[v]",
                "-frames:v", str(n_frames_pip),
                "-an",
                "-c:v", "libx264",
                "-preset", "ultrafast" if draft else "fast",
                "-crf", "28" if draft else "18",
                "-pix_fmt", "yuv420p",
                "-r", str(fps),
                "-movflags", "+faststart",
                str(out_path),
            ]
            proc = subprocess.run(
                cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE
            )
            if proc.returncode != 0:
                err = proc.stderr.decode("utf-8", errors="replace")
                sys.exit(f"ffmpeg pip extract failed ({out_path.name}):\n{err[-4000:]}")
            pieces.append(
                {
                    "path": out_path,
                    "start": place_at,
                    "duration": duration,
                    "start_frame": ov_start,
                    "n_frames": n_frames_pip,
                    "pip_i": pip_i,
                    "layout": layout,
                    "style": pip_style,
                }
            )
            used[pip_i] = True
            piece_i += 1

    by_pip: dict[int, list[dict]] = {}
    for p in pieces:
        by_pip.setdefault(p["pip_i"], []).append(p)

    for pip_i, group in by_pip.items():
        group.sort(key=lambda p: p["start_frame"])
        pip_n = source_segment_number(pip_entries[pip_i].get("source"))

        for a, b in zip(group, group[1:]):
            a_end = a["start_frame"] + a["n_frames"]
            gap = b["start_frame"] - a_end

            if gap < 0:
                sys.exit(
                    f"pip[{pip_i}] pieces overlap by {-gap} frame(s) "
                    f"at frame {a_end}"
                )

            if gap == 0:
                continue

            for ri, r in enumerate(ranges):
                rs = frame_starts[ri]
                re = rs + range_frames[ri]
                if re <= a_end or rs >= b["start_frame"]:
                    continue
                settings = range_settings(edit_dir, edl, r, segment_cache)
                if settings["n"] == pip_n:
                    sys.exit(
                        f"pip[{pip_i}] {gap}-frame hole between pieces "
                        f"at frame {a_end}"
                    )

    for i, pip in enumerate(pip_entries):
        if used[i]:
            continue
        src = pip.get("source") if isinstance(pip, dict) else pip
        start = pip.get("start") if isinstance(pip, dict) else "?"
        end = pip.get("end") if isinstance(pip, dict) else "?"
        print(
            f"warning: pip[{i}] {src} {start}-{end} "
            f"overlapped no same-segment A-roll range"
        )

    if pieces:
        print(f"extracted {len(pieces)} PIP piece(s) → {clips_dir.name}/")

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
    border_px = max(0, int(style.get("border_px") or 0))
    border_color = parse_hex_color(str(style.get("border_color") or "#FFFFFF"))
    radius_frac = float(style.get("corner_radius_fraction") or 0.0)
    radius = int(round(min(pw, ph) * radius_frac)) if shape != "circle" else 0

    parts: list[str] = []
    src = src_label
    pad_label = f"[pippad{tag}]"
    out_label = f"[pipa{tag}]"

    # Circle: paint the stroke as an annulus in geq. Do not pad a square
    # ring and then clip it — an inscribed circle only keeps the stroke on
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
    # distance. Do not pad a square ring then clip — the rounded mask
    # cuts through the stroke at the corners.
    r = max(0, min(radius, min(pw, ph) // 2))
    if r > 0:
        dx = f"abs(X-{pw}/2)-({pw}/2-{r})"
        dy = f"abs(Y-{ph}/2)-({ph}/2-{r})"
        dist = (
            f"hypot(max({dx}\\,0)\\,max({dy}\\,0))"
            f"+min(max({dx}\\,{dy})\\,0)-{r}"
        )
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
    subtitle_layers: list[tuple[Path, str]],
    out_path: Path,
    pip_pieces: list[dict] | None = None,
    frame_size: tuple[int, int] | None = None,
) -> None:
    """Final pass on the edit clock: A-roll → graphics → PIP → subtitles LAST → out."""
    pieces = pip_pieces or []
    has_graphics = bool(graphics)
    has_pip = bool(pieces)
    has_subs = bool(subtitle_layers)

    if not has_graphics and not has_pip and not has_subs:
        run(
            [
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-i", str(base_path),
                "-c:v", "copy",
                "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
                "-movflags", "+faststart",
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
            sys.exit(f"edl.graphics start ({t}) must be before end ({end})")
        # Limit the read so a longer file cannot outlast the overlay window
        # (overlay keeps going until every input is exhausted).
        inputs += ["-t", f"{end - t:.3f}", "-i", str(Path(graphic["file"]))]
    pip_input_start = 1 + len(graphics)
    for piece in pieces:
        inputs += ["-i", str(piece["path"])]

    filter_parts: list[str] = []
    if has_graphics:
        # Graphics are full-frame HyperFrames renders (typically 1920×1080).
        # Draft base is 1280×720 and 4K output is 3840×2160, so overlay at 0:0
        # without scale would crop or under-cover. Match the output frame.
        frame_w, frame_h = frame_size if frame_size is not None else probe_wh(base_path)
        for idx, graphic in enumerate(graphics, start=1):
            t = float(graphic["start"])
            filter_parts.append(
                f"[{idx}:v]scale={frame_w}:{frame_h},setpts=PTS-STARTPTS+{t}/TB[a{idx}]"
            )

    current = "[0:v]"
    for idx, graphic in enumerate(graphics, start=1):
        t = float(graphic["start"])
        end = float(graphic["end"])
        next_label = f"[v{idx}]"
        filter_parts.append(
            f"{current}[a{idx}]overlay=enable='between(t,{t:.3f},{end:.3f})'{next_label}"
        )
        current = next_label

    for pi, piece in enumerate(pieces):
        t = float(piece["start"])
        end = t + float(piece["duration"])
        layout = piece["layout"]
        style = piece["style"] or {}
        inp = pip_input_start + pi
        shifted = f"[pips{pi}]"
        filter_parts.append(f"[{inp}:v]setpts=PTS-STARTPTS+{t}/TB{shifted}")
        pip_filters, pip_label = build_pip_overlay_filters(
            shifted, layout, style, str(pi)
        )
        filter_parts.extend(pip_filters)
        x, y = int(layout["x"]), int(layout["y"])
        next_label = f"[vpip{pi}]"
        filter_parts.append(
            f"{current}{pip_label}overlay={x}:{y}:enable='between(t,{t:.9f},{end:.9f})'"
            f"{next_label}"
        )
        current = next_label

    if has_subs:
        for si, (subs_path, force_style_string) in enumerate(subtitle_layers):
            subs_abs = str(subs_path.resolve()).replace(":", r"\:").replace("'", r"\'")
            next_label = (
                "[outv]" if si == len(subtitle_layers) - 1 else f"[vs{si}]"
            )
            filter_parts.append(
                f"{current}subtitles='{subs_abs}':force_style='{force_style_string}'{next_label}"
            )
            current = next_label
        out_label = "[outv]"
    else:
        filter_parts.append(f"{current}null[outv]")
        out_label = "[outv]"

    filter_complex = ";".join(filter_parts)

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
        "fast",
        "-crf",
        "18",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-ar",
        "48000",
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

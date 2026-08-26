"""Render a video from the top-level EDL.

Pipeline:

  1. Per-range extract with sync-adjusted seeks, optional audio from the
     audio reference clip, color grade, and 30ms audio fades
  2. Lossless -c copy concat into base.mp4 (A-roll on the edit clock)
  3. Optional PIP pieces from top-level `edl.pip` (edit clock windows),
     with the same segment color grade as A-roll
  4. Final filter graph on the edit clock:
     A-roll → graphics → PIP inset → subtitles LAST

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
    segment_paths = extract_all_segments(
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
    )

    # 4. Composite on the edit clock: A-roll → graphics → PIP → captions LAST
    graphics = edl.get("graphics") or []
    build_final_composite(
        base_path,
        graphics,
        subtitle_layers,
        out_path,
        pip_pieces=pip_pieces,
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
    src_name = r["source"]
    n = source_segment_number(src_name)
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
        "source": src_name,
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
    duration: float,
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
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)

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

    cmd: list[str] = ["ffmpeg", "-y"]
    if use_separate_audio:
        cmd += [
            "-ss", f"{seg_start:.3f}", "-i", str(source),
            "-ss", f"{audio_start:.3f}", "-i", str(audio_source),
            "-t", f"{duration:.3f}",
            "-vf", vf,
            "-af", af,
            "-map", "0:v:0",
            "-map", "1:a:0",
        ]
    else:
        cmd += [
            "-ss", f"{seg_start:.3f}",
            "-i", str(source),
            "-t", f"{duration:.3f}",
            "-vf", vf,
            "-af", af,
        ]

    cmd += [
        "-c:v", "libx264",
        "-preset", preset,
        "-crf", crf,
        "-pix_fmt", "yuv420p",
        "-r", str(fps),
        "-c:a", "aac",
        "-b:a", "192k",
        "-ar", "48000",
        "-movflags", "+faststart",
        str(out_path),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def extract_all_segments(
    edl: dict,
    edit_dir: Path,
    draft: bool = False,
    fps: int = 24,
    out_size: tuple[int, int] | None = None,
    segment_cache: dict[int, dict] | None = None,
) -> list[Path]:
    """Extract every EDL range into edit_dir/clips_graded/seg_NN.mp4.

    Range start/end are on the segment clock. Sync remaps seeks onto each
    range source. Audio is `range.audio`, else that segment's
    `audio_reference_clip`, else the range source. Grade comes from the
    segment EDL when set, else the top-level EDL.
    """
    if segment_cache is None:
        segment_cache = {}

    clips_dir = edit_dir / ("clips_draft" if draft else "clips_graded")
    clips_dir.mkdir(parents=True, exist_ok=True)

    ranges = edl["ranges"]
    sources = edl["sources"]

    seg_paths: list[Path] = []
    print(f"extracting {len(ranges)} range(s) → {clips_dir.name}/")

    for i, r in enumerate(ranges):
        settings = range_settings(edit_dir, edl, r, segment_cache)
        src_name = r["source"]
        src_path = Path(sources[src_name])
        seg_start = float(r["start"])
        seg_end = float(r["end"])
        duration = seg_end - seg_start
        video_start = segment_clock_to_source_time(
            settings["sync"], src_name, seg_start
        )
        out_path = clips_dir / f"seg_{i:02d}_{src_name}.mp4"
        grade_filter = json_to_grade_vf_string(settings["grading_style"])

        audio_source = None
        audio_start = None
        audio_override = r.get("audio")
        if audio_override:
            audio_key = Path(str(audio_override)).stem
        else:
            audio_key = settings["audio_reference_clip"]
        if audio_key and audio_key != src_name:
            if audio_key not in sources:
                sys.exit(f"range[{i}] audio {audio_key!r} missing from sources")
            audio_source = Path(sources[audio_key])
            audio_start = segment_clock_to_source_time(
                settings["sync"], audio_key, seg_start
            )

        sync_note = ""
        if abs(video_start - seg_start) > 0.0005:
            sync_note = f"  src@{video_start:.2f}"
        grade_note = "  grade" if grade_filter else ""
        print(
            f"  [{i:02d}] {src_name}  {seg_start:7.2f}-{seg_end:7.2f}  "
            f"({duration:5.2f}s){sync_note}{grade_note}"
        )
        extract_segment(
            src_path,
            video_start,
            duration,
            grade_filter,
            out_path,
            draft=draft,
            fps=fps,
            out_size=out_size,
            audio_source=audio_source,
            audio_start=audio_start,
        )
        seg_paths.append(out_path)

    return seg_paths


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
) -> list[dict]:
    """Extract PIP clips from top-level `edl.pip`.

    Each EDL entry is `{source, start, end, crop}` on the edit clock (same
    as graphics). A piece is emitted for every overlap with an A-roll range
    from the same segment; that overlap is mapped back to the segment clock
    for the source seek. Grade comes from the overlapping range's segment
    EDL when set, else the top-level EDL. Returns `{path, start, duration,
    layout, style}` on the edit clock for compositing.
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
    clips_dir = edit_dir / ("clips_pip_draft" if draft else "clips_pip")
    clips_dir.mkdir(parents=True, exist_ok=True)
    pieces: list[dict] = []
    used = [False] * len(pip_entries)
    output_t = 0.0
    piece_i = 0

    for r in ranges:
        range_start = float(r["start"])
        range_end = float(r["end"])
        range_dur = range_end - range_start
        range_edit_start = output_t
        range_edit_end = output_t + range_dur
        settings = range_settings(edit_dir, edl, r, segment_cache)
        n = settings["n"]

        for pip_i, pip in enumerate(pip_entries):
            if not isinstance(pip, dict):
                sys.exit(f"edl.pip entries must be objects, got: {pip!r}")

            pip_source = pip.get("source")
            if not pip_source:
                sys.exit("edl.pip.source is required")
            if pip_source not in sources:
                sys.exit(f"edl.pip.source {pip_source!r} missing from sources")
            if source_segment_number(pip_source) != n:
                continue

            ov_edit_start = max(range_edit_start, float(pip["start"]))
            ov_edit_end = min(range_edit_end, float(pip["end"]))
            if ov_edit_end <= ov_edit_start:
                continue

            duration = ov_edit_end - ov_edit_start
            segment_t = range_start + (ov_edit_start - range_edit_start)
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
            place_at = ov_edit_start

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

            out_path = clips_dir / f"pip_{piece_i:02d}.mp4"
            grade_note = "  grade" if grade_filter else ""
            print(
                f"  pip [{piece_i:02d}] {pip_source}  "
                f"edit {ov_edit_start:.2f}-{ov_edit_end:.2f}  src@{video_start:.2f}  "
                f"layout={pw}x{ph} @ ({layout['x']},{layout['y']}) shape={shape}{grade_note}"
            )
            cmd = [
                "ffmpeg", "-y",
                "-ss", f"{video_start:.3f}",
                "-i", str(pip_source_path),
                "-t", f"{duration:.3f}",
                "-vf", vf,
                "-an",
                "-c:v", "libx264",
                "-preset", "ultrafast" if draft else "fast",
                "-crf", "28" if draft else "18",
                "-pix_fmt", "yuv420p",
                "-r", str(fps),
                "-movflags", "+faststart",
                str(out_path),
            ]
            subprocess.run(
                cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE
            )
            pieces.append(
                {
                    "path": out_path,
                    "start": place_at,
                    "duration": duration,
                    "layout": layout,
                    "style": pip_style,
                }
            )
            used[pip_i] = True
            piece_i += 1

        output_t += range_dur

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


def pip_alpha_expr(pw: int, ph: int, shape: str, radius: int) -> str:
    """ffmpeg geq alpha expression: 255 inside the shape, 0 outside."""
    if shape == "circle":
        r = min(pw, ph) // 2
        return (
            f"if(lte(pow(X-{pw}/2\\,2)+pow(Y-{ph}/2\\,2)\\,pow({r}\\,2))\\,255\\,0)"
        )

    # rect — optional rounded corners
    r = max(0, min(radius, min(pw, ph) // 2))
    if r <= 0:
        return "255"

    return (
        f"if(gt(abs(X-{pw}/2)\\,{pw}/2)+gt(abs(Y-{ph}/2)\\,{ph}/2)\\,0\\,"
        f"if(lte(abs(X-{pw}/2)\\,{pw}/2-{r})+lte(abs(Y-{ph}/2)\\,{ph}/2-{r})\\,255\\,"
        f"if(lte(hypot(abs(X-{pw}/2)-({pw}/2-{r})\\,abs(Y-{ph}/2)-({ph}/2-{r}))\\,{r})\\,255\\,0)))"
    )


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

    alpha = pip_alpha_expr(pw, ph, shape, radius)
    if shape == "circle" or radius > 0:
        parts.append(
            f"{src}format=rgba,"
            f"geq=r='r(X\\,Y)':g='g(X\\,Y)':b='b(X\\,Y)':a='{alpha}'{out_label}"
        )
        return parts, out_label

    if border_px > 0:
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
) -> None:
    """Final pass on the edit clock: A-roll → graphics → PIP → subtitles LAST → out."""
    pieces = pip_pieces or []
    has_graphics = bool(graphics)
    has_pip = bool(pieces)
    has_subs = bool(subtitle_layers)

    if not has_graphics and not has_pip and not has_subs:
        run(
            ["ffmpeg", "-y", "-i", str(base_path), "-c", "copy", str(out_path)],
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
    for idx, graphic in enumerate(graphics, start=1):
        t = float(graphic["start"])
        filter_parts.append(f"[{idx}:v]setpts=PTS-STARTPTS+{t}/TB[a{idx}]")

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
            f"{current}{pip_label}overlay={x}:{y}:enable='between(t,{t:.3f},{end:.3f})'"
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
        "copy",
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

"""Convert a grading_style JSON object to an ffmpeg -vf string.

Importable helper used by `grade.py` and `render.py`.
No CLI — call `json_to_grade_vf_string(data)`.
"""

from __future__ import annotations

# JSON color_balance keys → ffmpeg colorbalance option names
COLOR_BALANCE_KEYS = {
    "red_shadows": "rs",
    "green_shadows": "gs",
    "blue_shadows": "bs",
    "red_midtones": "rm",
    "green_midtones": "gm",
    "blue_midtones": "bm",
    "red_highlights": "rh",
    "green_highlights": "gh",
    "blue_highlights": "bh",
}


def json_to_grade_vf_string(data: dict | None) -> str:
    """Build an ffmpeg -vf filter string from a grading_style object."""
    if not data:
        return ""

    parts: list[str] = []

    # ==============================
    # eq
    # ==============================
    eq = data.get("eq") or {}
    if eq:
        eq_parts = [f"{key}={value}" for key, value in eq.items()]
        parts.append("eq=" + ":".join(eq_parts))

        # ==============================
        # color_balance → colorbalance
        # ==============================
    color_balance = data.get("color_balance") or {}
    if color_balance:
        cb_parts: list[str] = []
        for json_key, ffmpeg_key in COLOR_BALANCE_KEYS.items():
            if json_key in color_balance:
                cb_parts.append(f"{ffmpeg_key}={color_balance[json_key]}")
        if cb_parts:
            parts.append("colorbalance=" + ":".join(cb_parts))

            # ==============================
            # curves
            # ==============================
    curves = data.get("curves") or {}
    master = curves.get("master") or []
    if master:
        points = " ".join(f"{pt['input']}/{pt['output']}" for pt in master)
        parts.append(f"curves=master='{points}'")

    return ",".join(parts)

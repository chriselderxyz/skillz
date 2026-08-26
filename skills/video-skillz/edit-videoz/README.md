
# Clip Types

# Video Types

## Properties
Resolution: WxH

# Captions

## Burning Captions
By default captions will NOT be burned into the video.
You can turn on burned captions using

## Caption Styles
Built-in caption styles live at `assets/caption-styles/`. Copy the chosen style JSON into `edl.caption_style`; `render.py` reads it from the EDL (not the asset file) when burning.


# -------- Subtitle Style (bold-overlay, Proven at 1920×1080 and 1080×1920) --
#
# MarginV is NOT taste — it is a platform safe-zone rule.
# TikTok / IG Reels / Shorts UI (caption, username, music, right-rail actions)
# covers roughly the bottom ~25–30% of a 1080×1920 frame. Captions placed near
# the bottom edge get clipped or obscured by the UI. libass auto-scales the
# render canvas relative to PlayResY=288, so MarginV=90 lands the caption
# baseline roughly 30% up from the bottom on any aspect — clear of the UI on
# every major vertical-video platform. Do not drop this below ~75 without a
# specific reason.

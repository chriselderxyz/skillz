# Video Style Expected Properties

```json
{
    // ms to pad cut edges with
    // <50 is not advised due to transcription timing drift
    "cut_padding_ms": 100,

    // Silent sections longer than this are cut
    // cut_padding_ms applies
    "silence_cut_threshold_ms": 400,

    // ms of air at a line change or a speaker handoff
    "line_gap_ms": 500,

    // true cuts um, uh, ah, and similar fillers
    "cut_fillers": true,

    // true cuts breaths
    "cut_breaths": false,

    // true cuts keyboard clacking
    "cut_keyboard": false,

    // last | best | highest-energy
    "take_selection_mode": "last",

    // boolean, stored on the style
    "b_roll_enabled": false,

    // true allows a full graphic, an animation or image that is the picture
    "full_graphics_enabled": true,

    // full graphic duration stays inside this range
    "min_full_graphic_length_ms": 3000,
    "max_full_graphic_length_ms": 20000,

    // overlay graphic types allowed on this style. empty allows no overlay graphics
    // creator-credit | hook-text | context | text-story | cta
    "overlay_graphic_types": ["creator-credit", "context", "cta"],

    // overlay graphic duration stays inside this range
    "min_overlay_graphic_length_ms": 1500,
    "max_overlay_graphic_length_ms": 20000,

    // true allows a headless browser recording of a webpage
    "browser_enabled": true,

    // browser recording duration stays inside this range
    "min_browser_length_ms": 3000,
    "max_browser_length_ms": 20000,

    // longest a full-frame source may stay up before a picture change
    "max_continuous_shot_length_ms": 60000,

    // full | top-bottom-split | pip
    "allowed_layouts": ["full", "top-bottom-split", "pip"],

    // cold-open | greeting | question | text-card | mid-action
    // cold-open: first line is the claim or the action, no greeting
    // greeting: a hello or intro line can open
    // question: open on a question
    // text-card: open on a text graphic
    // mid-action: start inside an action already underway
    "opening_type": "greeting",

    // true allows jump zoom cuts on a full-frame head shot
    "zoom_cut": false,

    // how much tighter a zoom cut is. 1 is the crop. 1.15 is 15% tighter
    "zoom_amount": 1.15,

    // extra instructions for this style
    "other_instructions": ""
}
```

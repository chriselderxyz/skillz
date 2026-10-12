# Top Level Keys
- `title` and `description` are the video title and one paragraph on what it is.
- `sources` holds every **source**, keyed by **source** name.
    - `path` is the file, relative to the working directory.
    - `type`, `audio`, `duration`, `resolution`, and `fps` are the measured facts.
    - `base_crops` holds `full`, `pip`, `top`, and `bottom`.
    - An `animation` or `image` **source** has `description`. Omit `path` until it exists.
    - An `animation` or `image` **source** may have `text_elements`, keyed by role (ex. `headline`).
    - An `image` **source** has no `audio`, `duration`, or `fps`.
    - An **overlay graphic** **source** has `overlay_graphic_type`.
    - A `creator-credit` **source** has `credited_source`, naming the **source** it credits.
    - A **source** named by a `credited_source` has `credit`, with `creator`, `title`, and `speaker` when someone other than the creator speaks.
    - A browser recording **source** has `type` `browser`, `description`, and `actions`. Omit `path` until the recording exists.
        - `actions` run on the recording clock, which starts at `00:00:00.00` on the first **layer** that uses that **source**.
        - Each action has `type` and `at`.
            - `open` has `url` and shows that page.
            - `scroll` has `to`. A recording can scroll more than once.
            - `highlight` has `text`.
- `video_settings` is the video-settings config object.
- `video_style` is the video-style config object.
- `caption_style`, `srt_style`, `pip_style`, and `grading_style` are the chosen style objects.
    - Omit a style that is "none".
    - Omit `grading_style` while it is still "auto".
- `source_groups` holds every **source group**, keyed by **source group** number.
- `issues` is the flagged problem list shown to the user, one object per root cause with a `tag` and `text`.
- `scenes` holds every **scene**, keyed by **scene** ids.

# Identifiers
- **Scenes** use `s<n>`, **lines** use `l<n>`, **takes** use `t<n>`.
- Every identifier is monotonically increasing and is never reused.
  - **Line** and **take** identifiers increase across the whole file, not per **scene**.
  - New **scenes**, **lines**, and **takes** take the next unused number.
  - A deleted **scene**, **line**, or **take** leaves its number retired.

# Play Order
- **Scene** keys inside `scenes` are written in play order.
- **Line** keys inside `lines` are written in play order.
- `cuts` array order is play order.
- Reorder by rewriting keys in the new order, never by changing an identifier.

# Clocks
- `edit_start` and `edit_end` are on the **edit clock**.
- `audio_source_start` and `audio_source_end` are on the **audio source clock**.
- Footage **layer's** with a `source` in the same **source group** as the `audio_source` stay on the **audio source clock**, the same times as the kept take.
- Unsynced footage, such as B-roll or a source from another **source group**, is stored from `00:00:00.00` for the length of the layer. Compiling does not add a sync offset.
- Every time is a `HH:MM:SS.ss` string.

# Duration Rules
- The sum of a **line**'s `kept_take` cut durations equals that **line**'s **edit clock** duration.
- A **line**'s `edit_start` equals the previous **line**'s `edit_end`, and the first **line** in the video starts at `00:00:00.00`.
- The sum of a footage **layer**'s **cut** durations equals that **layer**'s **edit clock** duration.
- A **layer**'s `edit_start` and `edit_end` fall inside the **line** it is written on.

# Layers
- Every **line** has its own `layers` array, painted back to front.
- A **line** has at least one **layer**.
- Every **layer** has `frame`.
    - `full`, `pip`, `top`, `bottom`, or `{ "x", "y", "w", "h" }` as fractions of the output frame.
    - `full` fills the frame.
    - `pip` is the picture-in-picture inset. `pip_style` places and sizes it.
    - `top` and `bottom` each take half the frame.
- Every **layer** has `source`, which names an entry in `sources`.
- A footage **layer** has `edit_start`, `edit_end`, and `cuts`.
- A browser recording **layer** has no `cuts`. It uses `frame` `full`, `top`, `bottom`, or `{ "x", "y", "w", "h" }`.
- An `animation` or `image` **layer** has no `cuts`. It uses `frame` `full` or `{ "x", "y", "w", "h" }`.
- A **layer** may have `crop` to override `base_crops`.
- A full-frame `head` **layer** may have `zoom_cut` set to `true` when `video_style.zoom_cut` is true. That jumps the picture in by `video_style.zoom_amount`.
- **Layers** may overlap.

# Shape
```json
{
  "title": "Morning Ritual",
  "description": "A 25-second morning routine piece.",
  "sources": {
    "1-head": {
      "path": "src/1-head.mp4",
      "audio": true,
      "type": "head",
      "duration": "00:02:00.00",
      "resolution": "3840x2160",
      "fps": 29.97,
      "base_crops": {
        "pip": { "x": 1480, "y": 180, "w": 1920, "h": 1080 }
      }
    },
    "1-screen": {
      "path": "src/1-screen.mp4",
      "audio": true,
      "type": "screen",
      "duration": "00:02:00.00",
      "resolution": "3840x2160",
      "fps": 29.97
    },
    "coffee-first": {
      "type": "animation",
      "description": "Kinetic type with steam particles",
      "text_elements": { "headline": "COFFEE FIRST" },
      "path": "edit/graphics/1-graphic-coffee-first.mp4"
    },
    "podcast-clip": {
      "path": "src/podcast-clip.mp4",
      "audio": true,
      "type": "clip",
      "duration": "00:00:12.00",
      "resolution": "1920x1080",
      "fps": 30,
      "credit": { "creator": "Deep Work Podcast", "title": "Episode 12: Focus", "speaker": "Ana Ruiz" }
    },
    "podcast-clip-credit": {
      "type": "image",
      "overlay_graphic_type": "creator-credit",
      "credited_source": "podcast-clip",
      "description": "Lower third name plate, show line smaller under the speaker",
      "text_elements": { "speaker": "Ana Ruiz", "show": "Deep Work Podcast · Episode 12: Focus" }
    },
    "install-docs": {
      "type": "browser",
      "description": "Open the install docs, scroll to Install and Requirements, open the usage page, and highlight the npm command",
      "actions": [
        { "type": "open", "at": "00:00:00.00", "url": "https://example.com/docs/install" },
        { "type": "scroll", "at": "00:00:01.20", "to": "Install" },
        { "type": "scroll", "at": "00:00:03.00", "to": "Requirements" },
        { "type": "open", "at": "00:00:05.00", "url": "https://example.com/docs/usage" },
        { "type": "highlight", "at": "00:00:06.20", "text": "npm install example" }
      ],
      "path": "edit/browser/1-browser-install-docs.mp4"
    },
    "docs-url": {
      "type": "image",
      "overlay_graphic_type": "context",
      "description": "Rounded label pill",
      "text_elements": { "label": "example.com/docs" },
      "path": "edit/graphics/2-graphic-docs-url.png",
      "resolution": "576x86"
    }
  },
  "video_settings": {
    "orientation": "landscape",
    "resolution": "HD",
    "fps": 30
  },
  "video_style": {
    "cut_padding_ms": 100,
    "silence_cut_threshold_ms": 400,
    "line_gap_ms": 500,
    "cut_fillers": true,
    "cut_breaths": false,
    "cut_keyboard": false,
    "take_selection_mode": "last",
    "b_roll_enabled": false,
    "full_graphics_enabled": true,
    "min_full_graphic_length_ms": 3000,
    "max_full_graphic_length_ms": 20000,
    "overlay_graphic_types": ["creator-credit", "context", "cta"],
    "min_overlay_graphic_length_ms": 1500,
    "max_overlay_graphic_length_ms": 20000,
    "browser_enabled": true,
    "min_browser_length_ms": 3000,
    "max_browser_length_ms": 20000,
    "max_continuous_shot_length_ms": 60000,
    "allowed_layouts": ["full", "top-bottom-split", "pip"],
    "opening_type": "greeting",
    "zoom_cut": true,
    "zoom_amount": 1.15,
    "generate_chapters": true,
    "other_instructions": ""
  },
  "source_groups": {
    "1": {
      "audio_source": "1-screen",
      "sync": {
        "1-head": 0.42
      }
    }
  },
  "issues": [
    {
      "tag": "Mismatch",
      "text": "Frame rate mismatch between 1-head (29.97fps) and 1-screen (30fps)."
    }
  ],
  "scenes": {
    "s1": {
      "name": "PROBLEM: AI is bad at video editing.",
      "lines": {
        "l1": {
          "edit_start": "00:00:00.00",
          "edit_end": "00:00:04.18",
          "kept_take": {
            "id": "t3",
            "audio_source": "1-head",
            "transcript": "Every morning starts the same way",
            "cuts": [
              {
                "audio_source_start": "00:00:48.12",
                "audio_source_end": "00:00:49.72",
                "transcript": "Every morning"
              },
              {
                "audio_source_start": "00:00:50.52",
                "audio_source_end": "00:00:53.10",
                "transcript": "starts the same way"
              }
            ]
          },
          "rejected_takes": [
            {
              "id": "t1",
              "audio_source": "1-head",
              "transcript": "Ev\u2014 every morning starts the same way.",
              "reason": "False start on the first word",
              "cuts": [
                { "audio_source_start": "00:00:41.08", "audio_source_end": "00:00:44.61" }
              ]
            }
          ],
          "layers": [
            {
              "frame": "full",
              "source": "1-head",
              "edit_start": "00:00:00.00",
              "edit_end": "00:00:04.18",
              "cuts": [
                { "audio_source_start": "00:00:48.12", "audio_source_end": "00:00:49.72" },
                { "audio_source_start": "00:00:50.52", "audio_source_end": "00:00:53.10" }
              ]
            }
          ]
        },
        "l2": {
          "edit_start": "00:00:04.18",
          "edit_end": "00:00:09.41",
          "kept_take": {
            "id": "t5",
            "audio_source": "1-head",
            "transcript": "Coffee first. Everything else after.",
            "cuts": [
              { "audio_source_start": "00:01:07.22", "audio_source_end": "00:01:12.45" }
            ]
          },
          "rejected_takes": [],
          "layers": [
            {
              "frame": "full",
              "source": "coffee-first",
              "edit_start": "00:00:04.18",
              "edit_end": "00:00:09.41"
            },
            {
              "frame": "pip",
              "source": "1-head",
              "edit_start": "00:00:04.18",
              "edit_end": "00:00:09.41",
              "cuts": [
                { "audio_source_start": "00:01:07.22", "audio_source_end": "00:01:12.45" }
              ]
            }
          ]
        },
        "l3": {
          "edit_start": "00:00:09.41",
          "edit_end": "00:00:14.41",
          "kept_take": {
            "id": "t6",
            "audio_source": "1-head",
            "transcript": "Install it with npm.",
            "cuts": [
              { "audio_source_start": "00:01:20.00", "audio_source_end": "00:01:25.00" }
            ]
          },
          "rejected_takes": [],
          "layers": [
            {
              "frame": "full",
              "source": "install-docs",
              "edit_start": "00:00:09.41",
              "edit_end": "00:00:14.41"
            },
            {
              "frame": "pip",
              "source": "1-head",
              "edit_start": "00:00:09.41",
              "edit_end": "00:00:14.41",
              "cuts": [
                { "audio_source_start": "00:01:20.00", "audio_source_end": "00:01:25.00" }
              ]
            },
            {
              "frame": { "x": 0.04, "y": 0.05, "w": 0.3, "h": 0.08 },
              "source": "docs-url",
              "edit_start": "00:00:09.41",
              "edit_end": "00:00:12.41"
            }
          ]
        }
      }
    }
  }
}
```

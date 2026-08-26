# Create New SRT Style
- Ask the user for a style name and description
- Map the description to style fields
  - chars_per_line (int)
  - num_lines (int)
- Ask clarifying questions if required
- Save the result to `assets/srt-styles/<name>.json`
- Use the new style as the `srt_style` input variable
- Copy the JSON onto `edit/edl.json` as `srt_style`

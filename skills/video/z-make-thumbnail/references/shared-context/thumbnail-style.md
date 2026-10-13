# Background
- `style`: The background pattern, filled with `background_colors`.

## solid
- One color fills the frame.
- `background_colors`: The fill color.

## gradient
- The colors blend across the frame.
- `background_colors`: 2 or more colors, in blend order.
- `gradient_type`: `linear`, or `radial` to blend outward from the center.
- `gradient_angle`: The direction of a `linear` gradient in degrees, where 0 runs left to right and 90 runs top to bottom.
- `gradient_stops`: The position of each background color along the gradient, from 0 to 100, in `background_colors` order.
- The first color is solid before its stop, the last color is solid after its stop, and the colors blend between stops.
- A color repeated at two stops stays solid between them.

## left-right
- The left and right halves are each a solid color.
- `background_colors`: The left color, then the right color.

## quarters
- 4 equal vertical slices are each a solid color.
- `background_colors`: 4 colors, from left to right.

## grid
- A solid color with blueprint gridlines drawn over it.
- `background_colors`: The fill color.
- `grid_line_color`: The color of the major and minor lines.
- `grid_cell_size`: The width of each square cell between minor lines, as a percent of the frame width.
- `grid_major_every`: The number of cells between major lines.
- `grid_minor_line_width`: The minor line width, as a percent of the cell size.
- `grid_major_line_width`: The major line width, as a percent of the cell size.

# Colors
- `foreground_colors`: Colors for text and other elements that sit directly on the background, with the main color first.
- `outline_color`: The text outline color, used when the **font style** sets `outline_width`.
- `text_box_background`: Optional fill for a box around one word, to highlight it.
- `text_box_foreground`: Optional color for the word in that box.
- An element can take another color when that color suits it better, such as a product name in its brand colors.

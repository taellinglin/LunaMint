# EisenScript Reference (Complete)

This document lists every EisenScript element supported by the parser and all parameters accepted for each element, plus SD background filters and their parameters.

## Syntax

- Lines starting with `#` are comments.
- Commands are case-insensitive.
- Key/value arguments are written as `key=value`.
- Quote values containing spaces or special characters.
- Units:
  - `*_mm` values are millimeters.
  - Canvas `size` is in pixels.

## Elements (All Supported)

### size
Sets the canvas size in pixels.

Parameters:
- `width` (positional)
- `height` (positional)

Example:
```
size 1600 600
```

### background
Sets the canvas background color.

Parameters:
- `color` (positional)

Example:
```
background #1f1f1f
```

### rect
Draws a rectangle.

Parameters:
- `x` `y` `w` `h` (positional)
- `fill` (positional, optional; default `#000`)

Example:
```
rect 20 20 200 100 #333333
```

### circle
Draws a circle.

Parameters:
- `x` `y` `r` (positional)
- `fill` (positional, optional; default `#000`)

Example:
```
circle 200 200 40 #333333
```

### dot
Draws a 1px-radius dot (for pixel-style drawing).

Parameters:
- `x` `y` (positional)
- `fill` (positional, optional; default `#000`)

Example:
```
dot 120 80 #FF00FF80
```

### pix
Draws a 1x1 pixel square (for pixel-style drawing).

Parameters:
- `x` `y` (positional)
- `fill` (positional, optional; default `#000`)

Example:
```
pix 120 80 #00FF00AA
```

### polygon
Draws a polygon.

Parameters:
- `points` (key/value; format: "x,y x,y x,y")
- `fill` (key/value, optional; default `#000`)
- `stroke` (key/value, optional)
- `stroke_width` (key/value, optional)

Example:
```
polygon points="10,10 100,10 80,80" fill="#3A7AFE" stroke="#111" stroke_width=2
```

### line
Draws a line.

Parameters:
- `x1` `y1` `x2` `y2` (positional)
- `stroke` (positional, optional; default `#000`)
- `width` (positional, optional; default `1.0`)

Example:
```
line 10 10 500 10 #cccccc 2
```

### text
Draws text.

Parameters:
- `x` `y` `size` `fill` (positional)
- `text` (positional remainder)

Example:
```
text 60 80 32 #111111 "LunaMint Banknote"
```

### group / endgroup
Groups elements. If a boolean op is provided, shapes inside the group are combined into a single shape.

Parameters:
- `group` takes a boolean type as positional or `op=...`
- Supported booleans: `union`, `difference`, `divide`, `intersection`, `punchout`, `subtract`

Example:
```
group union
  circle 200 200 60 #FF000080
  circle 240 200 60 #00FF0080
endgroup
```

### text_dial
Warped polar text dial (concentric rings).

Parameters:
- `cx_mm`, `cy_mm`, `radius_mm`
- `text`
- `rings`
- `font`
- `font_dir`
- `font_size_mm`
- `spacing_mm`
- `ring_gap_mm`
- `rotation_seed`
- `snap_grid_px`
- `clip_radius_mm`
- `case` (`upper` | `lower` | `preserve`)
- `inner_radius_mm`

Example:
```
text_dial cx_mm=80 cy_mm=45 radius_mm=30 text="LUNAMINT" rings=6 font="Daemon Full Working" font_size_mm=1.2
```

### text_grid
Warped text grid cipher.

Parameters:
- `x_mm`, `y_mm`, `width_mm`, `height_mm`
- `text`
- `font`
- `font_dir`
- `font_size_mm`
- `spacing_mm`
- `snap_grid_px`

Example:
```
text_grid x_mm=10 y_mm=10 width_mm=60 height_mm=60 text="LUNAMINT" font="Daemon Full Working" font_size_mm=1.2
```

### pixel_art
Pixel-art stamp from an image (vectorized pixel blocks).

Parameters:
- `x_mm`, `y_mm`
- `image` (path to PNG)
- `pixel_size_mm`
- `alpha_threshold`
- `compress` (`true`|`false`)

Example:
```
pixel_art x_mm=10 y_mm=10 image="./portraits/logo.png" pixel_size_mm=0.6 compress=true
```

### letter_border
Letter-based border mask.

Parameters:
- `x_mm`, `y_mm`, `width_mm`, `height_mm`
- `border_thickness_mm`
- `text`
- `font`
- `font_dir`
- `font_size_mm`
- `spacing_mm`
- `inset_mm`
- `outset_mm`
- `offset_x_mm`
- `offset_y_mm`
- `layout` (`band` | `packed`)
- `palette` (comma-separated colors)
- `cycle_mode` (`sequential` | `random` | `encoding`)
- `cycle_seed`
- `encoding_algo` (`sha256` | `sha3_256` | `sm3`)
- `packed_spacing_x_mm`
- `packed_spacing_y_mm`
- `packed_glyph_scale`
- `fill_color`
- `opacity`
- `case`
- `base_fill`
- `pattern` (`stripes` | `solid`)
- `pattern_color`
- `pattern_opacity`

### hash_mandala
Hash-driven mandala based on text or file input.

Parameters:
- `cx_mm`, `cy_mm`, `radius_mm`
- `data` or `data_text`
- `data_path`
- `data_type`
- `font`
- `font_dir`
- `font_size_mm`
- `charset`
- `rings`
- `sectors`
- `opacity`
- `stroke_width_mm`
- `colorize`
- `use_roygbiv`
- `grid_density`
- `inset_scale`
- `outset_scale`
- `snap_grid_px`
- `ring_rows`
- `sector_density`
- `fill_empty`
- `background_color`
- `background_opacity`
- `border_color`
- `border_width_mm`
- `radial_lines`
- `tick_major`
- `tick_minor`
- `core_rings`
- `core_radials`
- `core_letter_every`
- `cardinal_markers`
- `stroke_only`
- `stroke_color`
- `stroke_color_secondary`
- `flat_glyphs`
- `glyph_fill`
- `glyph_stroke`
- `glyph_stroke_width_scale`
- `min_cols_per_sector`
- `taper_outer_strength`
- `taper_radial_strength`
- `ring_label_every`
- `ring_label_alternate`
- `ring_label_text`
- `ring_label_size_scale`
- `sector_padding_deg`
- `ring_padding_mm`
- `sector_outline`
- `sector_outline_color`
- `sector_outline_width_mm`
- `ring_pattern_mode`
- `sm2_row_variance`
- `label_every`
- `label_radius_ratio`
- `label_font_size_mm`
- `label_stroke_width_mm`
- `sector_boxes`
- `sector_box_size_mm`
- `center_digit`
- `center_digit_size_mm`
- `center_digit_fill_background`

### hash_mandala_rect
Rectangular variant of `hash_mandala`.

Parameters:
- `x_mm`, `y_mm`, `width_mm`, `height_mm`
- All parameters listed in `hash_mandala`

### midi_dial
MIDI note/CC visualization dial.

Parameters:
- `cx_mm`, `cy_mm`, `radius_mm`
- `file` (path to MIDI)
- `font`
- `font_dir`
- `font_size_mm`
- `note_charset`
- `cc_charset`
- `note_opacity`
- `cc_opacity`
- `background_color`
- `background_opacity`
- `outer_stroke`
- `outer_stroke_width_mm`
- `note_stroke`
- `note_stroke_width_mm`
- `cc_mark_length_mm`
- `cc_mark_width_mm`
- `cc_ring_offset_mm`
- `inner_radius_ratio`
- `outer_radius_ratio`
- `rotation_deg`

### sd_background
Generates an SD background and optionally applies a filter. Use this for EisenScript-only backgrounds (not the full banknote generator).

Common parameters:
- `seed_text`
- `bg_dir`
- `background_prompt`
- `filter`
- `margin`
- `background_segments` (used by `vectorize`)

Filter-specific parameters (used when `filter=glyph_grid`):
- `glyph_font`
- `glyph_font_dir`
- `glyph_font_size_mm`
- `glyph_charset`
- `glyph_invert`
- `glyph_snap_grid_px`
- `glyph_opacity`
- `glyph_fill_dark`
- `glyph_fill_light`
- `glyph_stroke_dark`
- `glyph_stroke_light`
- `glyph_stroke_width_mm`
- `glyph_inset_scale`
- `glyph_outset_scale`
- `glyph_threshold`
- `glyph_colorize`
- `glyph_cell_padding_mm`
- `glyph_dpi`

### sd_background_circle
SD background clipped to a circle (outside is transparent).

Parameters:
- Same as `sd_background`, plus:
- `cx`, `cy`, `r` (circle center + radius in px)

Notes:
- This is equivalent to `sd_background` with `background_clip=circle` and `background_clip_cx/cy/r`.

### qr_code
Black/white QR code renderer.

Parameters:
- `x`, `y` (pixels)
- `size` (pixels; square)
- `data` (or `text`)
- `border` (quiet zone in modules)
- `error` (`L` | `M` | `Q` | `H`)
- `foreground` (hex color)
- `background` (hex color or `none`)
- `invert` (`true` | `false`)

### back_vectorized_background
Backside SD vectorized background (same as generate_back).

Parameters:
- `seed_text`
- `bg_dir`
- `margin`
- `n_segments`
- `background_prompt`
- `denomination`

### back_corner_denoms
Denomination numbers in four corners.

Parameters:
- `denomination`

### back_corner_decorations
Functional corner decorations.

Parameters:
- `denomination`
- `timestamp_ms`
- `serial_id`
- `size`
- `padding`
- `stroke_width`

### back_holographic_seals
Blue circles + orange/red mandala seals (generate_back holographic seals).

Parameters:
- `serial_id`
- `denomination`
- `radius`

### back_center_text
Center title + phrase (generate_back style).

Parameters:
- `title`
- `phrase`
- `denomination`
- `denom_color` (optional override)

### back_circular_qr
Circular QR bands rendered as radial lines.

Parameters:
- `data` (or `text`)
- `cx`, `cy`
- `inner_radius`
- `outer_radius`
- `segments`
- `opacity`
- `colors` (comma-separated hex list)

### back_qr_border
QR-like border frame.

Parameters:
- `seed` (or `seed_text`)
- `serial_id`
- `timestamp_ms`

### back_verification_text
Verification text footer.

Parameters:
- `serial_id`
- `timestamp_ms`

### back_security_background
Triangle-based security background.

Parameters:
- `denomination`
- `serial_id`
- `margin`
- `base_triangle_size`
- `hierarchy_levels`

### chinese_microprint
Chinese microprint seal around a circle.

Parameters:
- `cx`, `cy`
- `radius`
- `text`
- `repetitions`
- `font_family`
- `font_size`

### rainbow_microseal
Rainbow microprint seal around a circle.

Parameters:
- `cx`, `cy`
- `radius`
- `symbol`
- `repetitions`
- `font_family`
- `font_size`

### back_aztec
Aztec-style QR elements from URL.

Parameters:
- `url`
- `cx`, `cy`
- `scale`
- `border`
- `rotation`
- `border_opacity`
- `denomination`

### front_banknote
Full banknote renderer with rich background and security features.

Parameters:
- `seed_text`
- `input_image_path`
- `width_mm`
- `height_mm`
- `title`
- `subtitle`
- `serial_id`
- `timestamp`
- `denomination`
- `specimen`
- `bg_dir`
- `background_prompt`
- `border_inset_mm`
- `border_thickness_mm`
- `enable_qr_border`
- `enable_background`
- `background_filter`
- `background_margin`
- `background_segments`
- `mosaic_font`
- `mosaic_font_dir`
- `mosaic_font_size_mm`
- `mosaic_charset`
- `mosaic_invert`
- `mosaic_snap_grid_px`
- `mosaic_opacity`
- `glyph_font`
- `glyph_font_dir`
- `glyph_font_size_mm`
- `glyph_charset`
- `glyph_invert`
- `glyph_snap_grid_px`
- `glyph_opacity`
- `glyph_fill_dark`
- `glyph_fill_light`
- `glyph_stroke_dark`
- `glyph_stroke_light`
- `glyph_stroke_width_mm`
- `glyph_inset_scale`
- `glyph_outset_scale`
- `glyph_threshold`
- `glyph_colorize`
- `glyph_cell_padding_mm`
- `enable_microgrid`
- `enable_decorative_border`
- `enable_center_seal`
- `enable_center_text`
- `enable_corner_decorations`
- `enable_corner_denoms`
- `enable_microprint`
- `microprint_repetitions`
- `microprint_text`
- `center_radius_scale`
- `small_radius_scale`
- `text_seal_scale`
- `secondary_ring_scale`
- `center_seal_scale`
- `title_font`
- `subtitle_font`
- `corner_font`
- `seal_chinese_font`
- `seal_english_font`
- `showcase_widgets`
- `ascii_stamp_prompt`
- `showcase_labels`
- `label_font`
- `label_size_mm`
- `qr_url`
- `require_signed_qr`
- `sm2_private_key`
- `sm2_public_key`
- `verify_base_url`
- `issuer_id`
- `validity_days`
- `pow_difficulty`
- `sm4_key`
- `sm4_enable`
- `qr_stamp_width`
- `qr_stamp_height`
- `qr_rows`
- `qr_side`
- `qr_stamp`
- `aztec`
- `aztec_scale`
- `aztec_border`
- `aztec_rotation_base`
- `aztec_offset_x`
- `aztec_offset_y`
- `aztec_border_opacity`

### back_banknote
Backside banknote renderer that mirrors the full back generator.

Parameters:
- `seed_text`
- `denomination`
- `title`
- `phrase`
- `width_mm`
- `height_mm`
- `serial_id`
- `timestamp_ms`

## Filters (All Supported)

These are valid for `sd_background filter=...` and `front_banknote background_filter=...`.

You can layer filters by joining them with `+`, e.g. `filter=vectorize+triangle_mosaic`.

To avoid old layers showing through, use `background_clear=true` (optional `background_clear_color` and `background_clear_opacity`).
You can also set `background_opacity` to fade the SD background layer.

SDAPI overrides:
- `sd_model` / `sd_model_name` / `model`
- `sd_cfg_scale` / `cfg_scale`

### for loops
EisenScript supports basic `for` blocks with simple math and `$var` substitution.

Example:
```
for [i=0; i<16; i++]
  angle = i * 22.5
  x = 600 + cos(angle) * 180
  y = 600 + sin(angle) * 180
  rainbow_microseal cx=$x cy=$y radius=60 symbol="$" repetitions=192
```

You can also iterate a list with `for name in ...`:
```
for quadrant in 1 2 3 4
  label = chr(119 + quadrant)
```

Supported functions: `sin`, `cos`, `tan` (degrees), `sqrt`, `abs`, `min`, `max`, `pow`, `chr`, `if`.

### cutout_circle
Clips the immediately previous layer to a circle (use after `sd_background` or any drawable op).

Parameters:
- `cx`, `cy` (center in px)
- `r` (radius in px)
- `target` ("last" or "background")

Example:
```
sd_background ...
cutout_circle cx=256 cy=256 r=240
```

### mask_circle
Applies a mask to the previous layer. By default, white shows and black hides. Use `invert=true` to flip (white hides).

Parameters:
- `cx`, `cy` (center in px)
- `r` (radius in px)
- `target` ("last" or "background")
- `invert` (true/false)

### vectorize
Vectorizes an SD background into SVG segments.

Parameters:
- `background_prompt`
- `background_margin`
- `background_segments`
- `bg_dir`
- `seed_text`

### vectorize_sm2_crosshatch
Vectorizes an SD background and overlays SM2-encoded crosshatching.

Parameters:
- `background_prompt`
- `background_margin`
- `background_segments`
- `bg_dir`
- `seed_text`
- `sm2_private_key` (optional override; falls back to env)
- `sm2_public_key` (optional override)
- `crosshatch_spacing` (default 6.0)
- `crosshatch_stroke_width` (default 0.5)
- `crosshatch_opacity` (default 0.45)
- `crosshatch_alpha` (overrides opacity if set)
- `crosshatch_h` (0-1 hue; omit to derive from signature)
- `crosshatch_s` (default 0.9)
- `crosshatch_l` (default 0.65)
- `crosshatch_v` (default 1.0)
- `crosshatch_hue_range` (default 0.28)
- `transparent_threshold` (default 248; skips near-white segments)
- `outline_stroke` (optional; stroke color for segment outlines)
- `outline_stroke_width` (default 0.8)
- `outline_stroke_opacity` (default 1.0)
- `outline_stroke_linecap` (default "round")
- `outline_stroke_linejoin` (default "round")
- `crosshatch_use_mask` (default false; use mask instead of clipPath for compatibility)
- `crosshatch_flatten` (default false; physically clips hatch lines to segments for laser/plotter tools)

### glyph_grid
Glyph grid filter over an SD background.

Parameters:
- `background_prompt`
- `background_margin`
- `bg_dir`
- `seed_text`
- `glyph_*` options listed in `sd_background`

### letter_mosaic
Letter mosaic filter over an SD background.

Parameters:
- `background_prompt`
- `background_margin`
- `bg_dir`
- `seed_text`

Config defaults (not exposed as EisenScript args):
- `font_name`
- `font_dir`
- `font_size_mm`
- `charset`
- `invert`
- `snap_grid_px`
- `opacity`
- `dpi`

### triangle_mosaic
Triangle mosaic filter over an SD background.

Parameters:
- `background_prompt`
- `background_margin`
- `bg_dir`
- `seed_text`

Config defaults (not exposed as EisenScript args):
- `base_cell`
- `min_cell`
- `max_depth`
- `variance_threshold`
- `opacity`

### none / image / raw
Embeds the raw generated image without applying a filter.

Parameters:
- `background_prompt`
- `background_margin`
- `bg_dir`
- `seed_text`

## SD API Configuration

- Environment: `SD_API_BASE_URL` or `SD_API_URL`
- Gradio sidebar field (Eisen tab)

## Notes

- MIDI file paths should be relative to project root, for example: `file="MIDI Collection/YourFile.mid"`.
- Quote any value containing spaces or special characters.
- MIDI file paths should be relative to the project root:
  - `file="MIDI Collection/YourFile.mid"`

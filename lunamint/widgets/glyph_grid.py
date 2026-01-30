"""Glyph grid widget for image-based patterns."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from PIL import Image
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont
import svgwrite

from .measure import mm_to_px, snap_px


@dataclass
class GlyphGridOptions:
    font_name: str = "Daemon Full Working"
    font_dir: str = "./fonts"
    font_size_mm: float = 1.2
    charset: str = "LUNAMINT"
    invert: bool = False
    snap_grid_px: float = 16.0
    opacity: float = 0.9
    fill_dark: str = "#111111"
    fill_light: str = "#f7f2eb"
    stroke_dark: str = "#0b0b0b"
    stroke_light: str = "#999999"
    stroke_width_mm: float = 0.12
    inset_scale: float = 0.8
    outset_scale: float = 1.1
    threshold: int = 140
    dpi: float = 300.0
    colorize: bool = False
    cell_padding_mm: float = 0.0


def _find_font_path(font_name: str, font_dir: str) -> Optional[str]:
    if font_name and Path(font_name).is_file():
        return str(font_name)
    if not Path(font_dir).is_dir():
        return None
    target = font_name.lower().replace(" ", "")
    for file in Path(font_dir).glob("*.ttf"):
        if target and target in file.stem.lower().replace(" ", ""):
            return str(file)
    for file in Path(font_dir).glob("*.otf"):
        if target and target in file.stem.lower().replace(" ", ""):
            return str(file)
    return None


def _pick_char(value: int, charset: str, invert: bool) -> str:
    if not charset:
        return ""
    idx = int((value / 255) * (len(charset) - 1))
    if invert:
        idx = (len(charset) - 1) - idx
    return charset[idx]


def add_glyph_grid_from_image_mm(
    dwg: svgwrite.Drawing,
    image_path: str,
    x_mm: float,
    y_mm: float,
    width_mm: float,
    height_mm: float,
    options: Optional[GlyphGridOptions] = None,
    dpi: float = 300.0,
) -> svgwrite.container.Group:
    opts = options or GlyphGridOptions()
    x = mm_to_px(x_mm, dpi)
    y = mm_to_px(y_mm, dpi)
    width = mm_to_px(width_mm, dpi)
    height = mm_to_px(height_mm, dpi)
    font_size_px = mm_to_px(opts.font_size_mm, dpi)
    stroke_width_px = max(0.5, mm_to_px(opts.stroke_width_mm, dpi))
    padding_px = mm_to_px(opts.cell_padding_mm, dpi)

    font_path = _find_font_path(opts.font_name, opts.font_dir)
    if not font_path:
        raise FileNotFoundError(f"Font '{opts.font_name}' not found in {opts.font_dir}")

    font = TTFont(font_path)
    units_per_em = font["head"].unitsPerEm
    base_scale = font_size_px / units_per_em
    glyph_set = font.getGlyphSet()
    cmap = font.getBestCmap()

    sample_glyph = glyph_set[cmap.get(ord("M"), list(glyph_set.keys())[0])]
    bounds_pen = BoundsPen(glyph_set)
    sample_glyph.draw(bounds_pen)
    bounds = bounds_pen.bounds
    if bounds:
        min_x, min_y, max_x, max_y = bounds
        cell_w = max(1.0, (max_x - min_x) * base_scale + padding_px)
        cell_h = max(1.0, (max_y - min_y) * base_scale + padding_px)
    else:
        cell_w = max(1.0, font_size_px + padding_px)
        cell_h = max(1.0, font_size_px + padding_px)

    cols = max(1, int(width / cell_w))
    rows = max(1, int(height / cell_h))

    img_rgb = Image.open(image_path).convert("RGB").resize((cols, rows))
    img_gray = img_rgb.convert("L")
    pixels = img_gray.load()
    pixels_rgb = img_rgb.load()

    def _tint(color: tuple[int, int, int], factor: float) -> str:
        r, g, b = color
        r = max(0, min(255, int(r * factor)))
        g = max(0, min(255, int(g * factor)))
        b = max(0, min(255, int(b * factor)))
        return f"#{r:02x}{g:02x}{b:02x}"

    group = dwg.g(opacity=opts.opacity)
    for r in range(rows):
        for c in range(cols):
            v = pixels[c, r]
            ch = _pick_char(v, opts.charset, opts.invert)
            if not ch:
                continue
            glyph_name = cmap.get(ord(ch))
            if not glyph_name:
                continue
            glyph = glyph_set[glyph_name]
            pen = SVGPathPen(glyph_set)
            glyph.draw(pen)
            path = pen.getCommands()
            if not path:
                continue

            bounds_pen = BoundsPen(glyph_set)
            glyph.draw(bounds_pen)
            bounds = bounds_pen.bounds
            if not bounds:
                continue
            min_x, min_y, max_x, max_y = bounds
            glyph_cx = (min_x + max_x) / 2
            glyph_cy = (min_y + max_y) / 2

            scale = base_scale * (opts.outset_scale if v < opts.threshold else opts.inset_scale)
            cx = x + c * cell_w + cell_w / 2
            cy = y + r * cell_h + cell_h / 2
            if opts.snap_grid_px > 0:
                cx = snap_px(cx, opts.snap_grid_px)
                cy = snap_px(cy, opts.snap_grid_px)

            if opts.colorize:
                rgb = pixels_rgb[c, r]
                fill = _tint(rgb, 1.0 if v < opts.threshold else 1.2)
                stroke = _tint(rgb, 0.6 if v < opts.threshold else 0.8)
            else:
                fill = opts.fill_dark if v < opts.threshold else opts.fill_light
                stroke = opts.stroke_dark if v < opts.threshold else opts.stroke_light

            transform = (
                f"translate({cx:.2f},{cy:.2f}) "
                f"scale({scale:.4f},{-scale:.4f}) "
                f"translate({-glyph_cx:.2f},{-glyph_cy:.2f})"
            )
            group.add(
                dwg.path(
                    d=path,
                    fill=fill,
                    stroke=stroke,
                    stroke_width=stroke_width_px,
                    transform=transform,
                )
            )

    dwg.add(group)
    return group

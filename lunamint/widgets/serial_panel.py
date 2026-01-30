"""Serial number panel widget."""
from __future__ import annotations

import svgwrite

from .measure import mm_to_px


def add_serial_panel_mm(
    dwg: svgwrite.Drawing,
    x_mm: float,
    y_mm: float,
    width_mm: float,
    height_mm: float,
    serial_text: str,
    font_size_mm: float = 2.6,
    font_family: str = "Daemon Full Working",
    text_color: str = "#111111",
    fill: str = "#f7f7f7",
    stroke: str = "#111111",
    stroke_width_mm: float = 0.15,
    rounding_mm: float = 0.6,
    dpi: float = 300.0,
) -> svgwrite.container.Group:
    x = mm_to_px(x_mm, dpi)
    y = mm_to_px(y_mm, dpi)
    width = mm_to_px(width_mm, dpi)
    height = mm_to_px(height_mm, dpi)
    stroke_width = mm_to_px(stroke_width_mm, dpi)
    rounding = mm_to_px(rounding_mm, dpi)
    font_size = mm_to_px(font_size_mm, dpi)

    group = dwg.g()
    group.add(
        dwg.rect(
            insert=(x, y),
            size=(width, height),
            rx=rounding,
            ry=rounding,
            fill=fill,
            stroke=stroke,
            stroke_width=stroke_width,
        )
    )
    group.add(
        dwg.text(
            serial_text,
            insert=(x + width / 2, y + height / 2 + font_size / 3),
            text_anchor="middle",
            font_size=font_size,
            font_family=font_family,
            fill=text_color,
        )
    )
    dwg.add(group)
    return group

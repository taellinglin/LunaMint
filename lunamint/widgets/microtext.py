"""Microtext elements."""
from __future__ import annotations

import svgwrite

from .measure import mm_to_px


def add_microtext_line(
    dwg: svgwrite.Drawing,
    text: str,
    x: float,
    y: float,
    width: float,
    font_size: float = 6,
    letter_spacing: float = 1.2,
    font_family: str = "Daemon Full Working",
    fill: str = "#111111",
    opacity: float = 0.35,
    repeat: bool = True,
) -> svgwrite.container.Group:
    """Repeat microtext across a line length."""
    group = dwg.g(opacity=opacity)
    if not text:
        return group
    cursor = x
    chunk_width = max(1.0, len(text) * font_size * 0.5 + letter_spacing * len(text))
    while cursor < x + width:
        group.add(
            dwg.text(
                text,
                insert=(cursor, y),
                font_size=font_size,
                font_family=font_family,
                fill=fill,
                letter_spacing=letter_spacing,
            )
        )
        if not repeat:
            break
        cursor += chunk_width
    dwg.add(group)
    return group


def add_microtext_line_mm(
    dwg: svgwrite.Drawing,
    text: str,
    x_mm: float,
    y_mm: float,
    width_mm: float,
    font_size_mm: float = 0.7,
    letter_spacing_mm: float = 0.2,
    font_family: str = "Daemon Full Working",
    fill: str = "#111111",
    opacity: float = 0.35,
    repeat: bool = True,
    dpi: float = 300.0,
) -> svgwrite.container.Group:
    return add_microtext_line(
        dwg,
        text=text,
        x=mm_to_px(x_mm, dpi),
        y=mm_to_px(y_mm, dpi),
        width=mm_to_px(width_mm, dpi),
        font_size=mm_to_px(font_size_mm, dpi),
        letter_spacing=mm_to_px(letter_spacing_mm, dpi),
        font_family=font_family,
        fill=fill,
        opacity=opacity,
        repeat=repeat,
    )

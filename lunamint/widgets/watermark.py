"""Watermark-like medallion elements."""
from __future__ import annotations

import math

import svgwrite

from .measure import mm_to_px


def add_watermark_medallion(
    dwg: svgwrite.Drawing,
    cx: float,
    cy: float,
    radius: float,
    text: str = "LUNAMINT",
    font_size: float = 18,
    stroke: str = "#666666",
    stroke_width: float = 0.6,
    fill: str = "none",
    opacity: float = 0.2,
) -> svgwrite.container.Group:
    """Draw a faint medallion with radial lines and center text."""
    group = dwg.g(opacity=opacity)
    group.add(dwg.circle(center=(cx, cy), r=radius, fill=fill, stroke=stroke, stroke_width=stroke_width))
    for i in range(36):
        angle = math.tau * i / 36
        x1 = cx + math.cos(angle) * (radius * 0.2)
        y1 = cy + math.sin(angle) * (radius * 0.2)
        x2 = cx + math.cos(angle) * radius
        y2 = cy + math.sin(angle) * radius
        group.add(dwg.line(start=(x1, y1), end=(x2, y2), stroke=stroke, stroke_width=stroke_width))
    group.add(
        dwg.text(
            text,
            insert=(cx, cy + font_size / 3),
            text_anchor="middle",
            font_size=font_size,
            font_family="FengGuangMingRui",
            fill=stroke,
        )
    )
    dwg.add(group)
    return group


def add_watermark_medallion_mm(
    dwg: svgwrite.Drawing,
    cx_mm: float,
    cy_mm: float,
    radius_mm: float,
    text: str = "LUNAMINT",
    font_size_mm: float = 2.2,
    stroke: str = "#666666",
    stroke_width_mm: float = 0.06,
    fill: str = "none",
    opacity: float = 0.2,
    dpi: float = 300.0,
) -> svgwrite.container.Group:
    return add_watermark_medallion(
        dwg,
        cx=mm_to_px(cx_mm, dpi),
        cy=mm_to_px(cy_mm, dpi),
        radius=mm_to_px(radius_mm, dpi),
        text=text,
        font_size=mm_to_px(font_size_mm, dpi),
        stroke=stroke,
        stroke_width=mm_to_px(stroke_width_mm, dpi),
        fill=fill,
        opacity=opacity,
    )

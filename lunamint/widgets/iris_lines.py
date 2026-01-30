"""Radial iris line widget."""
from __future__ import annotations

import math

import svgwrite

from .measure import mm_to_px


def add_iris_lines_mm(
    dwg: svgwrite.Drawing,
    cx_mm: float,
    cy_mm: float,
    radius_mm: float,
    lines: int = 90,
    stroke: str = "#111111",
    stroke_width_mm: float = 0.06,
    opacity: float = 0.2,
    dpi: float = 300.0,
) -> svgwrite.container.Group:
    cx = mm_to_px(cx_mm, dpi)
    cy = mm_to_px(cy_mm, dpi)
    radius = mm_to_px(radius_mm, dpi)
    stroke_width = mm_to_px(stroke_width_mm, dpi)

    group = dwg.g(opacity=opacity)
    for i in range(lines):
        angle = math.tau * i / lines
        x1 = cx + math.cos(angle) * radius * 0.15
        y1 = cy + math.sin(angle) * radius * 0.15
        x2 = cx + math.cos(angle) * radius
        y2 = cy + math.sin(angle) * radius
        group.add(dwg.line(start=(x1, y1), end=(x2, y2), stroke=stroke, stroke_width=stroke_width))
    dwg.add(group)
    return group

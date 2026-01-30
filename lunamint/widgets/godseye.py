"""God's-eye (Ojo de Dios) inspired vector motif."""
from __future__ import annotations

import math

import svgwrite

from .measure import mm_to_px


def add_godseye_mm(
    dwg: svgwrite.Drawing,
    cx_mm: float,
    cy_mm: float,
    radius_mm: float,
    rings: int = 6,
    rotation_deg: float = 0.0,
    stroke: str = "#111111",
    stroke_width_mm: float = 0.12,
    opacity: float = 0.6,
    dpi: float = 300.0,
) -> svgwrite.container.Group:
    """Draw concentric diamond rings with a subtle rotation."""
    cx = mm_to_px(cx_mm, dpi)
    cy = mm_to_px(cy_mm, dpi)
    radius = mm_to_px(radius_mm, dpi)
    stroke_width = mm_to_px(stroke_width_mm, dpi)

    group = dwg.g(opacity=opacity, transform=f"rotate({rotation_deg},{cx},{cy})")
    for i in range(rings):
        r = radius * (1 - i / max(1, rings))
        points = [
            (cx, cy - r),
            (cx + r, cy),
            (cx, cy + r),
            (cx - r, cy),
        ]
        group.add(dwg.polygon(points=points, fill="none", stroke=stroke, stroke_width=stroke_width))
    group.add(dwg.circle(center=(cx, cy), r=radius * 0.1, fill=stroke, stroke="none"))
    dwg.add(group)
    return group

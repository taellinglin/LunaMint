"""Rosette medallion patterns."""
from __future__ import annotations

import math

import svgwrite

from .measure import mm_to_px


def add_rosette(
    dwg: svgwrite.Drawing,
    cx: float,
    cy: float,
    radius: float,
    petals: int = 12,
    inner_ratio: float = 0.55,
    stroke: str = "#111111",
    stroke_width: float = 0.8,
    fill: str = "none",
    opacity: float = 0.65,
) -> svgwrite.container.Group:
    """Draw a classic banknote rosette using a rose curve."""
    group = dwg.g(opacity=opacity)
    inner = radius * inner_ratio
    points = []
    for i in range(361):
        theta = math.radians(i)
        r = inner + (radius - inner) * (math.sin(petals * theta) ** 2)
        x = cx + r * math.cos(theta)
        y = cy + r * math.sin(theta)
        points.append((x, y))
    path_data = "M " + " L ".join(f"{x:.2f},{y:.2f}" for x, y in points) + " Z"
    group.add(dwg.path(d=path_data, fill=fill, stroke=stroke, stroke_width=stroke_width))
    group.add(dwg.circle(center=(cx, cy), r=inner * 0.45, fill="none", stroke=stroke, stroke_width=stroke_width * 0.7))
    dwg.add(group)
    return group


def add_rosette_mm(
    dwg: svgwrite.Drawing,
    cx_mm: float,
    cy_mm: float,
    radius_mm: float,
    petals: int = 12,
    inner_ratio: float = 0.55,
    stroke: str = "#111111",
    stroke_width_mm: float = 0.1,
    fill: str = "none",
    opacity: float = 0.65,
    dpi: float = 300.0,
) -> svgwrite.container.Group:
    return add_rosette(
        dwg,
        cx=mm_to_px(cx_mm, dpi),
        cy=mm_to_px(cy_mm, dpi),
        radius=mm_to_px(radius_mm, dpi),
        petals=petals,
        inner_ratio=inner_ratio,
        stroke=stroke,
        stroke_width=mm_to_px(stroke_width_mm, dpi),
        fill=fill,
        opacity=opacity,
    )

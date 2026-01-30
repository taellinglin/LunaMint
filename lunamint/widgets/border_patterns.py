"""Additional border pattern widgets."""
from __future__ import annotations

import hashlib
import math
from typing import Iterable, Tuple

import svgwrite

from .measure import mm_to_px


Shape = Tuple[float, float, float, float]


def _iter_border_cells(x: float, y: float, width: float, height: float, cell: float) -> Iterable[Shape]:
    cols = max(1, int(math.ceil(width / cell)))
    rows = max(1, int(math.ceil(height / cell)))
    for r in range(rows):
        for c in range(cols):
            cx = x + c * cell
            cy = y + r * cell
            yield cx, cy, cell, cell


def add_barcode_border_mm(
    dwg: svgwrite.Drawing,
    x_mm: float,
    y_mm: float,
    width_mm: float,
    height_mm: float,
    border_thickness_mm: float = 2.5,
    module_mm: float = 0.5,
    data: str = "LUNAMINT",
    dark: str = "#111111",
    light: str = "#f8f8f8",
    opacity: float = 0.9,
    dpi: float = 300.0,
) -> svgwrite.container.Group:
    """Draw a barcode-like border ring with deterministic stripes."""
    x = mm_to_px(x_mm, dpi)
    y = mm_to_px(y_mm, dpi)
    width = mm_to_px(width_mm, dpi)
    height = mm_to_px(height_mm, dpi)
    thickness = mm_to_px(border_thickness_mm, dpi)
    module = max(1.0, mm_to_px(module_mm, dpi))

    group = dwg.g(opacity=opacity)
    seed = hashlib.sha3_256(data.encode("utf-8")).digest()

    def draw_band(bx: float, by: float, bw: float, bh: float, horizontal: bool) -> None:
        count = int(math.ceil((bw if horizontal else bh) / module))
        for i in range(count):
            v = seed[i % len(seed)]
            thickness_mod = module * (1.0 + (v % 3) * 0.35)
            if horizontal:
                bar_x = bx + i * module
                group.add(dwg.rect(insert=(bar_x, by), size=(thickness_mod, bh), fill=dark if v % 2 else light))
            else:
                bar_y = by + i * module
                group.add(dwg.rect(insert=(bx, bar_y), size=(bw, thickness_mod), fill=dark if v % 2 else light))

    draw_band(x, y, width, thickness, True)
    draw_band(x, y + height - thickness, width, thickness, True)
    draw_band(x, y, thickness, height, False)
    draw_band(x + width - thickness, y, thickness, height, False)

    dwg.add(group)
    return group


def add_tile_border_mm(
    dwg: svgwrite.Drawing,
    x_mm: float,
    y_mm: float,
    width_mm: float,
    height_mm: float,
    border_thickness_mm: float = 2.0,
    tile_mm: float = 1.6,
    data: str = "LUNAMINT",
    stroke: str = "#111111",
    fill: str = "#ffffff",
    opacity: float = 0.65,
    dpi: float = 300.0,
) -> svgwrite.container.Group:
    """Draw a tiled border of alternating shapes driven by data."""
    x = mm_to_px(x_mm, dpi)
    y = mm_to_px(y_mm, dpi)
    width = mm_to_px(width_mm, dpi)
    height = mm_to_px(height_mm, dpi)
    thickness = mm_to_px(border_thickness_mm, dpi)
    tile = max(1.0, mm_to_px(tile_mm, dpi))

    group = dwg.g(opacity=opacity)
    seed = hashlib.sha3_512(data.encode("utf-8")).digest()

    def draw_row(bx: float, by: float, bw: float, bh: float) -> None:
        cells = list(_iter_border_cells(bx, by, bw, bh, tile))
        for idx, (cx, cy, cw, ch) in enumerate(cells):
            v = seed[idx % len(seed)]
            kind = v % 4
            if kind == 0:
                group.add(dwg.rect(insert=(cx, cy), size=(cw, ch), fill=fill, stroke=stroke, stroke_width=0.6))
            elif kind == 1:
                group.add(dwg.circle(center=(cx + cw / 2, cy + ch / 2), r=min(cw, ch) * 0.45, fill=fill, stroke=stroke, stroke_width=0.6))
            elif kind == 2:
                points = [(cx + cw / 2, cy), (cx + cw, cy + ch / 2), (cx + cw / 2, cy + ch), (cx, cy + ch / 2)]
                group.add(dwg.polygon(points=points, fill=fill, stroke=stroke, stroke_width=0.6))
            else:
                points = [(cx, cy), (cx + cw, cy), (cx + cw / 2, cy + ch)]
                group.add(dwg.polygon(points=points, fill=fill, stroke=stroke, stroke_width=0.6))

    draw_row(x, y, width, thickness)
    draw_row(x, y + height - thickness, width, thickness)
    draw_row(x, y, thickness, height)
    draw_row(x + width - thickness, y, thickness, height)

    dwg.add(group)
    return group

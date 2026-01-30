"""Fractal cryptography stamp (L-system inspired)."""
from __future__ import annotations

import math

import svgwrite

from .measure import mm_to_px


def _lsystem(seed: str, rules: dict[str, str], iterations: int) -> str:
    result = seed
    for _ in range(iterations):
        result = "".join(rules.get(ch, ch) for ch in result)
    return result


def add_fractal_stamp_mm(
    dwg: svgwrite.Drawing,
    x_mm: float,
    y_mm: float,
    size_mm: float,
    seed: str = "F",
    rules: dict[str, str] | None = None,
    iterations: int = 3,
    angle_deg: float = 60,
    stroke: str = "#111111",
    stroke_width_mm: float = 0.08,
    opacity: float = 0.5,
    dpi: float = 300.0,
) -> svgwrite.container.Group:
    """Draw a compact fractal stamp using a turtle path."""
    rules = rules or {"F": "F+F--F+F"}
    command = _lsystem(seed, rules, iterations)

    x = mm_to_px(x_mm, dpi)
    y = mm_to_px(y_mm, dpi)
    size = mm_to_px(size_mm, dpi)
    stroke_width = mm_to_px(stroke_width_mm, dpi)

    heading = 0.0
    step = size / max(1, len(command) ** 0.5)
    points = [(x, y)]
    stack: list[tuple[float, float, float]] = []

    for ch in command:
        if ch == "F":
            x += math.cos(math.radians(heading)) * step
            y += math.sin(math.radians(heading)) * step
            points.append((x, y))
        elif ch == "+":
            heading += angle_deg
        elif ch == "-":
            heading -= angle_deg
        elif ch == "[":
            stack.append((x, y, heading))
        elif ch == "]" and stack:
            x, y, heading = stack.pop()
            points.append((x, y))

    path_data = "M " + " L ".join(f"{px:.2f},{py:.2f}" for px, py in points)
    group = dwg.g(opacity=opacity)
    group.add(dwg.path(d=path_data, fill="none", stroke=stroke, stroke_width=stroke_width))
    dwg.add(group)
    return group

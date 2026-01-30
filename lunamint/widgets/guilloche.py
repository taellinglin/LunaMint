"""Guilloche-style line patterns."""
from __future__ import annotations

import math
from typing import Iterable

import svgwrite

from .measure import mm_to_px


def _wave_points(x: float, y: float, width: float, amplitude: float, wavelength: float, phase: float) -> Iterable[tuple[float, float]]:
    steps = max(20, int(width / max(1.0, wavelength / 4)))
    for i in range(steps + 1):
        t = i / steps
        px = x + t * width
        py = y + math.sin((t * width / wavelength) * math.tau + phase) * amplitude
        yield px, py


def add_guilloche_band(
    dwg: svgwrite.Drawing,
    x: float,
    y: float,
    width: float,
    height: float,
    amplitude: float = 6.0,
    wavelength: float = 48.0,
    stroke: str = "#1b1b1b",
    stroke_width: float = 0.6,
    opacity: float = 0.55,
    layers: int = 4,
    phase_step: float = 0.5,
) -> svgwrite.container.Group:
    """Draw a horizontal guilloche band within a rectangle."""
    group = dwg.g(opacity=opacity)
    center_y = y + height / 2
    for layer in range(layers):
        phase = layer * phase_step
        offset = (layer - (layers - 1) / 2) * (height / max(1, layers))
        points = list(_wave_points(x, center_y + offset, width, amplitude, wavelength, phase))
        path_data = "M " + " L ".join(f"{px:.2f},{py:.2f}" for px, py in points)
        group.add(dwg.path(d=path_data, fill="none", stroke=stroke, stroke_width=stroke_width))
    dwg.add(group)
    return group


def add_guilloche_band_mm(
    dwg: svgwrite.Drawing,
    x_mm: float,
    y_mm: float,
    width_mm: float,
    height_mm: float,
    amplitude_mm: float = 0.6,
    wavelength_mm: float = 4.8,
    stroke: str = "#1b1b1b",
    stroke_width_mm: float = 0.08,
    opacity: float = 0.55,
    layers: int = 4,
    phase_step: float = 0.5,
    dpi: float = 300.0,
) -> svgwrite.container.Group:
    return add_guilloche_band(
        dwg,
        x=mm_to_px(x_mm, dpi),
        y=mm_to_px(y_mm, dpi),
        width=mm_to_px(width_mm, dpi),
        height=mm_to_px(height_mm, dpi),
        amplitude=mm_to_px(amplitude_mm, dpi),
        wavelength=mm_to_px(wavelength_mm, dpi),
        stroke=stroke,
        stroke_width=mm_to_px(stroke_width_mm, dpi),
        opacity=opacity,
        layers=layers,
        phase_step=phase_step,
    )

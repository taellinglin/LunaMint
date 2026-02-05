"""Pixel art stamping widget."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import svgwrite
from PIL import Image

from .measure import mm_to_px


@dataclass
class PixelArtOptions:
    pixel_size_mm: float = 0.5
    alpha_threshold: float = 0.05
    compress: bool = True
    dpi: float = 300.0


def _rgba_to_hex_opacity(rgba: tuple[int, int, int, int]) -> tuple[str, float]:
    r, g, b, a = rgba
    hex_color = f"#{r:02X}{g:02X}{b:02X}"
    opacity = a / 255.0
    return hex_color, opacity


def add_pixel_art_stamp_mm(
    dwg: svgwrite.Drawing,
    x_mm: float,
    y_mm: float,
    image_path: str,
    pixel_size_mm: float = 0.5,
    alpha_threshold: float = 0.05,
    compress: bool = True,
    dpi: float = 300.0,
) -> svgwrite.container.Group:
    if not image_path:
        return dwg.g()

    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"Pixel art image not found: {image_path}")

    base_x = mm_to_px(x_mm, dpi)
    base_y = mm_to_px(y_mm, dpi)
    pixel_size_px = mm_to_px(pixel_size_mm, dpi)

    img = Image.open(path).convert("RGBA")
    width, height = img.size
    pixels = img.load()

    group = dwg.g()

    for y in range(height):
        x = 0
        while x < width:
            rgba = pixels[x, y]
            if rgba[3] / 255.0 <= alpha_threshold:
                x += 1
                continue
            run_len = 1
            if compress:
                while x + run_len < width and pixels[x + run_len, y] == rgba:
                    run_len += 1
            hex_color, opacity = _rgba_to_hex_opacity(rgba)
            insert = (base_x + x * pixel_size_px, base_y + y * pixel_size_px)
            size = (pixel_size_px * run_len, pixel_size_px)
            rect_kwargs = {"insert": insert, "size": size, "fill": hex_color}
            if opacity < 1.0:
                rect_kwargs["fill_opacity"] = opacity
            group.add(dwg.rect(**rect_kwargs))
            x += run_len

    dwg.add(group)
    return group

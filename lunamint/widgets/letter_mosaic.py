"""Letter mosaic from image samples."""
from __future__ import annotations

import math
from pathlib import Path
from typing import Optional

from PIL import Image
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont
import svgwrite

from .measure import mm_to_px, snap_px


def add_letter_mosaic_from_image_mm(
    dwg: svgwrite.Drawing,
    image_path: str,
    x_mm: float,
    y_mm: float,
    width_mm: float,
    height_mm: float,
    font_name: str = "Daemon Full Working",
    font_dir: str = "./fonts",
    font_size_mm: float = 1.2,
    charset: str = "@#%*+=-:. ",
    invert: bool = False,
    opacity: float = 1.0,
    snap_grid_px: float = 16.0,
    dpi: float = 300.0,
) -> svgwrite.container.Group:
    img = Image.open(image_path).convert("L")
    x = mm_to_px(x_mm, dpi)
    y = mm_to_px(y_mm, dpi)
    width = mm_to_px(width_mm, dpi)
    height = mm_to_px(height_mm, dpi)
    font_size_px = mm_to_px(font_size_mm, dpi)

    font_path = None
    if Path(font_name).is_file():
        font_path = font_name
    else:
        for file in Path(font_dir).glob("*.ttf"):
            if font_name.lower().replace(" ", "") in file.stem.lower().replace(" ", ""):
                font_path = str(file)
                break
        if not font_path:
            for file in Path(font_dir).glob("*.otf"):
                if font_name.lower().replace(" ", "") in file.stem.lower().replace(" ", ""):
                    font_path = str(file)
                    break
    if not font_path:
        raise FileNotFoundError(f"Font '{font_name}' not found in {font_dir}")

    font = TTFont(font_path)
    units_per_em = font["head"].unitsPerEm
    scale = font_size_px / units_per_em
    glyph_set = font.getGlyphSet()
    cmap = font.getBestCmap()

    sample_glyph = glyph_set[cmap.get(ord("M"), list(glyph_set.keys())[0])]
    try:
        bbox = sample_glyph.boundingBox()
        x_min, y_min, x_max, y_max = bbox.xMin, bbox.yMin, bbox.xMax, bbox.yMax
    except Exception:
        x_min = getattr(sample_glyph, "xMin", 0)
        y_min = getattr(sample_glyph, "yMin", 0)
        x_max = getattr(sample_glyph, "xMax", font["head"].unitsPerEm)
        y_max = getattr(sample_glyph, "yMax", font["head"].unitsPerEm)
    cell_w = max(1.0, (x_max - x_min) * scale)
    cell_h = max(1.0, (y_max - y_min) * scale)

    cols = max(1, int(width / cell_w))
    rows = max(1, int(height / cell_h))
    img = img.resize((cols, rows))
    pixels = img.load()

    group = dwg.g(opacity=opacity)
    for r in range(rows):
        for c in range(cols):
            v = pixels[c, r]
            idx = int((v / 255) * (len(charset) - 1))
            if invert:
                idx = (len(charset) - 1) - idx
            ch = charset[idx]
            if ch == " ":
                continue
            glyph_name = cmap.get(ord(ch))
            if not glyph_name:
                continue
            glyph = glyph_set[glyph_name]
            pen = SVGPathPen(glyph_set)
            glyph.draw(pen)
            commands = pen.getCommands()
            if not commands:
                continue
            parsed = []
            for cmd, coords in _parse_svg_path(commands):
                new_coords = []
                for i in range(0, len(coords) - 1, 2):
                    px = x + c * cell_w + coords[i] * scale
                    py = y + (r + 1) * cell_h - coords[i + 1] * scale
                    if snap_grid_px > 0:
                        px = snap_px(px, snap_grid_px)
                        py = snap_px(py, snap_grid_px)
                    new_coords.extend([px, py])
                parsed.append((cmd, new_coords))
            group.add(dwg.path(d=_format_path(parsed), fill="#111111", stroke="none"))

    dwg.add(group)
    return group


def _parse_svg_path(path: str) -> list[tuple[str, list[float]]]:
    import re

    tokens = re.findall(r"[MLCQZmlcqz]|-?\d*\.?\d+(?:e[-+]?\d+)?", path)
    commands: list[tuple[str, list[float]]] = []
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token.upper() in {"M", "L", "C", "Q", "Z"}:
            cmd = token.upper()
            i += 1
            coords = []
            while i < len(tokens) and tokens[i].upper() not in {"M", "L", "C", "Q", "Z"}:
                coords.append(float(tokens[i]))
                i += 1
            commands.append((cmd, coords))
        else:
            i += 1
    return commands


def _format_path(commands: list[tuple[str, list[float]]]) -> str:
    parts = []
    for cmd, coords in commands:
        if coords:
            parts.append(cmd + " " + " ".join(f"{v:.2f}" for v in coords))
        else:
            parts.append(cmd)
    return " ".join(parts)

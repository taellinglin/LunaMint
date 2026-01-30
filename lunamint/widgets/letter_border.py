"""Letter border mask widget."""
from __future__ import annotations

import math
import os
from dataclasses import dataclass
from typing import Optional

import svgwrite
from PIL import ImageFont

from .measure import mm_to_px


@dataclass
class LetterBorderOptions:
    text: str = "LUNAMINT"
    font_name: str = "Daemon Full Working"
    font_dir: str = "./fonts"
    font_size_mm: float = 1.2
    spacing_mm: float = 0.2
    fill_color: str = "#111111"
    opacity: float = 1.0
    case: str = "upper"
    base_fill: Optional[str] = "#ffffff"
    pattern: str = "stripes"  # stripes | solid
    pattern_color: str = "#222222"
    pattern_opacity: float = 0.35


def _normalize_text(text: str, mode: str) -> str:
    text = text.replace("\n", " ").strip()
    if not text:
        return ""
    if mode == "lower":
        return text.lower()
    if mode == "preserve":
        return text
    return text.upper()


def _find_font_path(font_name: str, font_dir: str) -> str:
    if font_name and os.path.isfile(font_name):
        return font_name
    if os.path.isdir(font_dir):
        target = font_name.lower().replace(" ", "")
        for fn in os.listdir(font_dir):
            if not fn.lower().endswith((".ttf", ".otf")):
                continue
            name = os.path.splitext(fn)[0].lower().replace(" ", "")
            if target and target in name:
                return os.path.join(font_dir, fn)
    raise FileNotFoundError(f"Font '{font_name}' not found in {font_dir}")


def _load_font(font_name: str, font_dir: str, size_px: float) -> ImageFont.FreeTypeFont:
    font_path = _find_font_path(font_name, font_dir)
    return ImageFont.truetype(font_path, int(max(1, round(size_px))))


def _text_width(font: ImageFont.FreeTypeFont, text: str) -> float:
    box = font.getbbox(text)
    return max(1.0, float(box[2] - box[0]))


def add_letter_border_mask_mm(
    dwg: svgwrite.Drawing,
    x_mm: float,
    y_mm: float,
    width_mm: float,
    height_mm: float,
    border_thickness_mm: float = 3.0,
    text: str = "LUNAMINT",
    font_name: str = "Daemon Full Working",
    font_dir: str = "./fonts",
    font_size_mm: float = 1.2,
    spacing_mm: float = 0.2,
    fill_color: str = "#111111",
    opacity: float = 1.0,
    case: str = "upper",
    base_fill: Optional[str] = "#ffffff",
    pattern: str = "stripes",
    pattern_color: str = "#222222",
    pattern_opacity: float = 0.35,
    mask_id: Optional[str] = None,
    dpi: float = 300.0,
) -> svgwrite.container.Group:
    x = mm_to_px(x_mm, dpi)
    y = mm_to_px(y_mm, dpi)
    width = mm_to_px(width_mm, dpi)
    height = mm_to_px(height_mm, dpi)
    thickness = mm_to_px(border_thickness_mm, dpi)
    font_size_px = mm_to_px(font_size_mm, dpi)
    spacing_px = mm_to_px(spacing_mm, dpi)

    norm_text = _normalize_text(text, case)
    if not norm_text:
        return dwg.g()

    if base_fill:
        dwg.add(dwg.rect(insert=(x, y), size=(width, height), fill=base_fill))

    font = _load_font(font_name, font_dir, font_size_px)
    text_width = _text_width(font, norm_text)
    step = max(1.0, text_width + spacing_px)

    mask = dwg.defs.add(dwg.mask(id=mask_id or f"letter_border_{abs(hash(norm_text)) % 100000}"))
    mask.add(dwg.rect(insert=(x, y), size=(width, height), fill="#000"))

    def add_horizontal_band(y_pos: float) -> None:
        count = max(1, int(math.ceil(width / step)))
        for i in range(count):
            mask.add(
                dwg.text(
                    norm_text,
                    insert=(x + i * step, y_pos),
                    font_size=font_size_px,
                    font_family=font_name,
                    fill="#fff",
                )
            )

    top_y = y + font_size_px
    bottom_y = y + height - thickness + font_size_px
    add_horizontal_band(top_y)
    add_horizontal_band(bottom_y)

    line_height = max(1.0, font_size_px + spacing_px)
    total_chars = max(1, int(height / line_height))
    repeated = (norm_text * ((total_chars // len(norm_text)) + 1))[:total_chars]
    pad_x = max(1.0, thickness * 0.15)
    left_x = x + pad_x
    right_x = x + width - thickness + pad_x

    for idx, ch in enumerate(repeated):
        py = y + (idx + 1) * line_height
        if py > y + height:
            break
        mask.add(
            dwg.text(
                ch,
                insert=(left_x, py),
                font_size=font_size_px,
                font_family=font_name,
                fill="#fff",
            )
        )
        mask.add(
            dwg.text(
                ch,
                insert=(right_x, py),
                font_size=font_size_px,
                font_family=font_name,
                fill="#fff",
            )
        )

    group = dwg.g(opacity=opacity)
    group.update({"mask": f"url(#{mask['id']})"})

    if pattern == "stripes":
        stripe = dwg.g(opacity=pattern_opacity)
        spacing = max(6.0, font_size_px * 1.25)
        for i in range(int(-height), int(width + height), int(spacing)):
            stripe.add(
                dwg.line(
                    start=(x + i, y),
                    end=(x + i + height, y + height),
                    stroke=pattern_color,
                    stroke_width=1.2,
                )
            )
        group.add(stripe)
    else:
        group.add(dwg.rect(insert=(x, y), size=(width, height), fill=fill_color))

    dwg.add(group)
    return group

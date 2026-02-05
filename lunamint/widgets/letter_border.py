"""Letter border mask widget."""
from __future__ import annotations

import math
import os
import hashlib
import random
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
    inset_mm: float = 0.0
    outset_mm: float = 0.0
    offset_x_mm: float = 0.0
    offset_y_mm: float = 0.0
    layout: str = "band"  # band | packed
    palette: Optional[str] = None
    cycle_mode: str = "sequential"  # sequential | random | encoding
    cycle_seed: str = ""
    encoding_algo: str = "sha3_256"  # sha256 | sha3_256 | sm3 (if available)
    packed_spacing_x_mm: Optional[float] = None
    packed_spacing_y_mm: Optional[float] = None
    packed_glyph_scale: float = 1.0
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


def _parse_palette(palette: Optional[str | list[str]]) -> list[str]:
    if not palette:
        return []
    if isinstance(palette, list):
        return [str(p).strip() for p in palette if str(p).strip()]
    return [p.strip() for p in str(palette).split(",") if p.strip()]


def _hash_bytes(algo: str, data: bytes) -> bytes:
    name = algo.lower()
    if name == "sha256":
        return hashlib.sha256(data).digest()
    if name == "sm3":
        try:
            from gmssl import sm3, func  # type: ignore

            return bytes(sm3.sm3_hash(func.bytes_to_list(data)), "ascii")
        except Exception:
            return hashlib.sha3_256(data).digest()
    return hashlib.sha3_256(data).digest()


def _glyph_bbox(font: ImageFont.FreeTypeFont, ch: str) -> tuple[float, float, float, float]:
    box = font.getbbox(ch)
    return float(box[0]), float(box[1]), float(box[2]), float(box[3])


def _max_square_glyph(font: ImageFont.FreeTypeFont, text: str) -> float:
    max_dim = 1.0
    for ch in text:
        if ch.isspace():
            continue
        x0, y0, x1, y1 = _glyph_bbox(font, ch)
        max_dim = max(max_dim, x1 - x0, y1 - y0)
    return max_dim


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
    inset_mm: float = 0.0,
    outset_mm: float = 0.0,
    offset_x_mm: float = 0.0,
    offset_y_mm: float = 0.0,
    layout: str = "band",
    palette: Optional[str | list[str]] = None,
    cycle_mode: str = "sequential",
    cycle_seed: str = "",
    encoding_algo: str = "sha3_256",
    packed_spacing_x_mm: Optional[float] = None,
    packed_spacing_y_mm: Optional[float] = None,
    packed_glyph_scale: float = 1.0,
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
    outer_x = mm_to_px(x_mm, dpi)
    outer_y = mm_to_px(y_mm, dpi)
    outer_width = mm_to_px(width_mm, dpi)
    outer_height = mm_to_px(height_mm, dpi)
    inset_px = mm_to_px(inset_mm, dpi)
    outset_px = mm_to_px(outset_mm, dpi)
    offset_x_px = mm_to_px(offset_x_mm, dpi)
    offset_y_px = mm_to_px(offset_y_mm, dpi)

    x = outer_x - outset_px + inset_px + offset_x_px
    y = outer_y - outset_px + inset_px + offset_y_px
    width = max(1.0, outer_width + 2 * outset_px - 2 * inset_px)
    height = max(1.0, outer_height + 2 * outset_px - 2 * inset_px)
    thickness = mm_to_px(border_thickness_mm, dpi)
    font_size_px = mm_to_px(font_size_mm, dpi)
    spacing_px = mm_to_px(spacing_mm, dpi)

    norm_text = _normalize_text(text, case)
    if not norm_text:
        return dwg.g()

    if base_fill:
        dwg.add(dwg.rect(insert=(x, y), size=(width, height), fill=base_fill))

    font = _load_font(font_name, font_dir, font_size_px)

    if layout == "packed":
        if base_fill:
            dwg.add(dwg.rect(insert=(x, y), size=(width, height), fill=base_fill))

        chars = [ch for ch in norm_text if not ch.isspace()]
        if not chars:
            return dwg.g()

        base_cell = max(1.0, _max_square_glyph(font, norm_text) * max(0.1, packed_glyph_scale))
        spacing_x_px = spacing_px if packed_spacing_x_mm is None else mm_to_px(packed_spacing_x_mm, dpi)
        spacing_y_px = spacing_px if packed_spacing_y_mm is None else mm_to_px(packed_spacing_y_mm, dpi)
        cell_w = max(1.0, base_cell + max(0.0, spacing_x_px))
        cell_h = max(1.0, base_cell + max(0.0, spacing_y_px))
        cols = max(1, int(width // cell_w))
        rows = max(1, int(height // cell_h))
        grid_w = cols * cell_w
        grid_h = rows * cell_h
        start_x = x + (width - grid_w) / 2.0
        start_y = y + (height - grid_h) / 2.0

        inner_x = x + thickness
        inner_y = y + thickness
        inner_w = max(0.0, width - 2 * thickness)
        inner_h = max(0.0, height - 2 * thickness)

        palette_list = _parse_palette(palette)
        rng = random.Random(cycle_seed) if cycle_mode == "random" else None

        group = dwg.g(opacity=opacity)
        idx = 0
        for r in range(rows):
            cy = start_y + r * cell_h
            for c in range(cols):
                cx = start_x + c * cell_w

                if cx < x or cy < y or cx + cell_w > x + width or cy + cell_h > y + height:
                    continue

                intersects_inner = (
                    cx + cell_w > inner_x
                    and cx < inner_x + inner_w
                    and cy + cell_h > inner_y
                    and cy < inner_y + inner_h
                )
                if intersects_inner:
                    continue

                ch = chars[idx % len(chars)]
                idx += 1

                if palette_list:
                    if cycle_mode == "random":
                        color = rng.choice(palette_list) if rng else palette_list[0]
                    elif cycle_mode == "encoding":
                        payload = f"{cycle_seed}|{norm_text}|{r}|{c}|{ch}".encode("utf-8")
                        digest = _hash_bytes(encoding_algo, payload)
                        color = palette_list[int.from_bytes(digest[:2], "big") % len(palette_list)]
                    else:
                        color = palette_list[idx % len(palette_list)]
                else:
                    color = fill_color

                x0, y0, x1, y1 = _glyph_bbox(font, ch)
                glyph_w = x1 - x0
                glyph_h = y1 - y0
                gx = cx + (cell_w - glyph_w) / 2.0 - x0
                gy = cy + (cell_h - glyph_h) / 2.0 - y0

                group.add(
                    dwg.text(
                        ch,
                        insert=(gx, gy),
                        font_size=font_size_px,
                        font_family=font_name,
                        fill=color,
                    )
                )

        dwg.add(group)
        return group

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

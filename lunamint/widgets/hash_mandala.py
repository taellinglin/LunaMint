"""Hash mandala widgets (circular + rectangular)."""
from __future__ import annotations

import colorsys
import hashlib
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Tuple

from PIL import Image
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont
import svgwrite

from .measure import mm_to_px, snap_px


@dataclass
class HashMandalaOptions:
    font_name: str = "Daemon Full Working"
    font_dir: str = "./fonts"
    font_size_mm: float = 1.2
    charset: str = "LUNAMINT"
    rings: int = 0
    sectors: int = 0
    opacity: float = 0.85
    stroke_width_mm: float = 0.08
    colorize: bool = True
    use_roygbiv: bool = True
    grid_density: int = 10
    inset_scale: float = 0.85
    outset_scale: float = 1.15
    snap_grid_px: float = 8.0
    ring_rows: int = 3
    sector_density: float = 1.5
    fill_empty: bool = True
    background_color: str = "#0f1114"
    background_opacity: float = 0.25
    border_color: str = "#111111"
    border_width_mm: float = 0.12
    radial_lines: int = 24
    tick_major: int = 16
    tick_minor: int = 32
    core_rings: int = 4
    core_radials: int = 24
    core_letter_every: int = 2
    cardinal_markers: bool = True
    stroke_only: bool = False
    stroke_color: str = "#1a1a1a"
    stroke_color_secondary: str = "#1a1a1a"
    label_every: int = 4
    label_radius_ratio: float = 0.86
    label_font_size_mm: float = 1.0
    label_stroke_width_mm: float = 0.06
    sector_boxes: bool = True
    sector_box_size_mm: float = 1.4
    center_digit: int = 0
    center_digit_size_mm: float = 6.0
    center_digit_fill_background: bool = True
    flat_glyphs: bool = False
    glyph_fill: str = "#e6e6e6"
    glyph_stroke: str = "#1a1a1a"
    glyph_stroke_width_scale: float = 1.0
    min_cols_per_sector: int = 3
    taper_outer_strength: float = 0.35
    taper_radial_strength: float = 0.55
    ring_label_every: int = 0
    ring_label_alternate: bool = True
    ring_label_text: str = "123456789"
    ring_label_size_scale: float = 0.9
    sector_padding_deg: float = 0.0
    ring_padding_mm: float = 0.0
    sector_outline: bool = False
    sector_outline_color: str = "#1a1a1a"
    sector_outline_width_mm: float = 0.08
    ring_pattern_mode: bool = True
    sm2_row_variance: int = 2


def _find_font_path(font_name: str, font_dir: str) -> Optional[str]:
    if font_name and Path(font_name).is_file():
        return str(font_name)
    if not Path(font_dir).is_dir():
        return None
    target = font_name.lower().replace(" ", "")
    for file in Path(font_dir).glob("*.ttf"):
        if target and target in file.stem.lower().replace(" ", ""):
            return str(file)
    for file in Path(font_dir).glob("*.otf"):
        if target and target in file.stem.lower().replace(" ", ""):
            return str(file)
    return None


def _sm3_or_sha3(data: bytes) -> bytes:
    try:
        from lunalib.core import sm3  # type: ignore

        if hasattr(sm3, "hash"):
            result = sm3.hash(data)
        elif hasattr(sm3, "sm3_hash"):
            result = sm3.sm3_hash(data)
        elif hasattr(sm3, "hash_bytes"):
            result = sm3.hash_bytes(data)
        else:
            result = None
        if isinstance(result, bytes):
            return result
        if isinstance(result, str):
            try:
                return bytes.fromhex(result)
            except ValueError:
                return result.encode("utf-8")
        if isinstance(result, list):
            return bytes(result)
    except Exception:
        pass
    return hashlib.sha3_256(data).digest()


def _seed_from_data(data_text: str | None, data_path: str | None, data_type: str | None) -> Tuple[str, bytes]:
    if data_path and os.path.exists(data_path):
        raw = Path(data_path).read_bytes()
        suffix = Path(data_path).suffix.lower().lstrip(".")
        dtype = (data_type or suffix or "file").lower()
        if dtype in {"png", "jpg", "jpeg", "image"}:
            try:
                img = Image.open(data_path).convert("RGB")
                w, h = img.size
                palette = img.resize((8, 1)).getdata()
                colors = "-".join(f"{r:02x}{g:02x}{b:02x}" for r, g, b in palette)
                seed_text = f"IMG{w}x{h}-{colors}-{Path(data_path).name}"
                return seed_text, _sm3_or_sha3(seed_text.encode("utf-8"))
            except Exception:
                pass
        digest = _sm3_or_sha3(raw)
        seed_text = f"{dtype}:{Path(data_path).name}:{len(raw)}:{digest.hex()[:20]}"
        return seed_text, digest

    seed_text = (data_text or "LUNAMINT").strip()
    return seed_text, _sm3_or_sha3(seed_text.encode("utf-8"))


def _palette_from_hash(digest: bytes, count: int = 8) -> list[str]:
    colors: list[str] = []
    for i in range(count):
        a = digest[(i * 3) % len(digest)] / 255.0
        b = digest[(i * 3 + 1) % len(digest)] / 255.0
        c = digest[(i * 3 + 2) % len(digest)] / 255.0
        hue = a
        sat = 0.35 + b * 0.45
        lig = 0.25 + c * 0.45
        r, g, b = colorsys.hls_to_rgb(hue, lig, sat)
        colors.append(f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}")
    return colors


def _roygbiv_palette(digest: bytes, count: int = 24) -> list[str]:
    base = [
        (0.0, 0.75, 0.50),
        (30.0, 0.80, 0.55),
        (55.0, 0.85, 0.60),
        (120.0, 0.65, 0.45),
        (220.0, 0.75, 0.50),
        (260.0, 0.70, 0.45),
        (290.0, 0.75, 0.55),
    ]
    colors: list[str] = []
    for i in range(count):
        h, s, l = base[i % len(base)]
        a = digest[(i * 3) % len(digest)] / 255.0
        b = digest[(i * 3 + 1) % len(digest)] / 255.0
        c = digest[(i * 3 + 2) % len(digest)] / 255.0
        h += (a - 0.5) * 20.0
        s = max(0.45, min(0.95, s + (b - 0.5) * 0.20))
        l = max(0.35, min(0.65, l + (c - 0.5) * 0.20))
        r, g, b = colorsys.hls_to_rgb((h % 360) / 360.0, l, s)
        colors.append(f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}")
    return colors


def _char_stream(seed_text: str, charset: str) -> Iterable[str]:
    if not charset:
        charset = "LUNAMINT"
    raw = hashlib.sha3_256(seed_text.encode("utf-8")).digest()
    while True:
        for b in raw:
            yield charset[b % len(charset)]
        raw = hashlib.sha3_256(raw).digest()


def _glyph_path(font: TTFont, glyph_name: str) -> tuple[str, Tuple[float, float, float, float]] | None:
    glyph_set = font.getGlyphSet()
    glyph = glyph_set[glyph_name]
    pen = SVGPathPen(glyph_set)
    glyph.draw(pen)
    path = pen.getCommands()
    if not path:
        return None
    bounds_pen = BoundsPen(glyph_set)
    glyph.draw(bounds_pen)
    if not bounds_pen.bounds:
        return None
    return path, bounds_pen.bounds


def _seed_chars(seed_text: str) -> list[str]:
    chars = [ch for ch in seed_text.upper() if ch.isalnum()]
    if not chars:
        chars = ["X"]
    return chars[:8]


def _glyph_for_char(font: TTFont, cmap: dict[int, str], ch: str) -> tuple[str, Tuple[float, float, float, float]] | None:
    glyph_name = cmap.get(ord(ch))
    if not glyph_name:
        return None
    return _glyph_path(font, glyph_name)


def _add_radial_lines(
    group: svgwrite.container.Group,
    cx: float,
    cy: float,
    inner_r: float,
    outer_r: float,
    count: int,
    stroke: str,
    stroke_width: float,
    dash_every: int = 4,
    rotation: float = 0.0,
) -> None:
    for i in range(count):
        angle = (360 / max(1, count)) * i + rotation
        angle_rad = math.radians(angle - 90)
        x1 = cx + math.cos(angle_rad) * inner_r
        y1 = cy + math.sin(angle_rad) * inner_r
        x2 = cx + math.cos(angle_rad) * outer_r
        y2 = cy + math.sin(angle_rad) * outer_r
        line = svgwrite.shapes.Line(start=(x1, y1), end=(x2, y2), stroke=stroke, stroke_width=stroke_width)
        if dash_every and i % dash_every != 0:
            line.update({"stroke-dasharray": "4,2"})
        group.add(line)


def _add_tick_marks(
    group: svgwrite.container.Group,
    cx: float,
    cy: float,
    radius: float,
    count: int,
    tick_length: float,
    stroke: str,
    stroke_width: float,
    rotation: float = 0.0,
) -> None:
    for i in range(count):
        angle = (360 / max(1, count)) * i + rotation
        angle_rad = math.radians(angle - 90)
        x1 = cx + math.cos(angle_rad) * radius
        y1 = cy + math.sin(angle_rad) * radius
        x2 = cx + math.cos(angle_rad) * (radius - tick_length)
        y2 = cy + math.sin(angle_rad) * (radius - tick_length)
        group.add(svgwrite.shapes.Line(start=(x1, y1), end=(x2, y2), stroke=stroke, stroke_width=stroke_width))


def _add_sector_boxes(
    group: svgwrite.container.Group,
    cx: float,
    cy: float,
    radius: float,
    count: int,
    box_size: float,
    stroke: str,
    stroke_width: float,
) -> None:
    for i in range(count):
        angle = (360 / max(1, count)) * i
        angle_rad = math.radians(angle - 90)
        x = cx + math.cos(angle_rad) * radius
        y = cy + math.sin(angle_rad) * radius
        group.add(
            svgwrite.shapes.Rect(
                insert=(x - box_size / 2, y - box_size / 2),
                size=(box_size, box_size),
                fill="none",
                stroke=stroke,
                stroke_width=stroke_width,
                transform=f"rotate(45 {x:.2f} {y:.2f})",
            )
        )


def _add_sector_labels(
    group: svgwrite.container.Group,
    font: TTFont,
    cmap: dict[int, str],
    cx: float,
    cy: float,
    radius: float,
    count: int,
    label_every: int,
    labels: str,
    size_px: float,
    stroke: str,
    stroke_width: float,
    units_per_em: int,
) -> None:
    if label_every <= 0:
        return
    for i in range(count):
        if i % label_every != 0:
            continue
        angle = (360 / max(1, count)) * i
        angle_rad = math.radians(angle - 90)
        x = cx + math.cos(angle_rad) * radius
        y = cy + math.sin(angle_rad) * radius
        ch = labels[i % len(labels)]
        glyph_data = _glyph_for_char(font, cmap, ch)
        if not glyph_data:
            continue
        path, bounds = glyph_data
        min_x, min_y, max_x, max_y = bounds
        glyph_cx = (min_x + max_x) / 2
        glyph_cy = (min_y + max_y) / 2
        scale = size_px / units_per_em
        transform = (
            f"translate({x:.2f},{y:.2f}) "
            f"rotate({angle:.2f}) "
            f"scale({scale:.4f},{-scale:.4f}) "
            f"translate({-glyph_cx:.2f},{-glyph_cy:.2f})"
        )
        group.add(
            svgwrite.path.Path(
                d=path,
                fill="none",
                stroke=stroke,
                stroke_width=stroke_width,
                transform=transform,
            )
        )


def _digit_color(digit: int) -> str:
    start = (255, 64, 128)
    end = (128, 0, 255)
    t = max(0.0, min(1.0, (digit - 1) / 8))
    r = int(start[0] + (end[0] - start[0]) * t)
    g = int(start[1] + (end[1] - start[1]) * t)
    b = int(start[2] + (end[2] - start[2]) * t)
    return f"#{r:02x}{g:02x}{b:02x}"


def _next_glyph(
    font: TTFont,
    cmap: dict[int, str],
    char_iter: Iterable[str],
    fallback_char: str = "M",
) -> tuple[str, Tuple[float, float, float, float]] | None:
    glyph_set = font.getGlyphSet()
    attempts = 0
    while attempts < 64:
        attempts += 1
        ch = next(char_iter)
        glyph_name = cmap.get(ord(ch))
        if glyph_name and glyph_name in glyph_set:
            glyph_data = _glyph_path(font, glyph_name)
            if glyph_data:
                return glyph_data
    fallback_name = cmap.get(ord(fallback_char)) or next(iter(cmap.values()), None)
    if fallback_name:
        return _glyph_path(font, fallback_name)
    return None


def add_hash_mandala_mm(
    dwg: svgwrite.Drawing,
    cx_mm: float,
    cy_mm: float,
    radius_mm: float,
    data_text: str = "LUNAMINT",
    data_path: str | None = None,
    data_type: str | None = None,
    options: Optional[HashMandalaOptions] = None,
    dpi: float = 300.0,
) -> svgwrite.container.Group:
    opts = options or HashMandalaOptions()
    seed_text, digest = _seed_from_data(data_text, data_path, data_type)
    if opts.stroke_only:
        colors = [opts.stroke_color, opts.stroke_color_secondary]
    else:
        palette = _roygbiv_palette(digest, 28) if opts.use_roygbiv else _palette_from_hash(digest, 28)
        colors = palette if opts.colorize else ["#111111"] * len(palette)

    font_path = _find_font_path(opts.font_name, opts.font_dir)
    if not font_path:
        raise FileNotFoundError(f"Font '{opts.font_name}' not found in {opts.font_dir}")

    font = TTFont(font_path)
    units_per_em = font["head"].unitsPerEm
    font_size_px = mm_to_px(opts.font_size_mm, dpi)
    base_scale = font_size_px / units_per_em
    cmap = font.getBestCmap()
    seed_chars = _seed_chars(seed_text)

    cx = mm_to_px(cx_mm, dpi)
    cy = mm_to_px(cy_mm, dpi)
    radius = mm_to_px(radius_mm, dpi)
    stroke_width = mm_to_px(opts.stroke_width_mm, dpi)
    ring_padding_px = mm_to_px(opts.ring_padding_mm, dpi)
    sector_outline_width = mm_to_px(opts.sector_outline_width_mm, dpi)
    border_width = mm_to_px(opts.border_width_mm, dpi)
    label_size_px = mm_to_px(opts.label_font_size_mm, dpi)
    label_stroke_width = mm_to_px(opts.label_stroke_width_mm, dpi)
    box_size_px = mm_to_px(opts.sector_box_size_mm, dpi)

    base_stroke = opts.stroke_color if opts.stroke_only else "#111111"

    group = dwg.g(opacity=opts.opacity)

    if opts.background_color and opts.background_opacity > 0:
        group.add(
            dwg.circle(
                center=(cx, cy),
                r=radius * 0.98,
                fill=opts.background_color,
                opacity=opts.background_opacity,
                stroke="none",
            )
        )
    group.add(
        dwg.circle(
            center=(cx, cy),
            r=radius * 0.95,
            fill="none",
            stroke=base_stroke,
            stroke_width=stroke_width * 4.0,
        )
    )

    ring_count = opts.rings if opts.rings and opts.rings > 0 else 6 + (digest[0] % 4)
    base_sectors = opts.sectors if opts.sectors and opts.sectors > 0 else 12 + (digest[1] % 13)
    rotation_offset = (digest[2] / 255.0) * 360.0
    char_iter = _char_stream(seed_text, opts.charset)

    for ring_idx in range(ring_count):
        outer = radius * (0.92 - ring_idx * 0.75 / ring_count)
        inner = radius * (0.92 - (ring_idx + 1) * 0.75 / ring_count)
        outer -= ring_padding_px
        inner += ring_padding_px
        ring_thickness = max(1.0, outer - inner)
        ring_color = colors[ring_idx % len(colors)]
        base_stroke = opts.stroke_color if opts.stroke_only else "#111111"
        group.add(
            dwg.circle(
                center=(cx, cy),
                r=outer,
                fill="none",
                stroke=base_stroke,
                stroke_width=stroke_width,
                opacity=0.8,
            )
        )

        _add_radial_lines(
            group,
            cx,
            cy,
            inner,
            outer,
            count=max(6, int(base_sectors * (0.5 if ring_idx % 2 else 1.0))),
            stroke=base_stroke,
            stroke_width=stroke_width * 0.6,
            rotation=rotation_offset + ring_idx * 7.5,
        )

        layer_type = ring_idx % 4 if opts.ring_pattern_mode else -1
        if layer_type == 0:
            sectors = 1
            sector_pad = 0.0
        elif layer_type == 1:
            sectors = 8
            sector_pad = 1.0
        elif layer_type == 2:
            sectors = 16
            sector_pad = 0.0
        elif layer_type == 3:
            sectors = 12
            sector_pad = 0.5
        else:
            sectors = max(6, base_sectors + (digest[ring_idx % len(digest)] % 6))
            sector_pad = max(0.0, min((360.0 / sectors) * 0.4, opts.sector_padding_deg))

        sector_angle = 360.0 / sectors
        glyph_size_px = max(font_size_px, ring_thickness * 0.55)
        base_row_count = max(
            1,
            int(math.ceil(ring_thickness / max(1.0, glyph_size_px * 1.2) * opts.sector_density)),
        )
        base_row_count = max(base_row_count, opts.ring_rows)

        if layer_type == 2:
            _add_tick_marks(
                group,
                cx,
                cy,
                outer,
                count=sectors,
                tick_length=ring_thickness * 0.40,
                stroke=base_stroke,
                stroke_width=max(1.0, stroke_width * 0.9),
                rotation=rotation_offset,
            )
            for tick_idx in range(sectors):
                angle = tick_idx * sector_angle + rotation_offset
                angle_rad = math.radians(angle - 90)
                radius_mid = (outer + inner) * 0.5
                x = cx + math.cos(angle_rad) * radius_mid
                y = cy + math.sin(angle_rad) * radius_mid
                ch = seed_chars[(ring_idx + tick_idx) % len(seed_chars)]
                glyph_data = _glyph_for_char(font, cmap, ch)
                if not glyph_data:
                    continue
                path, bounds = glyph_data
                min_x, min_y, max_x, max_y = bounds
                glyph_cx = (min_x + max_x) / 2
                glyph_cy = (min_y + max_y) / 2
                size_px = max(6.0, ring_thickness * 0.5)
                scale = size_px / units_per_em
                transform = (
                    f"translate({x:.2f},{y:.2f}) "
                    f"rotate({angle:.2f}) "
                    f"scale({scale:.4f},{-scale:.4f}) "
                    f"translate({-glyph_cx:.2f},{-glyph_cy:.2f})"
                )
                letter_color = colors[(ring_idx * sectors + tick_idx) % len(colors)]
                group.add(
                    dwg.path(
                        d=path,
                        fill=letter_color if opts.flat_glyphs and opts.colorize else "none",
                        stroke=letter_color,
                        stroke_width=max(0.5, stroke_width * 0.5),
                        transform=transform,
                    )
                )
        else:
            for sector_idx in range(sectors):
                start_angle = sector_idx * sector_angle + sector_pad + rotation_offset
                angle_span = sector_angle - 2 * sector_pad
                sector_char = seed_chars[(ring_idx + sector_idx) % len(seed_chars)]
                sector_glyph = _glyph_for_char(font, cmap, sector_char)
                density_scale = 1.0
                size_scale = 1.0
                if layer_type == 3 and sector_idx % 2 == 1:
                    density_scale = 1.5
                    size_scale = 0.7
                if layer_type == 0:
                    density_scale = 1.2
                    size_scale = 0.6 / 0.55
                elif layer_type == 1:
                    density_scale = 1.5
                    size_scale = 0.35 / 0.55
                elif layer_type == 3 and sector_idx % 2 == 0:
                    density_scale = 0.8
                    size_scale = 0.5 / 0.55

                row_variance = 0
                if opts.sm2_row_variance > 0:
                    row_variance = digest[(ring_idx + sector_idx) % len(digest)] % (opts.sm2_row_variance + 1)
                row_count = max(1, base_row_count + row_variance)

                for row in range(row_count):
                    radius_mid = outer - (row + 0.5) * ring_thickness / row_count
                    arc_len = 2 * math.pi * radius_mid * (angle_span / 360.0)
                    base_cols = max(1, int(math.ceil(arc_len / max(1.0, glyph_size_px * 0.8))))
                    col_count = max(opts.min_cols_per_sector, int(math.ceil(base_cols * density_scale)))

                    for col in range(col_count):
                        angle = start_angle + (col + 0.5) * angle_span / col_count
                        label_char = ""
                        use_ring_label = (
                            opts.ring_label_every > 0
                            and (not opts.ring_label_alternate or ring_idx % 2 == 1)
                            and col % max(1, opts.ring_label_every) == 0
                        )
                        if use_ring_label and opts.ring_label_text:
                            label_char = opts.ring_label_text[(col + row + sector_idx) % len(opts.ring_label_text)]
                            glyph_data = _glyph_for_char(font, cmap, label_char) or _next_glyph(font, cmap, char_iter)
                        else:
                            glyph_data = sector_glyph or _next_glyph(font, cmap, char_iter)
                        if not glyph_data:
                            if not opts.fill_empty:
                                continue
                            else:
                                continue
                        path, bounds = glyph_data
                        min_x, min_y, max_x, max_y = bounds
                        glyph_cx = (min_x + max_x) / 2
                        glyph_cy = (min_y + max_y) / 2
                        glyph_w = max(1.0, max_x - min_x)
                        glyph_h = max(1.0, max_y - min_y)
                        cell_w = max(1.0, arc_len / max(1, col_count))
                        cell_h = max(1.0, ring_thickness / max(1, row_count))
                        stroke_px = stroke_width * max(0.3, opts.glyph_stroke_width_scale)
                        scale_w = max(0.0, (cell_w - stroke_px) / glyph_w)
                        scale_h = max(0.0, (cell_h - stroke_px) / glyph_h)
                        fit_scale = min(scale_w, scale_h) * 1.2 * size_scale
                        taper_t = min(1.0, radius_mid / max(1.0, radius))
                        taper_x = 1.0 - opts.taper_outer_strength * taper_t
                        taper_y = 1.0 - opts.taper_radial_strength * taper_t
                        base_scale = fit_scale * (
                            opts.outset_scale if (row + col + sector_idx) % 2 == 0 else opts.inset_scale
                        )
                        if use_ring_label:
                            base_scale *= opts.ring_label_size_scale
                        scale_x = base_scale * max(0.2, taper_x)
                        scale_y = base_scale * max(0.2, taper_y)

                        x = cx + radius_mid * math.cos(math.radians(angle - 90))
                        y = cy + radius_mid * math.sin(math.radians(angle - 90))
                        if opts.snap_grid_px > 0:
                            x = snap_px(x, opts.snap_grid_px)
                            y = snap_px(y, opts.snap_grid_px)

                        transform = (
                            f"translate({x:.2f},{y:.2f}) "
                            f"rotate({angle:.2f}) "
                            f"scale({scale_x:.4f},{-scale_y:.4f}) "
                            f"translate({-glyph_cx:.2f},{-glyph_cy:.2f})"
                        )
                        sector_color = colors[(ring_idx + sector_idx) % len(colors)]
                        glyph_stroke_width = stroke_width * max(0.3, opts.glyph_stroke_width_scale)
                        if layer_type == 0:
                            glyph_stroke_width *= 0.8
                        elif layer_type == 1:
                            glyph_stroke_width *= 0.6
                        elif layer_type == 3:
                            glyph_stroke_width *= 0.7

                        if opts.stroke_only:
                            fill = "none"
                            stroke = base_stroke
                        elif use_ring_label:
                            if opts.flat_glyphs:
                                fill = sector_color if opts.colorize else opts.glyph_fill
                            else:
                                fill = "none"
                            if opts.ring_label_text and label_char.isdigit():
                                stroke = _digit_color(int(label_char))
                            else:
                                stroke = opts.glyph_stroke
                        elif opts.flat_glyphs:
                            fill = sector_color if opts.colorize else opts.glyph_fill
                            stroke = sector_color
                        else:
                            fill = colors[(ring_idx + sector_idx + row) % len(colors)]
                            stroke = colors[(ring_idx + sector_idx + row + 3) % len(colors)]
                        group.add(
                            dwg.path(
                                d=path,
                                fill=fill,
                                stroke=stroke,
                                stroke_width=glyph_stroke_width,
                                transform=transform,
                            )
                        )

        if ring_idx % 2 == 0:
            _add_tick_marks(
                group,
                cx,
                cy,
                inner,
                count=max(12, base_sectors * 2),
                tick_length=stroke_width * 6,
                stroke=base_stroke,
                stroke_width=stroke_width * 0.5,
                rotation=rotation_offset + ring_idx * 3.75,
            )
        if opts.sector_outline:
            for sector_idx in range(sectors):
                angle = sector_idx * sector_angle
                angle_rad = math.radians(angle - 90)
                x1 = cx + math.cos(angle_rad) * inner
                y1 = cy + math.sin(angle_rad) * inner
                x2 = cx + math.cos(angle_rad) * outer
                y2 = cy + math.sin(angle_rad) * outer
                group.add(
                    svgwrite.shapes.Line(
                        start=(x1, y1),
                        end=(x2, y2),
                        stroke=opts.sector_outline_color,
                        stroke_width=sector_outline_width,
                    )
                )

    base_stroke = opts.stroke_color if opts.stroke_only else "#111111"
    _add_radial_lines(
        group,
        cx,
        cy,
        radius * 0.12,
        radius * 0.95,
        count=max(12, opts.radial_lines),
        stroke=base_stroke,
        stroke_width=stroke_width * 0.7,
        rotation=rotation_offset,
    )

    _add_tick_marks(
        group,
        cx,
        cy,
        radius * 0.98,
        count=max(8, opts.tick_major),
        tick_length=stroke_width * 10,
        stroke=base_stroke,
        stroke_width=stroke_width * 0.9,
        rotation=rotation_offset,
    )
    _add_tick_marks(
        group,
        cx,
        cy,
        radius * 0.98,
        count=max(12, opts.tick_minor),
        tick_length=stroke_width * 6,
        stroke=base_stroke,
        stroke_width=stroke_width * 0.6,
        rotation=rotation_offset,
    )

    if opts.sector_boxes:
        _add_sector_boxes(
            group,
            cx,
            cy,
            radius * 0.97,
            count=max(8, opts.sectors),
            box_size=box_size_px,
            stroke=base_stroke,
            stroke_width=stroke_width * 0.8,
        )

    _add_sector_labels(
        group,
        font,
        cmap,
        cx,
        cy,
        radius * opts.label_radius_ratio,
        count=max(8, opts.sectors),
        label_every=max(1, opts.label_every),
        labels="0123456789",
        size_px=label_size_px,
        stroke=base_stroke,
        stroke_width=label_stroke_width,
        units_per_em=units_per_em,
    )

    innermost_radius = radius * (0.92 - 0.75)
    core_radius = innermost_radius * 0.85
    group.add(
        dwg.circle(
            center=(cx, cy),
            r=core_radius,
            fill="none",
            stroke=base_stroke,
            stroke_width=stroke_width * 1.2,
        )
    )
    _add_radial_lines(
        group,
        cx,
        cy,
        0,
        core_radius,
        count=max(12, opts.core_radials),
        stroke=base_stroke,
        stroke_width=stroke_width * 0.7,
        dash_every=0,
        rotation=rotation_offset,
    )
    for i in range(1, max(1, opts.core_rings) + 1):
        r = core_radius * (i / (opts.core_rings + 1))
        group.add(
            dwg.circle(
                center=(cx, cy),
                r=r,
                fill="none",
                stroke=base_stroke,
                stroke_width=stroke_width * 0.7,
            )
        )
        if opts.core_letter_every > 0 and i % opts.core_letter_every == 0:
            count = 12 + i * 4
            for j in range(count):
                angle = (360 / count) * j
                angle_rad = math.radians(angle - 90)
                x = cx + math.cos(angle_rad) * r
                y = cy + math.sin(angle_rad) * r
                ch = seed_chars[j % len(seed_chars)]
                glyph_data = _glyph_for_char(font, cmap, ch)
                if not glyph_data:
                    continue
                path, bounds = glyph_data
                min_x, min_y, max_x, max_y = bounds
                glyph_cx = (min_x + max_x) / 2
                glyph_cy = (min_y + max_y) / 2
                size_px = max(6.0, font_size_px * 0.5)
                scale = size_px / units_per_em
                transform = (
                    f"translate({x:.2f},{y:.2f}) "
                    f"rotate({angle:.2f}) "
                    f"scale({scale:.4f},{-scale:.4f}) "
                    f"translate({-glyph_cx:.2f},{-glyph_cy:.2f})"
                )
                if opts.stroke_only:
                    core_fill = "none"
                    core_stroke = base_stroke
                elif opts.flat_glyphs:
                    core_fill = opts.glyph_fill
                    core_stroke = opts.glyph_stroke
                else:
                    core_fill = "none"
                    core_stroke = base_stroke
                letter_color = colors[(i * count + j) % len(colors)]
                group.add(
                    dwg.path(
                        d=path,
                        fill=letter_color if opts.flat_glyphs and opts.colorize else core_fill,
                        stroke=letter_color if opts.colorize else core_stroke,
                        stroke_width=max(0.4, stroke_width * 0.4),
                        transform=transform,
                    )
                )

    if opts.cardinal_markers:
        cardinal_radius = radius * 0.97
        for idx, angle in enumerate([0, 90, 180, 270]):
            angle_rad = math.radians(angle - 90)
            x = cx + math.cos(angle_rad) * cardinal_radius
            y = cy + math.sin(angle_rad) * cardinal_radius
            box = stroke_width * 10
            group.add(
                dwg.rect(
                    insert=(x - box / 2, y - box / 2),
                    size=(box, box),
                    fill="none",
                    stroke=base_stroke,
                    stroke_width=stroke_width * 0.9,
                    transform=f"rotate(45 {x:.2f} {y:.2f})",
                )
            )
            ch = seed_chars[idx % len(seed_chars)]
            glyph_data = _glyph_for_char(font, cmap, ch)
            if not glyph_data:
                continue
            path, bounds = glyph_data
            min_x, min_y, max_x, max_y = bounds
            glyph_cx = (min_x + max_x) / 2
            glyph_cy = (min_y + max_y) / 2
            size_px = max(8.0, font_size_px * 0.8)
            scale = size_px / units_per_em
            transform = (
                f"translate({x:.2f},{y:.2f}) "
                f"scale({scale:.4f},{-scale:.4f}) "
                f"translate({-glyph_cx:.2f},{-glyph_cy:.2f})"
            )
            if opts.stroke_only:
                marker_fill = "none"
                marker_stroke = base_stroke
            elif opts.flat_glyphs:
                marker_fill = opts.glyph_fill
                marker_stroke = opts.glyph_stroke
            else:
                marker_fill = "none"
                marker_stroke = base_stroke
            group.add(
                dwg.path(
                    d=path,
                    fill=marker_fill,
                    stroke=marker_stroke,
                    stroke_width=stroke_width * 0.7,
                    transform=transform,
                )
            )

    if 1 <= opts.center_digit <= 9:
        ch = str(opts.center_digit)
        glyph_data = _glyph_for_char(font, cmap, ch)
        if glyph_data:
            path, bounds = glyph_data
            min_x, min_y, max_x, max_y = bounds
            glyph_cx = (min_x + max_x) / 2
            glyph_cy = (min_y + max_y) / 2
            size_px = mm_to_px(opts.center_digit_size_mm, dpi)
            scale = size_px / units_per_em
            digit_color = _digit_color(opts.center_digit)
            fill_color = (
                colors[digest[3] % len(colors)]
                if opts.center_digit_fill_background
                else "none"
            )
            group.add(
                dwg.path(
                    d=path,
                    fill=fill_color,
                    stroke=digit_color,
                    stroke_width=stroke_width * 1.4,
                    transform=(
                        f"translate({cx:.2f},{cy:.2f}) "
                        f"scale({scale:.4f},{-scale:.4f}) "
                        f"translate({-glyph_cx:.2f},{-glyph_cy:.2f})"
                    ),
                )
            )

    if opts.border_color and border_width > 0:
        group.add(
            dwg.circle(
                center=(cx, cy),
                r=radius * 0.98,
                fill="none",
                stroke=opts.border_color,
                stroke_width=border_width,
                opacity=0.9,
            )
        )

    dwg.add(group)
    return group


def add_hash_mandala_rect_mm(
    dwg: svgwrite.Drawing,
    x_mm: float,
    y_mm: float,
    width_mm: float,
    height_mm: float,
    data_text: str = "LUNAMINT",
    data_path: str | None = None,
    data_type: str | None = None,
    options: Optional[HashMandalaOptions] = None,
    dpi: float = 300.0,
) -> svgwrite.container.Group:
    opts = options or HashMandalaOptions()
    seed_text, digest = _seed_from_data(data_text, data_path, data_type)
    palette = _palette_from_hash(digest)
    colors = palette if opts.colorize else ["#111111"] * len(palette)

    font_path = _find_font_path(opts.font_name, opts.font_dir)
    if not font_path:
        raise FileNotFoundError(f"Font '{opts.font_name}' not found in {opts.font_dir}")
    font = TTFont(font_path)
    units_per_em = font["head"].unitsPerEm
    font_size_px = mm_to_px(opts.font_size_mm, dpi)
    base_scale = font_size_px / units_per_em
    cmap = font.getBestCmap()

    x = mm_to_px(x_mm, dpi)
    y = mm_to_px(y_mm, dpi)
    width = mm_to_px(width_mm, dpi)
    height = mm_to_px(height_mm, dpi)
    stroke_width = mm_to_px(opts.stroke_width_mm, dpi)

    group = dwg.g(opacity=opts.opacity)
    group.add(
        dwg.rect(
            insert=(x, y),
            size=(width, height),
            fill="none",
            stroke=colors[0],
            stroke_width=stroke_width,
        )
    )

    cols = max(4, opts.grid_density)
    rows = max(4, int(opts.grid_density * (height / max(1.0, width))))
    cell_w = width / cols
    cell_h = height / rows
    char_iter = _char_stream(seed_text, opts.charset)

    for r in range(rows):
        for c in range(cols):
            glyph_char = next(char_iter)
            glyph_name = cmap.get(ord(glyph_char))
            if not glyph_name:
                continue
            glyph_data = _glyph_path(font, glyph_name)
            if not glyph_data:
                continue
            path, bounds = glyph_data
            min_x, min_y, max_x, max_y = bounds
            glyph_cx = (min_x + max_x) / 2
            glyph_cy = (min_y + max_y) / 2

            scale = base_scale * (opts.outset_scale if (r + c) % 2 == 0 else opts.inset_scale)
            cx = x + c * cell_w + cell_w / 2
            cy = y + r * cell_h + cell_h / 2
            if opts.snap_grid_px > 0:
                cx = snap_px(cx, opts.snap_grid_px)
                cy = snap_px(cy, opts.snap_grid_px)

            fill = colors[(r + c) % len(colors)]
            stroke = colors[(r + c + 4) % len(colors)]
            transform = (
                f"translate({cx:.2f},{cy:.2f}) "
                f"scale({scale:.4f},{-scale:.4f}) "
                f"translate({-glyph_cx:.2f},{-glyph_cy:.2f})"
            )
            group.add(
                dwg.path(
                    d=path,
                    fill=fill,
                    stroke=stroke,
                    stroke_width=stroke_width,
                    transform=transform,
                )
            )

    # Overlay grid lines
    for c in range(1, cols):
        gx = x + c * cell_w
        group.add(
            dwg.line(
                start=(gx, y),
                end=(gx, y + height),
                stroke=colors[c % len(colors)],
                stroke_width=stroke_width * 0.5,
                opacity=0.6,
            )
        )
    for r in range(1, rows):
        gy = y + r * cell_h
        group.add(
            dwg.line(
                start=(x, gy),
                end=(x + width, gy),
                stroke=colors[r % len(colors)],
                stroke_width=stroke_width * 0.5,
                opacity=0.6,
            )
        )

    dwg.add(group)
    return group

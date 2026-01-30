"""Border widgets for back-side banknote graphics."""
from __future__ import annotations

import math
import random
from typing import List, Tuple

import svgwrite


def add_functional_corner_decorations(dwg, W, H, denom, timestamp, serial_id,
                                      size=100, padding=75, stroke_width=1):
    COLORS = [
        ("#D80027", "#FF5555", "#FF69B4"),
        ("#009E60", "#55FFAA", "#FFD700"),
        ("#0052B4", "#55AAFF", "#FF69B4"),
        ("#222222", "#AAAAAA", "#FFD700"),
    ]

    def micro_text_pattern(x, y, text, rows=12, cols=12, spacing=10,
                           c_main="#000", c_highlight="#FF69B4"):
        for row in range(rows):
            for col in range(cols):
                color = c_main if (row + col) % 3 else c_highlight
                dwg.add(dwg.text(text,
                                 insert=(x + col * spacing, y + row * spacing),
                                 font_size=6, font_family="Daemon Full Working",
                                 fill=color, opacity=0.25))

    def tesselated_triangles(dwg, x, y, s, rows=8, cols=8,
                             c_main="#000", c_highlight="#FFD700"):
        h = s * (3 ** 0.5) / 2
        for row in range(rows):
            for col in range(cols):
                x0 = x + col * s
                y0 = y + row * h
                if (row + col) % 2 == 0:
                    pts = [(x0, y0 + h), (x0 + s / 2, y0), (x0 + s, y0 + h)]
                else:
                    pts = [(x0, y0), (x0 + s, y0), (x0 + s / 2, y0 + h)]
                stroke_color = c_main if (row + col) % 4 else c_highlight
                dwg.add(dwg.polygon(points=pts, fill="none",
                                    stroke=stroke_color,
                                    stroke_width=0.6, opacity=0.7))

    def top_left(x, y, denom):
        main, secondary, highlight = COLORS[0]
        for i in range(3):
            offset = i * size * 0.18
            stroke_c = main if i % 2 == 0 else highlight
            dwg.add(dwg.rect(insert=(x + offset, y + offset),
                             size=(size - 2 * offset, size - 2 * offset),
                             rx=8, ry=8, fill="none",
                             stroke=stroke_c, stroke_width=stroke_width))
        dwg.add(dwg.text(denom, insert=(x + size / 2, y + size / 2),
                         font_size=22, text_anchor="middle",
                         alignment_baseline="middle",
                         font_family="Daemon Full Working", fill=secondary))
        micro_text_pattern(x + 12, y + 12, denom, c_main=secondary, c_highlight=highlight)

    def top_right(x, y, denom):
        main, secondary, highlight = COLORS[1]
        tesselated_triangles(dwg, x - size, y, size / 6, rows=12, cols=12,
                             c_main=main, c_highlight=highlight)
        dwg.add(dwg.text(denom, insert=(x - size / 2, y + size / 2),
                         font_size=20, text_anchor="middle",
                         alignment_baseline="middle",
                         font_family="Daemon Full Working", fill=random.choice([secondary, highlight])))

    def bottom_left(x, y, denom):
        main, secondary, highlight = COLORS[2]
        tesselated_triangles(dwg, x, y - size, size / 6, rows=12, cols=12,
                             c_main=main, c_highlight=highlight)
        dwg.add(dwg.text(denom, insert=(x + size / 2, y - size / 2),
                         font_size=20, text_anchor="middle",
                         alignment_baseline="middle",
                         font_family="Daemon Full Working", fill=random.choice([secondary, highlight])))

    def bottom_right(x, y, denom, timestamp):
        main, secondary, highlight = COLORS[3]
        for i in range(4):
            offset = i * size * 0.18
            stroke_c = main if i % 2 else highlight
            dwg.add(dwg.rect(insert=(x - size + offset, y - size + offset),
                             size=(size - 2 * offset, size - 2 * offset),
                             rx=10, ry=10, fill="none",
                             stroke=stroke_c, stroke_width=stroke_width))
        dwg.add(dwg.text(denom, insert=(x - size / 2, y - size / 2),
                         font_size=22, text_anchor="middle",
                         alignment_baseline="middle",
                         font_family="Daemon Full Working", fill=random.choice([secondary, highlight])))
        micro_text_pattern(x - size + 5, y - size + 5, f"{denom} {timestamp}",
                           c_main=secondary, c_highlight=highlight)

    top_left(padding, padding, denom)
    top_right(W - padding, padding, denom)
    bottom_left(padding, H - padding, denom)
    bottom_right(W - padding, H - padding, denom, timestamp)


def add_decorative_border(dwg, W: int, H: int, border_info: dict, denom_value: int, timestamp_ms: int):
    import datetime
    if isinstance(timestamp_ms, dict):
        timestamp_ms = timestamp_ms.get("timestamp_ms", 0)

    ts = datetime.datetime.fromtimestamp(timestamp_ms / 1000.0)
    bands = [
        ("year", ts.year % 100, 0.25 + 0.025),
        ("month", ts.month, 0.1875 + 0.025),
        ("day", ts.day, 0.125 + 0.025),
        ("hour", ts.hour, 0.1875 + 0.025),
        ("minute", ts.minute, 0.09375 + 0.025),
        ("second", ts.second, 0.046875 + 0.025),
        ("microsecond", ts.microsecond // 1000, 0.0234375 + 0.025),
    ]

    start_x = float(border_info.get("diamond_start_x", 0))
    start_y = float(border_info.get("diamond_start_y", 0))
    width = float(border_info.get("diamond_width", W))
    height = float(border_info.get("diamond_height", H))

    cm_to_px = lambda cm: float(cm * 96.0 / 2.54)
    pad_base = cm_to_px(0.25)
    inset = -0.75
    denom_value = denom_value or 0

    def draw_shape(g, x, y, size, kind, band_index):
        half = size / 2.0
        fill_black = band_index % 2 == 0

        if fill_black:
            fill_color = "#000"
            stroke_color = "#FFFFFF"
            stroke_opacity = 1 / (band_index + 0.01)
            fill_opacity = 1
        else:
            fill_color = "#FFF"
            stroke_color = "#000000"
            fill_opacity = band_index / 1
            stroke_opacity = 1

        stroke_width = max(0.5, size * 0.025)

        if kind == 0:
            pts = [(x + half, y), (x + size, y + half), (x + half, y + size), (x, y + half)]
            g.add(dwg.polygon(points=pts, fill=fill_color, fill_opacity=fill_opacity,
                              stroke=stroke_color, stroke_opacity=stroke_opacity, stroke_width=stroke_width))
        elif kind == 1:
            pts = [(x + half, y), (x + size, y + half), (x + half, y + size), (x, y + half)]
            g.add(dwg.polygon(points=pts, fill="none",
                              stroke=stroke_color, stroke_opacity=stroke_opacity, stroke_width=stroke_width))
        elif kind == 2:
            g.add(dwg.rect(insert=(x, y), size=(size, size), fill=fill_color,
                           fill_opacity=fill_opacity, stroke=stroke_color,
                           stroke_opacity=stroke_opacity, stroke_width=stroke_width))
        elif kind == 3:
            g.add(dwg.rect(insert=(x, y), size=(size, size), fill="none",
                           stroke=stroke_color, stroke_opacity=stroke_opacity, stroke_width=stroke_width))
        elif kind == 4:
            g.add(dwg.line(start=(x, y), end=(x + size, y + size), stroke=stroke_color,
                           stroke_width=stroke_width, stroke_opacity=stroke_opacity))
            g.add(dwg.line(start=(x + size, y), end=(x, y + size), stroke=stroke_color,
                           stroke_width=stroke_width, stroke_opacity=stroke_opacity))

    group = dwg.g(opacity=0.7)
    y = start_y + pad_base
    for band_index, (_band, value, thickness) in enumerate(bands):
        x = start_x + pad_base
        size = cm_to_px(thickness)
        pattern_len = int((width - 2 * pad_base) / size)
        for i in range(pattern_len):
            kind = (value + i + denom_value) % 5
            draw_shape(group, x, y, size, kind, band_index)
            x += size
        y += size + inset

    dwg.add(group)


def add_qr_like_border(dwg: svgwrite.Drawing, seed: str, width: int, height: int, serial_id=None, timestamp_ms=None):
    inset_px = mm_to_px(0.5)
    border_thickness_px = mm_to_px(3)

    qr_border_start_x = float(inset_px)
    qr_border_start_y = float(inset_px)
    qr_border_end_x = float(width - inset_px)
    qr_border_end_y = float(height - inset_px)

    qr_border_inner_start_x = qr_border_start_x + border_thickness_px
    qr_border_inner_start_y = qr_border_start_y + border_thickness_px
    qr_border_inner_end_x = qr_border_end_x - border_thickness_px
    qr_border_inner_end_y = qr_border_end_y - border_thickness_px

    cell = max(2, border_thickness_px // 8)

    qr_border_width = qr_border_end_x - qr_border_start_x
    qr_border_height = qr_border_end_y - qr_border_start_y
    cols = int(math.ceil(qr_border_width / cell))
    rows = int(math.ceil(qr_border_height / cell))

    seed_bytes = to_bytes(make_qr_seed(seed, serial_id, str(timestamp_ms) if timestamp_ms else None))

    for r in range(rows):
        for c in range(cols):
            x = float(qr_border_start_x + c * cell)
            y = float(qr_border_start_y + r * cell)

            if (qr_border_inner_start_x <= x < qr_border_inner_end_x and
                qr_border_inner_start_y <= y < qr_border_inner_end_y):
                continue

            idx = (r * cols + c) % len(seed_bytes)
            v = seed_bytes[idx]

            red = int((v * 3) % 256)
            green = int((v * 7 + r * 5) % 256)
            blue = int((v * 13 + c * 11) % 256)
            color = f"rgb({red},{green},{blue})"

            s = 1.0 if (v % 3 == 0) else (0.6 if (v % 3 == 1) else 0.35)
            w = float(max(1, int(cell * s)))
            h = float(max(1, int(cell * s)))

            dwg.add(dwg.rect(
                insert=(x + (cell - w) / 2, y + (cell - h) / 2),
                size=(w, h),
                fill=color,
                fill_opacity=1.0,
            ))

    return {
        "diamond_start_x": qr_border_inner_start_x,
        "diamond_start_y": qr_border_inner_start_y,
        "diamond_width": qr_border_inner_end_x - qr_border_inner_start_x,
        "diamond_height": qr_border_inner_end_y - qr_border_inner_start_y,
        "image_start_x": qr_border_inner_start_x + border_thickness_px,
        "image_start_y": qr_border_inner_start_y + border_thickness_px,
        "image_width": qr_border_inner_end_x - qr_border_inner_start_x - 2 * border_thickness_px,
        "image_height": qr_border_inner_end_y - qr_border_inner_start_y - 2 * border_thickness_px,
    }


def mm_to_px(mm: float, dpi: float = 300.0) -> int:
    return int(round(mm * dpi / 25.4))


def to_bytes(s: str) -> bytes:
    return str(s).encode("utf-8")


def make_qr_seed(seed: str, serial_id: str = None, timestamp: str = None) -> str:
    parts = []
    if seed:
        parts.append(seed)
    if serial_id:
        parts.append(serial_id)
    if timestamp:
        parts.append(timestamp)
    return "_".join(parts) if parts else "default_seed"

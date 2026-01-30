"""Border widgets for front-side banknote graphics."""
from __future__ import annotations

import math
from typing import Dict

import svgwrite


def make_qr_seed(seed: str, serial_id: str = None, timestamp: str = None) -> str:
    parts = []
    if seed:
        parts.append(seed)
    if serial_id:
        parts.append(serial_id)
    if timestamp:
        parts.append(timestamp)
    return "_".join(parts) if parts else "default_seed"


def add_qr_like_border(
    dwg: svgwrite.Drawing,
    seed: str,
    width: int,
    height: int,
    serial_id=None,
    timestamp_ms=None,
    inset_mm: float = 0.5,
    border_thickness_mm: float = 3.0,
):
    inset_px = mm_to_px(inset_mm)
    border_thickness_px = mm_to_px(border_thickness_mm)

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


def add_subtle_frame_and_microgrid(dwg, W: int, H: int, border_info: Dict, denomination: int, timestamp_ms: int, seed_hash: bytes):
    diamond_start_x = border_info["diamond_start_x"] + 0.25
    diamond_start_y = border_info["diamond_start_y"] + 0.25
    diamond_width = border_info["diamond_width"] - 0.25
    diamond_height = border_info["diamond_height"] - 0.25

    denom_seed = denomination % 100
    time_seed = timestamp_ms % 10000
    hash_seed = sum(seed_hash) % 256 if seed_hash else 0

    pad = int(min(diamond_width, diamond_height) * 0.03)

    microgrid = dwg.g(opacity=0.12)
    step = 10 + (denom_seed % 7)

    for x in range(int(diamond_start_x + pad), int(diamond_start_x + diamond_width - pad), step):
        for y in range(int(diamond_start_y + pad), int(diamond_start_y + diamond_height - pad), step):
            size = 1 + ((hash_seed + x + y) % 3)
            microgrid.add(dwg.circle(center=(x, y), r=size, fill="#000000"))

    dwg.add(microgrid)

    frame = dwg.g(opacity=0.5)
    frame.add(dwg.rect(
        insert=(diamond_start_x + pad, diamond_start_y + pad),
        size=(diamond_width - 2 * pad, diamond_height - 2 * pad),
        fill="none",
        stroke="#222",
        stroke_width=1.2,
    ))
    frame.add(dwg.rect(
        insert=(diamond_start_x + pad + 6, diamond_start_y + pad + 6),
        size=(diamond_width - 2 * pad - 12, diamond_height - 2 * pad - 12),
        fill="none",
        stroke="#555",
        stroke_width=0.8,
    ))
    dwg.add(frame)

    accents = dwg.g(opacity=0.6)
    accent_color = "#222" if (time_seed % 2 == 0) else "#444"
    accents.add(dwg.line(
        start=(diamond_start_x + pad, diamond_start_y + pad),
        end=(diamond_start_x + diamond_width - pad, diamond_start_y + diamond_height - pad),
        stroke=accent_color,
        stroke_width=0.5,
    ))
    accents.add(dwg.line(
        start=(diamond_start_x + pad, diamond_start_y + diamond_height - pad),
        end=(diamond_start_x + diamond_width - pad, diamond_start_y + pad),
        stroke=accent_color,
        stroke_width=0.5,
    ))
    dwg.add(accents)


def add_decorative_border(dwg, W: int, H: int, border_info: Dict, denom_value: int, timestamp_ms: int):
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


def mm_to_px(mm: float, dpi: float = 300.0) -> int:
    return int(round(mm * dpi / 25.4))


def to_bytes(s: str) -> bytes:
    return str(s).encode("utf-8")

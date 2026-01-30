"""Warped polar text dial and grid encoders."""
from __future__ import annotations

import hashlib
import math
from pathlib import Path
from typing import Iterable, Optional

import svgwrite
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.basePen import BasePen
from fontTools.pens.boundsPen import BoundsPen
from fontTools.ttLib import TTFont

from .measure import mm_to_px, snap_px


def _normalize_text(text: str, mode: str = "upper") -> str:
    text = text.replace(" ", "").replace("\n", "")
    out = []
    for ch in text:
        code = ord(ch)
        if 32 <= code <= 126:
            if mode == "lower":
                out.append(ch.lower())
            elif mode == "preserve":
                out.append(ch)
            else:
                out.append(ch.upper())
        else:
            out.append(f"{code:X}")
    return "".join(out)


def _repeat_to_capacity(text: str, capacity: int) -> str:
    if capacity <= 0 or not text:
        return ""
    repeats = (capacity + len(text) - 1) // len(text)
    return (text * repeats)[:capacity]


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


class WarpPen(BasePen):
    def __init__(self, glyph_set, out_pen, warp_func):
        super().__init__(glyph_set)
        self.out_pen = out_pen
        self.warp = warp_func

    def _moveTo(self, p0):
        self.out_pen.moveTo(self.warp(*p0))

    def _lineTo(self, p1):
        self.out_pen.lineTo(self.warp(*p1))

    def _curveToOne(self, p1, p2, p3):
        self.out_pen.curveTo(self.warp(*p1), self.warp(*p2), self.warp(*p3))

    def _qCurveToOne(self, p1, p2):
        self.out_pen.qCurveTo(self.warp(*p1), self.warp(*p2))

    def _closePath(self):
        self.out_pen.closePath()

    def _endPath(self):
        self.out_pen.endPath()


def _warp_point(
    x: float,
    y: float,
    cx: float,
    cy: float,
    radius: float,
    angle_start: float,
    angle_span: float,
    advance: float,
    snap: float,
) -> tuple[float, float]:
    if advance <= 0:
        advance = 1.0
    t = x / advance
    angle = angle_start + angle_span * t
    r = radius + y
    px = cx + r * math.cos(angle)
    py = cy + r * math.sin(angle)
    if snap > 0:
        return snap_px(px, snap), snap_px(py, snap)
    return px, py


def _color_for_index(seed: bytes, idx: int) -> str:
    hue = (seed[idx % len(seed)] * 137) % 360
    sat = 70
    light = 40 + (seed[(idx + 3) % len(seed)] % 30)
    return _hsl_to_hex(hue, sat, light)


def _resolve_glyph_name(cmap: dict[int, str], glyph_set, ch: str) -> Optional[str]:
    glyph_name = cmap.get(ord(ch))
    if not glyph_name or glyph_name in {".notdef", "NULL"}:
        if ch.islower():
            glyph_name = cmap.get(ord(ch.upper()))
        elif ch.isupper():
            glyph_name = cmap.get(ord(ch.lower()))
    if not glyph_name or glyph_name in {".notdef", "NULL"}:
        return None
    if glyph_name not in glyph_set:
        return None
    return glyph_name


def _hsl_to_hex(h: float, s: float, l: float) -> str:
    h = (h % 360) / 360.0
    s = max(0.0, min(1.0, s / 100.0))
    l = max(0.0, min(1.0, l / 100.0))

    def _hue_to_rgb(p: float, q: float, t: float) -> float:
        if t < 0:
            t += 1
        if t > 1:
            t -= 1
        if t < 1 / 6:
            return p + (q - p) * 6 * t
        if t < 1 / 2:
            return q
        if t < 2 / 3:
            return p + (q - p) * (2 / 3 - t) * 6
        return p

    if s == 0:
        r = g = b = l
    else:
        q = l + s - l * s if l >= 0.5 else l * (1 + s)
        p = 2 * l - q
        r = _hue_to_rgb(p, q, h + 1 / 3)
        g = _hue_to_rgb(p, q, h)
        b = _hue_to_rgb(p, q, h - 1 / 3)

    return f"#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}"


def _load_font(font_path: str) -> TTFont:
    return TTFont(font_path)


def _find_font_path(font_name: str, font_dir: str) -> str:
    if font_name and Path(font_name).is_file():
        return font_name
    for ext in (".ttf", ".otf"):
        candidate = Path(font_dir) / f"{font_name}{ext}"
        if candidate.exists():
            return str(candidate)
    for file in Path(font_dir).glob("*.ttf"):
        if font_name.lower().replace(" ", "") in file.stem.lower().replace(" ", ""):
            return str(file)
    for file in Path(font_dir).glob("*.otf"):
        if font_name.lower().replace(" ", "") in file.stem.lower().replace(" ", ""):
            return str(file)
    raise FileNotFoundError(f"Font '{font_name}' not found in {font_dir}")


def add_polar_text_dial_px(
    dwg: svgwrite.Drawing,
    cx: float,
    cy: float,
    radius: float,
    text: str,
    rings: int = 6,
    font_name: str = "Daemon Full Working",
    font_dir: str = "./fonts",
    font_size_px: float = 16.0,
    spacing_px: float = 2.0,
    ring_gap_px: float = 4.0,
    rotation_seed: str = "",
    snap_grid_px: float = 16.0,
    clip_radius_px: Optional[float] = None,
    case: str = "upper",
    inner_radius_px: Optional[float] = None,
) -> svgwrite.container.Group:
    norm_text = _normalize_text(text, case)
    if not norm_text:
        return dwg.g()

    font_path = _find_font_path(font_name, font_dir)
    font = _load_font(font_path)
    glyph_set = font.getGlyphSet()
    cmap = font.getBestCmap()
    units_per_em = font["head"].unitsPerEm
    scale = font_size_px / units_per_em

    seed = hashlib.sha3_256((norm_text + rotation_seed).encode("utf-8")).digest()

    group = dwg.g()
    if clip_radius_px:
        clip = dwg.defs.add(dwg.clipPath(id="dial_clip"))
        clip.add(dwg.circle(center=(cx, cy), r=clip_radius_px))
        group.update({"clip-path": "url(#dial_clip)"})

    min_radius = inner_radius_px if inner_radius_px is not None else font_size_px
    for ring_idx in range(rings):
        ring_radius = radius - ring_idx * (font_size_px + ring_gap_px)
        if ring_radius <= min_radius:
            break
        circumference = 2 * math.pi * ring_radius
        sample_advances = []
        for ch in norm_text:
            glyph_name = _resolve_glyph_name(cmap, glyph_set, ch)
            if not glyph_name:
                continue
            sample_advances.append(font["hmtx"][glyph_name][0] * scale)
        avg_advance = (sum(sample_advances) / len(sample_advances)) if sample_advances else font_size_px
        capacity = max(1, int(circumference / max(1.0, avg_advance + spacing_px)))
        ring_text = _repeat_to_capacity(norm_text, capacity)
        ring_rotation = (seed[ring_idx % len(seed)] / 255.0) * 2 * math.pi

        advances: list[float] = []
        glyph_names: list[Optional[str]] = []
        for ch in ring_text:
            glyph_name = _resolve_glyph_name(cmap, glyph_set, ch)
            glyph_names.append(glyph_name)
            if glyph_name:
                advances.append(max(1.0, font["hmtx"][glyph_name][0] * scale))
            else:
                advances.append(max(1.0, avg_advance))

        total_advance = sum(a + spacing_px for a in advances)
        if total_advance <= 0:
            continue

        cursor_advance = 0.0
        for char_idx, ch in enumerate(ring_text):
            glyph_name = glyph_names[char_idx]
            if not glyph_name:
                cursor_advance += advances[char_idx] + spacing_px
                continue
            glyph = glyph_set[glyph_name]
            advance = advances[char_idx]
            angle_start = ring_rotation + (cursor_advance / total_advance) * (2 * math.pi)
            angle_span = ((advance + spacing_px) / total_advance) * (2 * math.pi)

            def _warp(x, y):
                return _warp_point(
                    x * scale,
                    y * scale,
                    cx,
                    cy,
                    ring_radius,
                    angle_start,
                    angle_span,
                    advance,
                    snap_grid_px,
                )

            out_pen = SVGPathPen(glyph_set)
            warp_pen = WarpPen(glyph_set, out_pen, _warp)
            glyph.draw(warp_pen)
            path = out_pen.getCommands()
            if not path:
                continue
            color = _color_for_index(seed, char_idx + ring_idx)
            group.add(dwg.path(d=path, fill=color, stroke="none"))
            cursor_advance += advance + spacing_px

    dwg.add(group)
    return group


def add_polar_text_dial_mm(
    dwg: svgwrite.Drawing,
    cx_mm: float,
    cy_mm: float,
    radius_mm: float,
    text: str,
    rings: int = 6,
    font_name: str = "Daemon Full Working",
    font_dir: str = "./fonts",
    font_size_mm: float = 1.2,
    spacing_mm: float = 0.2,
    ring_gap_mm: float = 0.6,
    rotation_seed: str = "",
    snap_grid_px: float = 16.0,
    clip_radius_mm: Optional[float] = None,
    case: str = "upper",
    inner_radius_mm: Optional[float] = None,
    dpi: float = 300.0,
) -> svgwrite.container.Group:
    return add_polar_text_dial_px(
        dwg,
        cx=mm_to_px(cx_mm, dpi),
        cy=mm_to_px(cy_mm, dpi),
        radius=mm_to_px(radius_mm, dpi),
        text=text,
        rings=rings,
        font_name=font_name,
        font_dir=font_dir,
        font_size_px=mm_to_px(font_size_mm, dpi),
        spacing_px=mm_to_px(spacing_mm, dpi),
        ring_gap_px=mm_to_px(ring_gap_mm, dpi),
        rotation_seed=rotation_seed,
        snap_grid_px=snap_grid_px,
        clip_radius_px=mm_to_px(clip_radius_mm, dpi) if clip_radius_mm else None,
        case=case,
        inner_radius_px=mm_to_px(inner_radius_mm, dpi) if inner_radius_mm else None,
    )


def add_text_grid_cipher_px(
    dwg: svgwrite.Drawing,
    x: float,
    y: float,
    width: float,
    height: float,
    text: str,
    font_name: str = "Daemon Full Working",
    font_dir: str = "./fonts",
    font_size_px: float = 16.0,
    spacing_px: float = 0.0,
    snap_grid_px: float = 16.0,
) -> svgwrite.container.Group:
    norm_text = _normalize_text(text)
    if not norm_text:
        return dwg.g()

    font_path = _find_font_path(font_name, font_dir)
    font = TTFont(font_path)
    units_per_em = font["head"].unitsPerEm
    scale = font_size_px / units_per_em
    glyph_set = font.getGlyphSet()
    cmap = font.getBestCmap()

    sample_glyph = glyph_set[cmap.get(ord("M"), list(glyph_set.keys())[0])]
    bounds_pen = BoundsPen(glyph_set)
    sample_glyph.draw(bounds_pen)
    bounds = bounds_pen.bounds
    if bounds:
        min_x, min_y, max_x, max_y = bounds
        cell_w = max(1.0, (max_x - min_x) * scale + spacing_px)
        cell_h = max(1.0, (max_y - min_y) * scale + spacing_px)
    else:
        cell_w = max(1.0, font_size_px + spacing_px)
        cell_h = max(1.0, font_size_px + spacing_px)

    cols = max(1, int(width / cell_w))
    rows = max(1, int(height / cell_h))
    total = cols * rows
    filled = _repeat_to_capacity(norm_text, total)
    seed = hashlib.sha3_256(norm_text.encode("utf-8")).digest()

    group = dwg.g()
    idx = 0
    for r in range(rows):
        for c in range(cols):
            ch = filled[idx]
            idx += 1
            glyph_name = _resolve_glyph_name(cmap, glyph_set, ch)
            if not glyph_name:
                continue
            glyph = glyph_set[glyph_name]
            base_x = x + c * cell_w
            base_y = y + (r + 1) * cell_h
            color = _color_for_index(seed, idx)

            def _warp_grid(xp, yp):
                px = base_x + xp * scale
                py = base_y - yp * scale
                if snap_grid_px > 0:
                    px = snap_px(px, snap_grid_px)
                    py = snap_px(py, snap_grid_px)
                return px, py

            out_pen = SVGPathPen(glyph_set)
            warp_pen = WarpPen(glyph_set, out_pen, _warp_grid)
            glyph.draw(warp_pen)
            path = out_pen.getCommands()
            if path:
                group.add(dwg.path(d=path, fill=color, stroke="none"))
    dwg.add(group)
    return group


def add_text_grid_cipher_mm(
    dwg: svgwrite.Drawing,
    x_mm: float,
    y_mm: float,
    width_mm: float,
    height_mm: float,
    text: str,
    font_name: str = "Daemon Full Working",
    font_dir: str = "./fonts",
    font_size_mm: float = 1.2,
    spacing_mm: float = 0.0,
    snap_grid_px: float = 16.0,
    dpi: float = 300.0,
) -> svgwrite.container.Group:
    return add_text_grid_cipher_px(
        dwg,
        x=mm_to_px(x_mm, dpi),
        y=mm_to_px(y_mm, dpi),
        width=mm_to_px(width_mm, dpi),
        height=mm_to_px(height_mm, dpi),
        text=text,
        font_name=font_name,
        font_dir=font_dir,
        font_size_px=mm_to_px(font_size_mm, dpi),
        spacing_px=mm_to_px(spacing_mm, dpi),
        snap_grid_px=snap_grid_px,
    )

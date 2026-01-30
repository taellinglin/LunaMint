"""MIDI-driven mandala dial widget."""
from __future__ import annotations

import colorsys
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import svgwrite
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont

from .measure import mm_to_px

NOTE_ALPHA = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
CC_ALPHA = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"


@dataclass
class MidiDialOptions:
    font_name: str = "Daemon Full Working"
    font_dir: str = "./fonts"
    font_size_mm: float = 2.2
    note_charset: str = NOTE_ALPHA
    cc_charset: str = CC_ALPHA
    note_opacity: float = 0.95
    cc_opacity: float = 0.9
    background_color: str = "#000000"
    background_opacity: float = 0.35
    outer_stroke: str = "#111111"
    outer_stroke_width_mm: float = 0.5
    note_stroke: str = "#111111"
    note_stroke_width_mm: float = 0.12
    cc_mark_length_mm: float = 1.0
    cc_mark_width_mm: float = 0.08
    cc_ring_offset_mm: float = 1.2
    inner_radius_ratio: float = 0.12
    outer_radius_ratio: float = 0.92
    rotation_deg: float = 0.0


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


def _glyph_for_char(font: TTFont, cmap: Dict[int, str], ch: str) -> tuple[str, Tuple[float, float, float, float]] | None:
    glyph_name = cmap.get(ord(ch))
    if not glyph_name:
        return None
    return _glyph_path(font, glyph_name)


def _note_char(note: int, charset: str) -> str:
    if not charset:
        charset = NOTE_ALPHA
    return charset[note % len(charset)]


def _cc_color(cc_value: int) -> str:
    hue = (cc_value / 127.0) % 1.0
    r, g, b = colorsys.hls_to_rgb(hue, 0.55, 0.75)
    return f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"


def _note_color(note: int, velocity: int) -> str:
    hue = ((note % 12) / 12.0) % 1.0
    light = 0.35 + (velocity / 127.0) * 0.35
    r, g, b = colorsys.hls_to_rgb(hue, light, 0.75)
    return f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"


def _load_midi_events(path: Path) -> tuple[List[dict], List[dict], float]:
    try:
        import mido
    except Exception as exc:
        raise RuntimeError("mido is required for midi_dial. Install it with pip install mido.") from exc

    midi = mido.MidiFile(path)
    tempo = 500000
    current_time = 0.0
    active_notes: Dict[Tuple[int, int], dict] = {}
    notes: List[dict] = []
    cc_events: List[dict] = []

    for msg in mido.merge_tracks(midi.tracks):
        current_time += mido.tick2second(msg.time, midi.ticks_per_beat, tempo)
        if msg.type == "set_tempo":
            tempo = msg.tempo
            continue
        if msg.type == "note_on" and msg.velocity > 0:
            active_notes[(msg.channel, msg.note)] = {
                "start": current_time,
                "velocity": msg.velocity,
                "note": msg.note,
                "channel": msg.channel,
            }
        elif msg.type in {"note_off", "note_on"}:
            if msg.type == "note_on" and msg.velocity > 0:
                continue
            key = (msg.channel, msg.note)
            if key in active_notes:
                start = active_notes[key]["start"]
                notes.append(
                    {
                        "start": start,
                        "end": current_time,
                        "note": msg.note,
                        "velocity": active_notes[key]["velocity"],
                        "channel": msg.channel,
                    }
                )
                del active_notes[key]
        elif msg.type == "control_change":
            cc_events.append(
                {
                    "time": current_time,
                    "control": msg.control,
                    "value": msg.value,
                    "channel": msg.channel,
                }
            )

    max_time = 0.0
    if notes:
        max_time = max(max_time, max(n["end"] for n in notes))
    if cc_events:
        max_time = max(max_time, max(c["time"] for c in cc_events))
    if max_time <= 0:
        max_time = 1.0

    return notes, cc_events, max_time


def add_midi_dial_mm(
    dwg: svgwrite.Drawing,
    cx_mm: float,
    cy_mm: float,
    radius_mm: float,
    midi_path: str,
    options: Optional[MidiDialOptions] = None,
    dpi: float = 300.0,
) -> svgwrite.container.Group:
    opts = options or MidiDialOptions()
    path = Path(midi_path)
    if not path.exists():
        raise FileNotFoundError(f"MIDI file not found: {midi_path}")

    notes, cc_events, max_time = _load_midi_events(path)

    font_path = _find_font_path(opts.font_name, opts.font_dir)
    if not font_path:
        raise FileNotFoundError(f"Font not found: {opts.font_name}")
    font = TTFont(font_path)
    cmap = font.getBestCmap() or {}
    units_per_em = font["head"].unitsPerEm

    cx = mm_to_px(cx_mm, dpi)
    cy = mm_to_px(cy_mm, dpi)
    radius = mm_to_px(radius_mm, dpi)
    font_px = mm_to_px(opts.font_size_mm, dpi)
    outer_stroke = mm_to_px(opts.outer_stroke_width_mm, dpi)
    note_stroke = mm_to_px(opts.note_stroke_width_mm, dpi)
    cc_mark_len = mm_to_px(opts.cc_mark_length_mm, dpi)
    cc_mark_w = mm_to_px(opts.cc_mark_width_mm, dpi)
    cc_offset = mm_to_px(opts.cc_ring_offset_mm, dpi)

    group = dwg.g()
    if opts.background_color and opts.background_opacity > 0:
        group.add(
            dwg.circle(
                center=(cx, cy),
                r=radius * opts.outer_radius_ratio,
                fill=opts.background_color,
                opacity=opts.background_opacity,
                stroke="none",
            )
        )

    group.add(
        dwg.circle(
            center=(cx, cy),
            r=radius * opts.outer_radius_ratio,
            fill="none",
            stroke=opts.outer_stroke,
            stroke_width=outer_stroke,
        )
    )

    if notes:
        min_note = min(n["note"] for n in notes)
        max_note = max(n["note"] for n in notes)
    else:
        min_note = 0
        max_note = 1

    inner_r = radius * opts.inner_radius_ratio
    outer_r = radius * opts.outer_radius_ratio
    span = max(1, max_note - min_note)

    for note in notes:
        t = note["start"] / max_time
        angle = opts.rotation_deg + t * 360.0
        angle_rad = math.radians(angle - 90)
        radius_mid = inner_r + ((note["note"] - min_note) / span) * (outer_r - inner_r)
        x = cx + math.cos(angle_rad) * radius_mid
        y = cy + math.sin(angle_rad) * radius_mid

        ch = _note_char(note["note"], opts.note_charset)
        glyph = _glyph_for_char(font, cmap, ch)
        if not glyph:
            continue
        path_d, bounds = glyph
        min_x, min_y, max_x, max_y = bounds
        glyph_cx = (min_x + max_x) / 2
        glyph_cy = (min_y + max_y) / 2
        scale = font_px / units_per_em
        transform = (
            f"translate({x:.2f},{y:.2f}) "
            f"rotate({angle:.2f}) "
            f"scale({scale:.4f},{-scale:.4f}) "
            f"translate({-glyph_cx:.2f},{-glyph_cy:.2f})"
        )
        color = _note_color(note["note"], note["velocity"])
        group.add(
            dwg.path(
                d=path_d,
                fill=color,
                stroke=opts.note_stroke,
                stroke_width=note_stroke,
                opacity=opts.note_opacity,
                transform=transform,
            )
        )

    for event in cc_events:
        t = event["time"] / max_time
        angle = opts.rotation_deg + t * 360.0
        angle_rad = math.radians(angle - 90)
        r0 = outer_r + cc_offset
        r1 = r0 + cc_mark_len
        x1 = cx + math.cos(angle_rad) * r0
        y1 = cy + math.sin(angle_rad) * r0
        x2 = cx + math.cos(angle_rad) * r1
        y2 = cy + math.sin(angle_rad) * r1
        color = _cc_color(event["value"])
        group.add(
            dwg.line(
                start=(x1, y1),
                end=(x2, y2),
                stroke=color,
                stroke_width=cc_mark_w,
                opacity=opts.cc_opacity,
            )
        )

    dwg.add(group)
    return group

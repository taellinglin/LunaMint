"""EisenScript: simple script-to-SVG + HTML/Canvas renderer."""
from __future__ import annotations

import base64
import json
import shlex
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import math
import svgwrite

from ..widgets.measure import mm_to_px

from ..graphics.generate_banknote_front import generate_fantasy_banknote
from ..graphics.generate_banknote_back import (
    generate_backside_svg,
    add_vectorized_background as add_back_vectorized_background,
    add_functional_corner_decorations,
    add_corner_denoms,
    add_circular_qr_continuous,
    add_holographic_seals,
    add_center_text,
    add_verification_text,
    add_security_background,
    add_qr_like_border,
    add_chinese_microprint,
    add_rainbow_microseal,
    add_colored_aztec_to_canvas,
    denom_to_int,
    generate_timestamp_ms_precise,
)
from ..graphics.modules.qr import safe_make_matrix, denomination_to_color
from ..filters import (
    add_vectorized_background,
    add_triangle_mosaic_background,
    add_letter_mosaic_background,
    add_glyph_grid_background,
    generate_sd_background,
)
from ..filters.glyph_grid import GlyphGridConfig
from ..widgets.glyph_grid import GlyphGridOptions
from ..widgets import (
    add_polar_text_dial_mm,
    add_text_grid_cipher_mm,
    add_letter_border_mask_mm,
    add_hash_mandala_mm,
    add_hash_mandala_rect_mm,
    HashMandalaOptions,
    add_midi_dial_mm,
    MidiDialOptions,
)


@dataclass
class CanvasState:
    width: int = 1600
    height: int = 600
    background: str = "#ffffff"


@dataclass
class DrawOp:
    op: str
    args: Dict[str, object]


@dataclass
class ScriptProgram:
    state: CanvasState = field(default_factory=CanvasState)
    ops: List[DrawOp] = field(default_factory=list)


def _parse_kv_args(args: List[str]) -> Dict[str, str]:
    values: Dict[str, str] = {}
    last_key: Optional[str] = None
    for arg in args:
        if "=" not in arg:
            if not last_key:
                raise ValueError(f"Invalid argument '{arg}', expected key=value")
            values[last_key] = f"{values[last_key]} {arg}".strip()
            continue
        key, value = arg.split("=", 1)
        if not key:
            raise ValueError(f"Invalid argument '{arg}', missing key")
        key = key.strip()
        cleaned = value.strip()
        if (cleaned.startswith('"') and cleaned.endswith('"')) or (cleaned.startswith("'") and cleaned.endswith("'")):
            cleaned = cleaned[1:-1].strip()
        values[key] = cleaned
        last_key = key
    return values


def _coerce_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _coerce_float(value: str, fallback: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _coerce_int(value: str, fallback: int) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return fallback


def _normalize_front_params(args: Dict[str, str]) -> Dict[str, object]:
    seed_text = args.get("seed_text", "LunaMint")
    input_image_path = args.get("input_image_path") or args.get("input_image", "")
    width_mm = _coerce_float(args.get("width_mm", "160"), 160.0)
    height_mm = _coerce_float(args.get("height_mm", "60"), 60.0)
    title = args.get("title", "灵国国库")
    subtitle = args.get("subtitle", "天圆地方")
    serial_id = args.get("serial_id") or None
    timestamp = args.get("timestamp") or None
    denomination = args.get("denomination", "100 卢纳币")
    specimen = _coerce_bool(args.get("specimen", "true"))
    bg_dir = args.get("bg_dir", "./backgrounds")
    background_prompt = args.get("background_prompt", "")
    border_inset_mm = _coerce_float(args.get("border_inset_mm", "0.5"), 0.5)
    border_thickness_mm = _coerce_float(args.get("border_thickness_mm", "3"), 3.0)
    enable_qr_border = _coerce_bool(args.get("enable_qr_border", "true"))
    enable_background = _coerce_bool(args.get("enable_background", "true"))
    background_filter = args.get("background_filter", "vectorize")
    background_margin = _coerce_int(args.get("background_margin", "60"), 60)
    background_segments = _coerce_int(args.get("background_segments", "1024"), 1024)
    mosaic_font = args.get("mosaic_font", "Daemon Full Working")
    mosaic_font_dir = args.get("mosaic_font_dir", "./fonts")
    mosaic_font_size_mm = _coerce_float(args.get("mosaic_font_size_mm", "1.1"), 1.1)
    mosaic_charset = args.get("mosaic_charset", "LUNAMINT")
    mosaic_invert = _coerce_bool(args.get("mosaic_invert", "false"))
    mosaic_snap_grid_px = _coerce_float(args.get("mosaic_snap_grid_px", "16"), 16.0)
    mosaic_opacity = _coerce_float(args.get("mosaic_opacity", "1.0"), 1.0)
    glyph_font = args.get("glyph_font", "Daemon Full Working")
    glyph_font_dir = args.get("glyph_font_dir", "./fonts")
    glyph_font_size_mm = _coerce_float(args.get("glyph_font_size_mm", "1.2"), 1.2)
    glyph_charset = args.get("glyph_charset", "LUNAMINT")
    glyph_invert = _coerce_bool(args.get("glyph_invert", "false"))
    glyph_snap_grid_px = _coerce_float(args.get("glyph_snap_grid_px", "16"), 16.0)
    glyph_opacity = _coerce_float(args.get("glyph_opacity", "0.9"), 0.9)
    glyph_fill_dark = args.get("glyph_fill_dark", "#111111")
    glyph_fill_light = args.get("glyph_fill_light", "#f7f2eb")
    glyph_stroke_dark = args.get("glyph_stroke_dark", "#0b0b0b")
    glyph_stroke_light = args.get("glyph_stroke_light", "#999999")
    glyph_stroke_width_mm = _coerce_float(args.get("glyph_stroke_width_mm", "0.12"), 0.12)
    glyph_inset_scale = _coerce_float(args.get("glyph_inset_scale", "0.8"), 0.8)
    glyph_outset_scale = _coerce_float(args.get("glyph_outset_scale", "1.1"), 1.1)
    glyph_threshold = _coerce_int(args.get("glyph_threshold", "140"), 140)
    glyph_colorize = _coerce_bool(args.get("glyph_colorize", "false"))
    glyph_cell_padding_mm = _coerce_float(args.get("glyph_cell_padding_mm", "0"), 0.0)
    enable_microgrid = _coerce_bool(args.get("enable_microgrid", "true"))
    enable_decorative_border = _coerce_bool(args.get("enable_decorative_border", "true"))
    enable_center_seal = _coerce_bool(args.get("enable_center_seal", "true"))
    enable_center_text = _coerce_bool(args.get("enable_center_text", "true"))
    enable_corner_decorations = _coerce_bool(args.get("enable_corner_decorations", "true"))
    enable_corner_denoms = _coerce_bool(args.get("enable_corner_denoms", "true"))
    enable_microprint = _coerce_bool(args.get("enable_microprint", "true"))
    microprint_repetitions = _coerce_int(args.get("microprint_repetitions", "16"), 16)
    microprint_text = args.get("microprint_text") or None
    center_radius_scale = _coerce_float(args.get("center_radius_scale", "0.32"), 0.32)
    small_radius_scale = _coerce_float(args.get("small_radius_scale", "0.25"), 0.25)
    text_seal_scale = _coerce_float(args.get("text_seal_scale", "0.65"), 0.65)
    secondary_ring_scale = _coerce_float(args.get("secondary_ring_scale", "0.88"), 0.88)
    center_seal_scale = _coerce_float(args.get("center_seal_scale", "1.2"), 1.2)
    title_font = args.get("title_font", "FengGuangMingRui")
    subtitle_font = args.get("subtitle_font", "FengGuangMingRui")
    corner_font = args.get("corner_font", "Daemon Full Working")
    seal_chinese_font = args.get("seal_chinese_font", "FengGuangMingRui")
    seal_english_font = args.get("seal_english_font", "Daemon Full Working")
    showcase_widgets = _coerce_bool(args.get("showcase_widgets", "false"))
    ascii_stamp_prompt = args.get("ascii_stamp_prompt") or None
    showcase_labels = _coerce_bool(args.get("showcase_labels", "false"))
    label_font = args.get("label_font", "Daemon Full Working")
    label_size_mm = _coerce_float(args.get("label_size_mm", "2.6"), 2.6)
    qr_url = args.get("qr_url") or None
    require_signed_qr = _coerce_bool(args.get("require_signed_qr", "false"))
    sm2_private_key = args.get("sm2_private_key") or None
    sm2_public_key = args.get("sm2_public_key") or None
    verify_base_url = args.get("verify_base_url") or None
    issuer_id = args.get("issuer_id") or None
    validity_days = _coerce_int(args.get("validity_days", "365"), 365)
    pow_difficulty = _coerce_int(args.get("pow_difficulty", "12"), 12)
    sm4_key = args.get("sm4_key") or None
    sm4_enable = _coerce_bool(args.get("sm4_enable", "false"))
    qr_stamp_width = _coerce_int(args.get("qr_stamp_width", "60"), 60)
    qr_stamp_height = _coerce_int(args.get("qr_stamp_height", "60"), 60)
    qr_rows = _coerce_int(args.get("qr_rows", "6"), 6)
    qr_side = args.get("qr_side", "both")
    qr_stamp = _coerce_bool(args.get("qr_stamp", "true"))
    aztec = _coerce_bool(args.get("aztec", "true"))
    aztec_scale = _coerce_float(args.get("aztec_scale", "3"), 3.0)
    aztec_border = _coerce_float(args.get("aztec_border", "12"), 12.0)
    aztec_rotation_base = _coerce_float(args.get("aztec_rotation_base", "0"), 0.0)
    aztec_offset_x = _coerce_float(args.get("aztec_offset_x", "360"), 360.0)
    aztec_offset_y = _coerce_float(args.get("aztec_offset_y", "0"), 0.0)
    aztec_border_opacity = _coerce_float(args.get("aztec_border_opacity", "0.5"), 0.5)

    return {
        "seed_text": seed_text,
        "input_image_path": input_image_path,
        "width_mm": width_mm,
        "height_mm": height_mm,
        "title": title,
        "subtitle": subtitle,
        "serial_id": serial_id,
        "timestamp": timestamp,
        "denomination": denomination,
        "specimen": specimen,
        "bg_dir": bg_dir,
        "background_prompt": background_prompt,
        "border_inset_mm": border_inset_mm,
        "border_thickness_mm": border_thickness_mm,
        "enable_qr_border": enable_qr_border,
        "enable_background": enable_background,
        "background_filter": background_filter,
        "background_margin": background_margin,
        "background_segments": background_segments,
        "mosaic_font": mosaic_font,
        "mosaic_font_dir": mosaic_font_dir,
        "mosaic_font_size_mm": mosaic_font_size_mm,
        "mosaic_charset": mosaic_charset,
        "mosaic_invert": mosaic_invert,
        "mosaic_snap_grid_px": mosaic_snap_grid_px,
        "mosaic_opacity": mosaic_opacity,
        "glyph_font": glyph_font,
        "glyph_font_dir": glyph_font_dir,
        "glyph_font_size_mm": glyph_font_size_mm,
        "glyph_charset": glyph_charset,
        "glyph_invert": glyph_invert,
        "glyph_snap_grid_px": glyph_snap_grid_px,
        "glyph_opacity": glyph_opacity,
        "glyph_fill_dark": glyph_fill_dark,
        "glyph_fill_light": glyph_fill_light,
        "glyph_stroke_dark": glyph_stroke_dark,
        "glyph_stroke_light": glyph_stroke_light,
        "glyph_stroke_width_mm": glyph_stroke_width_mm,
        "glyph_inset_scale": glyph_inset_scale,
        "glyph_outset_scale": glyph_outset_scale,
        "glyph_threshold": glyph_threshold,
        "glyph_colorize": glyph_colorize,
        "glyph_cell_padding_mm": glyph_cell_padding_mm,
        "enable_microgrid": enable_microgrid,
        "enable_decorative_border": enable_decorative_border,
        "enable_center_seal": enable_center_seal,
        "enable_center_text": enable_center_text,
        "enable_corner_decorations": enable_corner_decorations,
        "enable_corner_denoms": enable_corner_denoms,
        "enable_microprint": enable_microprint,
        "microprint_repetitions": microprint_repetitions,
        "microprint_text": microprint_text,
        "center_radius_scale": center_radius_scale,
        "small_radius_scale": small_radius_scale,
        "text_seal_scale": text_seal_scale,
        "secondary_ring_scale": secondary_ring_scale,
        "center_seal_scale": center_seal_scale,
        "title_font": title_font,
        "subtitle_font": subtitle_font,
        "corner_font": corner_font,
        "seal_chinese_font": seal_chinese_font,
        "seal_english_font": seal_english_font,
        "showcase_widgets": showcase_widgets,
        "ascii_stamp_prompt": ascii_stamp_prompt,
        "showcase_labels": showcase_labels,
        "label_font": label_font,
        "label_size_mm": label_size_mm,
        "qr_url": qr_url,
        "require_signed_qr": require_signed_qr,
        "sm2_private_key": sm2_private_key,
        "sm2_public_key": sm2_public_key,
        "verify_base_url": verify_base_url,
        "issuer_id": issuer_id,
        "validity_days": validity_days,
        "pow_difficulty": pow_difficulty,
        "sm4_key": sm4_key,
        "sm4_enable": sm4_enable,
        "qr_stamp_width": qr_stamp_width,
        "qr_stamp_height": qr_stamp_height,
        "qr_rows": qr_rows,
        "qr_side": qr_side,
        "qr_stamp": qr_stamp,
        "aztec": aztec,
        "aztec_scale": aztec_scale,
        "aztec_border": aztec_border,
        "aztec_rotation_base": aztec_rotation_base,
        "aztec_offset_x": aztec_offset_x,
        "aztec_offset_y": aztec_offset_y,
        "aztec_border_opacity": aztec_border_opacity,
    }


def _autoclose_quote(line: str) -> str:
    double_count = line.count('"')
    single_count = line.count("'")
    if double_count % 2 == 1:
        return line + '"'
    if single_count % 2 == 1:
        return line + "'"
    return line


def _split_script_line(line: str) -> List[str]:
    try:
        return shlex.split(line, posix=False)
    except ValueError as exc:
        fixed = _autoclose_quote(line)
        if fixed != line:
            try:
                return shlex.split(fixed, posix=False)
            except ValueError:
                pass
        raise ValueError(f"Invalid quoting in line: {line}") from exc


def parse_script(source: str) -> ScriptProgram:
    program = ScriptProgram()
    logical_lines: List[str] = []
    buffer = ""
    last_op: DrawOp | None = None

    for raw_line in source.splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("{#") or stripped.startswith("{%"):
            continue
        if stripped.endswith("\\"):
            buffer += stripped[:-1].rstrip() + " "
            continue
        buffer += stripped
        logical_lines.append(buffer)
        buffer = ""

    if buffer:
        logical_lines.append(buffer)
    for line in logical_lines:
        parts = _split_script_line(line)
        if not parts:
            continue
        cmd = parts[0].lower()
        args = parts[1:]
        if cmd == "size":
            program.state.width = int(float(args[0]))
            program.state.height = int(float(args[1]))
        elif cmd == "background":
            program.state.background = args[0]
        elif cmd == "rect":
            x, y, w, h = map(float, args[:4])
            fill = args[4] if len(args) > 4 else "#000"
            last_op = DrawOp("rect", {"x": x, "y": y, "w": w, "h": h, "fill": fill})
            program.ops.append(last_op)
        elif cmd == "circle":
            x, y, r = map(float, args[:3])
            fill = args[3] if len(args) > 3 else "#000"
            last_op = DrawOp("circle", {"x": x, "y": y, "r": r, "fill": fill})
            program.ops.append(last_op)
        elif cmd == "text_dial":
            values = _parse_kv_args(args)
            last_op = DrawOp("text_dial", values)
            program.ops.append(last_op)
        elif cmd == "text_grid":
            values = _parse_kv_args(args)
            last_op = DrawOp("text_grid", values)
            program.ops.append(last_op)
        elif cmd == "letter_border":
            values = _parse_kv_args(args)
            last_op = DrawOp("letter_border", values)
            program.ops.append(last_op)
        elif cmd == "hash_mandala":
            values = _parse_kv_args(args)
            last_op = DrawOp("hash_mandala", values)
            program.ops.append(last_op)
        elif cmd == "hash_mandala_rect":
            values = _parse_kv_args(args)
            last_op = DrawOp("hash_mandala_rect", values)
            program.ops.append(last_op)
        elif cmd == "line":
            x1, y1, x2, y2 = map(float, args[:4])
            stroke = args[4] if len(args) > 4 else "#000"
            width = float(args[5]) if len(args) > 5 else 1.0
            last_op = DrawOp("line", {"x1": x1, "y1": y1, "x2": x2, "y2": y2, "stroke": stroke, "width": width})
            program.ops.append(last_op)
        elif cmd == "midi_dial":
            values = _parse_kv_args(args)
            last_op = DrawOp("midi_dial", values)
            program.ops.append(last_op)
        elif cmd == "text":
            x, y = map(float, args[:2])
            size = float(args[2])
            fill = args[3]
            content = " ".join(args[4:])
            last_op = DrawOp("text", {"x": x, "y": y, "size": size, "fill": fill, "text": content})
            program.ops.append(last_op)
        elif cmd == "qr_code":
            values = _parse_kv_args(args)
            last_op = DrawOp("qr_code", values)
            program.ops.append(last_op)
        elif cmd in {
            "back_vectorized_background",
            "back_corner_denoms",
            "back_corner_decorations",
            "back_holographic_seals",
            "back_center_text",
            "back_circular_qr",
            "back_qr_border",
            "back_verification_text",
            "back_security_background",
            "chinese_microprint",
            "rainbow_microseal",
            "back_aztec",
        }:
            values = _parse_kv_args(args)
            last_op = DrawOp(cmd, values)
            program.ops.append(last_op)
        elif cmd == "sd_background":
            values = _parse_kv_args(args)
            last_op = DrawOp("sd_background", values)
            program.ops.append(last_op)
        elif cmd == "front_banknote":
            values = _parse_kv_args(args)
            last_op = DrawOp("front_banknote", values)
            program.ops.append(last_op)
        elif cmd == "back_banknote":
            values = _parse_kv_args(args)
            last_op = DrawOp("back_banknote", values)
            program.ops.append(last_op)
        else:
            if "=" in cmd and last_op and last_op.op in {"front_banknote", "back_banknote"}:
                values = _parse_kv_args([cmd] + args)
                last_op.args.update(values)
                continue
            raise ValueError(f"Unknown command: {cmd}")
    return program


def _normalize_back_params(args: Dict[str, str]) -> Dict[str, object]:
    seed_text = args.get("seed_text", "LunaMint")
    denomination = args.get("denomination", "100 卢纳币")
    title = args.get("title", "灵国国库")
    phrase = args.get("phrase", "灵之意志，天下共识")
    width_mm = _coerce_float(args.get("width_mm", "160"), 160.0)
    height_mm = _coerce_float(args.get("height_mm", "60"), 60.0)
    serial_id = args.get("serial_id") or None
    timestamp_ms = _coerce_int(args.get("timestamp_ms", "0"), 0) or None

    return {
        "seed_text": seed_text,
        "denomination": denomination,
        "title": title,
        "phrase": phrase,
        "width_mm": width_mm,
        "height_mm": height_mm,
        "serial_id": serial_id,
        "timestamp_ms": timestamp_ms,
    }


def _image_mime_type(path: Path) -> str:
    suffix = path.suffix.lower().lstrip(".")
    if suffix in {"jpg", "jpeg"}:
        return "image/jpeg"
    if suffix in {"webp"}:
        return "image/webp"
    return "image/png"


def _add_image_background(dwg: svgwrite.Drawing, W: int, H: int, image_path: Path) -> None:
    data = image_path.read_bytes()
    mime = _image_mime_type(image_path)
    b64 = base64.b64encode(data).decode("ascii")
    href = f"data:{mime};base64,{b64}"
    dwg.add(dwg.image(href=href, insert=(0, 0), size=(W, H)))


def _parse_color_list(value: str | None) -> list[str]:
    if not value:
        return []
    cleaned: list[str] = []
    for v in value.split(","):
        item = v.strip().strip('"').strip("'")
        if item:
            cleaned.append(item)
    return cleaned


def _clean_path(value: str | None, fallback: str = "./backgrounds") -> str:
    if value is None:
        return fallback
    cleaned = str(value).strip().strip('"').strip("'")
    return cleaned or fallback


def _render_ops(dwg: svgwrite.Drawing, ops: List[DrawOp], canvas_w: int, canvas_h: int) -> None:
    for op in ops:
        if op.op == "rect":
            dwg.add(dwg.rect(insert=(op.args["x"], op.args["y"]), size=(op.args["w"], op.args["h"]), fill=op.args["fill"]))
        elif op.op == "circle":
            dwg.add(dwg.circle(center=(op.args["x"], op.args["y"]), r=op.args["r"], fill=op.args["fill"]))
        elif op.op == "polygon":
            # polygon expects 'points' as a list of (x, y) tuples, and 'fill' (optionally 'stroke', 'stroke_width')
            points = op.args["points"]
            fill = op.args.get("fill", "#000")
            stroke = op.args.get("stroke", None)
            stroke_width = op.args.get("stroke_width", None)
            polygon_kwargs = {"fill": fill}
            if stroke:
                polygon_kwargs["stroke"] = stroke
            if stroke_width:
                polygon_kwargs["stroke_width"] = stroke_width
            dwg.add(dwg.polygon(points=points, **polygon_kwargs))
        elif op.op == "line":
            dwg.add(dwg.line(start=(op.args["x1"], op.args["y1"]), end=(op.args["x2"], op.args["y2"]), stroke=op.args["stroke"], stroke_width=op.args["width"]))
        elif op.op == "text":
            dwg.add(dwg.text(op.args["text"], insert=(op.args["x"], op.args["y"]), fill=op.args["fill"], font_size=op.args["size"]))
        elif op.op == "qr_code":
            args = op.args
            data = str(args.get("data", args.get("text", "")))
            if not data:
                continue
            x = float(args.get("x", 0))
            y = float(args.get("y", 0))
            size = float(args.get("size", 120))
            border = int(float(args.get("border", 2)))
            error_level = str(args.get("error", "M")).upper()
            invert = str(args.get("invert", "false")).lower() == "true"
            foreground = str(args.get("foreground", "#000000"))
            background = str(args.get("background", "#ffffff"))

            try:
                import qrcode
            except Exception:
                raise RuntimeError("qrcode is required for qr_code. Install it with pip install qrcode.")

            error_map = {
                "L": qrcode.constants.ERROR_CORRECT_L,
                "M": qrcode.constants.ERROR_CORRECT_M,
                "Q": qrcode.constants.ERROR_CORRECT_Q,
                "H": qrcode.constants.ERROR_CORRECT_H,
            }
            qr = qrcode.QRCode(
                version=None,
                error_correction=error_map.get(error_level, qrcode.constants.ERROR_CORRECT_M),
                box_size=1,
                border=border,
            )
            qr.add_data(data)
            qr.make(fit=True)
            matrix = qr.get_matrix()
            cells = len(matrix)
            if cells <= 0:
                continue
            cell_size = size / cells

            fg = background if invert else foreground
            bg = foreground if invert else background

            if bg and bg.lower() != "none":
                dwg.add(dwg.rect(insert=(x, y), size=(size, size), fill=bg))

            for r in range(cells):
                for c in range(cells):
                    if not matrix[r][c]:
                        continue
                    dwg.add(
                        dwg.rect(
                            insert=(x + c * cell_size, y + r * cell_size),
                            size=(cell_size, cell_size),
                            fill=fg,
                        )
                    )
        elif op.op == "back_vectorized_background":
            args = op.args
            seed_text = str(args.get("seed_text", ""))
            bg_dir = _clean_path(args.get("bg_dir", "./backgrounds"))
            margin = int(float(args.get("margin", 60)))
            n_segments = int(float(args.get("n_segments", args.get("background_segments", 1024))))
            background_prompt = str(args.get("background_prompt", ""))
            denomination = args.get("denomination")
            add_back_vectorized_background(
                dwg,
                W=canvas_w,
                H=canvas_h,
                seed_text=seed_text,
                bg_dir=bg_dir,
                margin=margin,
                n_segments=n_segments,
                background_prompt=background_prompt,
                denomination=denomination,
            )
        elif op.op == "back_corner_denoms":
            args = op.args
            denom = args.get("denomination", "100")
            add_corner_denoms(dwg, canvas_w, canvas_h, str(denom))
        elif op.op == "back_corner_decorations":
            args = op.args
            denom = args.get("denomination", "100")
            timestamp = args.get("timestamp_ms") or generate_timestamp_ms_precise()
            serial_id = args.get("serial_id", "")
            size = int(float(args.get("size", 100)))
            padding = int(float(args.get("padding", 75)))
            stroke_width = float(args.get("stroke_width", 1))
            add_functional_corner_decorations(
                dwg,
                canvas_w,
                canvas_h,
                denom,
                timestamp,
                serial_id,
                size=size,
                padding=padding,
                stroke_width=stroke_width,
            )
        elif op.op == "back_holographic_seals":
            args = op.args
            serial_id = str(args.get("serial_id", ""))
            denom = args.get("denomination", 100)
            radius = int(float(args.get("radius", min(canvas_w, canvas_h) * 0.25)))
            add_holographic_seals(dwg, canvas_w, canvas_h, serial_id=serial_id, denomination=denom, radius=radius)
        elif op.op == "back_center_text":
            args = op.args
            title = str(args.get("title", "灵国国库"))
            phrase = str(args.get("phrase", "灵之意志，天下共识"))
            denom = args.get("denomination", 100)
            denom_int = denom_to_int(denom)
            denom_exp = int(round(math.log10(max(1, denom_int)))) if denom_int > 0 else 0
            denom_color = str(args.get("denom_color", denomination_to_color(denom_exp)))
            add_center_text(dwg, canvas_w, canvas_h, title, phrase, denom_color)
        elif op.op == "back_circular_qr":
            args = op.args
            text = str(args.get("data", args.get("text", "")))
            if not text:
                continue
            cx = float(args.get("cx", canvas_w / 2))
            cy = float(args.get("cy", canvas_h / 2))
            inner_radius = int(float(args.get("inner_radius", 0)))
            outer_radius = int(float(args.get("outer_radius", min(canvas_w, canvas_h) * 0.36)))
            segments = int(float(args.get("segments", 4)))
            opacity = float(args.get("opacity", 0.5))
            colors = _parse_color_list(str(args.get("colors", "")))
            add_circular_qr_continuous(
                dwg,
                cx,
                cy,
                text=text,
                inner_radius=inner_radius,
                outer_radius=outer_radius,
                segments=segments,
                colors=colors or None,
                opacity=opacity,
            )
        elif op.op == "back_qr_border":
            args = op.args
            seed = str(args.get("seed", args.get("seed_text", "")))
            serial_id = args.get("serial_id")
            timestamp_ms = args.get("timestamp_ms")
            add_qr_like_border(dwg, seed, canvas_w, canvas_h, serial_id=serial_id, timestamp_ms=timestamp_ms)
        elif op.op == "back_verification_text":
            args = op.args
            serial_id = args.get("serial_id", "")
            timestamp_ms = args.get("timestamp_ms") or generate_timestamp_ms_precise()
            add_verification_text(dwg, canvas_w, canvas_h, serial_id, timestamp_ms)
        elif op.op == "back_security_background":
            args = op.args
            denom = denom_to_int(args.get("denomination", 100))
            serial_id = args.get("serial_id")
            seed_text = args.get("seed_text", args.get("seed", ""))
            timestamp_ms = args.get("timestamp_ms")
            sm2_private_key = args.get("sm2_private_key")
            sm2_public_key = args.get("sm2_public_key")
            margin = int(float(args.get("margin", 60)))
            base_triangle_size = int(float(args.get("base_triangle_size", 16)))
            hierarchy_levels = int(float(args.get("hierarchy_levels", 2)))
            add_security_background(
                dwg,
                canvas_w,
                canvas_h,
                denomination=denom,
                serial_id=serial_id,
                seed_text=str(seed_text) if seed_text is not None else None,
                timestamp_ms=int(timestamp_ms) if timestamp_ms is not None else None,
                sm2_private_key=str(sm2_private_key) if sm2_private_key else None,
                sm2_public_key=str(sm2_public_key) if sm2_public_key else None,
                margin=margin,
                base_triangle_size=base_triangle_size,
                hierarchy_levels=hierarchy_levels,
            )
        elif op.op == "chinese_microprint":
            args = op.args
            cx = int(float(args.get("cx", canvas_w / 2)))
            cy = int(float(args.get("cy", canvas_h / 2)))
            radius = int(float(args.get("radius", min(canvas_w, canvas_h) * 0.08)))
            text = str(args.get("text", "壹佰 卢纳币"))
            repetitions = int(float(args.get("repetitions", 1)))
            font_family = str(args.get("font_family", "FengGuangMingRui"))
            font_size = int(float(args.get("font_size", 8)))
            add_chinese_microprint(
                dwg,
                cx=cx,
                cy=cy,
                radius=radius,
                text=text,
                repetitions=repetitions,
                font_family=font_family,
                font_size=font_size,
            )
        elif op.op == "rainbow_microseal":
            args = op.args
            cx = int(float(args.get("cx", canvas_w / 2)))
            cy = int(float(args.get("cy", canvas_h / 2)))
            radius = int(float(args.get("radius", min(canvas_w, canvas_h) * 0.08)))
            symbol = args.get("symbol")
            repetitions = int(float(args.get("repetitions", 64)))
            font_family = str(args.get("font_family", "Daemon Full Working"))
            font_size = int(float(args.get("font_size", 8)))
            add_rainbow_microseal(
                dwg,
                cx=cx,
                cy=cy,
                radius=radius,
                symbol=symbol,
                repetitions=repetitions,
                font_family=font_family,
                font_size=font_size,
            )
        elif op.op == "back_aztec":
            args = op.args
            url = str(args.get("url", ""))
            if not url:
                continue
            cx = float(args.get("cx", canvas_w / 2))
            cy = float(args.get("cy", canvas_h / 2))
            scale = int(float(args.get("scale", 3)))
            rotation = float(args.get("rotation", 0))
            border = int(float(args.get("border", 12)))
            border_opacity = float(args.get("border_opacity", 0.5))
            denom = denom_to_int(args.get("denomination", 100))
            denom_exp = int(round(math.log10(max(1, denom)))) if denom > 0 else 0
            matrix = safe_make_matrix(url)
            if matrix is None:
                continue
            add_colored_aztec_to_canvas(
                dwg,
                cx=cx,
                cy=cy,
                matrix=matrix,
                denom_exponent=denom_exp,
                scale=scale,
                border=border,
                rotation=rotation,
                border_opacity=border_opacity,
            )
        elif op.op == "sd_background":
            args = op.args
            filter_name = str(args.get("filter", args.get("background_filter", "vectorize"))).strip().lower()
            seed_text = str(args.get("seed_text", args.get("seed", "")))
            bg_dir = _clean_path(args.get("bg_dir", "./backgrounds"))
            margin = int(float(args.get("margin", args.get("background_margin", 60))))
            background_prompt = str(args.get("background_prompt", ""))
            background_segments = int(float(args.get("background_segments", 1024)))

            if filter_name in {"none", "image", "raw"}:
                background_path = generate_sd_background(
                    prompt=background_prompt,
                    width=canvas_w - 2 * margin,
                    height=canvas_h - 2 * margin,
                    save_path=bg_dir,
                    seed_text=seed_text,
                )
                if background_path:
                    _add_image_background(dwg, canvas_w, canvas_h, Path(background_path))
            elif filter_name in {"letter_mosaic", "letter-mosaic", "mosaic", "letters"}:
                add_letter_mosaic_background(
                    dwg=dwg,
                    W=canvas_w,
                    H=canvas_h,
                    seed_text=seed_text,
                    bg_dir=bg_dir,
                    margin=margin,
                    background_prompt=background_prompt,
                )
            elif filter_name in {"glyph_grid", "glyph-grid", "glyphs", "grid"}:
                glyph_options = GlyphGridOptions(
                    font_name=str(args.get("glyph_font", "Daemon Full Working")),
                    font_dir=str(args.get("glyph_font_dir", "./fonts")),
                    font_size_mm=float(args.get("glyph_font_size_mm", 1.2)),
                    charset=str(args.get("glyph_charset", "LUNAMINT")),
                    invert=str(args.get("glyph_invert", "false")).lower() == "true",
                    snap_grid_px=float(args.get("glyph_snap_grid_px", 16)),
                    opacity=float(args.get("glyph_opacity", 0.9)),
                    fill_dark=str(args.get("glyph_fill_dark", "#111111")),
                    fill_light=str(args.get("glyph_fill_light", "#f7f2eb")),
                    stroke_dark=str(args.get("glyph_stroke_dark", "#0b0b0b")),
                    stroke_light=str(args.get("glyph_stroke_light", "#999999")),
                    stroke_width_mm=float(args.get("glyph_stroke_width_mm", 0.12)),
                    inset_scale=float(args.get("glyph_inset_scale", 0.8)),
                    outset_scale=float(args.get("glyph_outset_scale", 1.1)),
                    threshold=int(float(args.get("glyph_threshold", 140))),
                    colorize=str(args.get("glyph_colorize", "false")).lower() == "true",
                    cell_padding_mm=float(args.get("glyph_cell_padding_mm", 0.0)),
                    dpi=float(args.get("glyph_dpi", 300.0)),
                )
                add_glyph_grid_background(
                    dwg=dwg,
                    W=canvas_w,
                    H=canvas_h,
                    seed_text=seed_text,
                    bg_dir=bg_dir,
                    margin=margin,
                    background_prompt=background_prompt,
                    config=GlyphGridConfig(options=glyph_options),
                )
            elif filter_name in {"triangle_mosaic", "triangle-mosaic", "triangles"}:
                add_triangle_mosaic_background(
                    dwg=dwg,
                    W=canvas_w,
                    H=canvas_h,
                    seed_text=seed_text,
                    bg_dir=bg_dir,
                    margin=margin,
                    background_prompt=background_prompt,
                )
            else:
                add_vectorized_background(
                    dwg=dwg,
                    W=canvas_w,
                    H=canvas_h,
                    seed_text=seed_text,
                    bg_dir=bg_dir,
                    margin=margin,
                    n_segments=background_segments,
                    background_prompt=background_prompt,
                )
        elif op.op == "text_dial":
            args = op.args
            add_polar_text_dial_mm(
                dwg,
                cx_mm=float(args.get("cx_mm", 80)),
                cy_mm=float(args.get("cy_mm", 45)),
                radius_mm=float(args.get("radius_mm", 30)),
                text=str(args.get("text", "LUNAMINT")),
                rings=int(float(args.get("rings", 6))),
                font_name=str(args.get("font", "Daemon Full Working")),
                font_dir=str(args.get("font_dir", "./fonts")),
                font_size_mm=float(args.get("font_size_mm", 1.2)),
                spacing_mm=float(args.get("spacing_mm", 0.2)),
                ring_gap_mm=float(args.get("ring_gap_mm", 0.6)),
                rotation_seed=str(args.get("rotation_seed", "")),
                snap_grid_px=float(args.get("snap_grid_px", 16)),
                clip_radius_mm=float(args.get("clip_radius_mm", 0)) or None,
                case=str(args.get("case", "upper")).lower(),
                inner_radius_mm=float(args.get("inner_radius_mm", 0)) or None,
            )
        elif op.op == "text_grid":
            args = op.args
            add_text_grid_cipher_mm(
                dwg,
                x_mm=float(args.get("x_mm", 10)),
                y_mm=float(args.get("y_mm", 10)),
                width_mm=float(args.get("width_mm", 60)),
                height_mm=float(args.get("height_mm", 60)),
                text=str(args.get("text", "LUNAMINT")),
                font_name=str(args.get("font", "Daemon Full Working")),
                font_dir=str(args.get("font_dir", "./fonts")),
                font_size_mm=float(args.get("font_size_mm", 1.2)),
                spacing_mm=float(args.get("spacing_mm", 0.0)),
                snap_grid_px=float(args.get("snap_grid_px", 16)),
            )
        elif op.op == "letter_border":
            args = op.args
            add_letter_border_mask_mm(
                dwg,
                x_mm=float(args.get("x_mm", 0)),
                y_mm=float(args.get("y_mm", 0)),
                width_mm=float(args.get("width_mm", 160)),
                height_mm=float(args.get("height_mm", 60)),
                border_thickness_mm=float(args.get("border_thickness_mm", 3.0)),
                text=str(args.get("text", "LUNAMINT")),
                font_name=str(args.get("font", "Daemon Full Working")),
                font_dir=str(args.get("font_dir", "./fonts")),
                font_size_mm=float(args.get("font_size_mm", 1.2)),
                spacing_mm=float(args.get("spacing_mm", 0.2)),
                fill_color=str(args.get("fill_color", "#111111")),
                opacity=float(args.get("opacity", 1.0)),
                case=str(args.get("case", "upper")).lower(),
                base_fill=str(args.get("base_fill", "#ffffff")) if args.get("base_fill") is not None else None,
                pattern=str(args.get("pattern", "stripes")),
                pattern_color=str(args.get("pattern_color", "#222222")),
                pattern_opacity=float(args.get("pattern_opacity", 0.35)),
            )
        elif op.op == "hash_mandala":
            args = op.args
            add_hash_mandala_mm(
                dwg,
                cx_mm=float(args.get("cx_mm", 80)),
                cy_mm=float(args.get("cy_mm", 30)),
                radius_mm=float(args.get("radius_mm", 22)),
                data_text=str(args.get("data", args.get("data_text", "LUNAMINT"))),
                data_path=str(args.get("data_path")) if args.get("data_path") else None,
                data_type=str(args.get("data_type")) if args.get("data_type") else None,
                options=HashMandalaOptions(
                    font_name=str(args.get("font", "Daemon Full Working")),
                    font_dir=str(args.get("font_dir", "./fonts")),
                    font_size_mm=float(args.get("font_size_mm", 1.2)),
                    charset=str(args.get("charset", "LUNAMINT")),
                    rings=int(float(args.get("rings", 7))),
                    sectors=int(float(args.get("sectors", 12))),
                    opacity=float(args.get("opacity", 0.85)),
                    stroke_width_mm=float(args.get("stroke_width_mm", 0.08)),
                    colorize=str(args.get("colorize", "true")).lower() == "true",
                    grid_density=int(float(args.get("grid_density", 10))),
                    inset_scale=float(args.get("inset_scale", 0.85)),
                    outset_scale=float(args.get("outset_scale", 1.15)),
                    snap_grid_px=float(args.get("snap_grid_px", 8.0)),
                    ring_rows=int(float(args.get("ring_rows", 3))),
                    sector_density=float(args.get("sector_density", 1.5)),
                    fill_empty=str(args.get("fill_empty", "true")).lower() == "true",
                    background_color=str(args.get("background_color", "#0f1114")),
                    background_opacity=float(args.get("background_opacity", 0.25)),
                    border_color=str(args.get("border_color", "#111111")),
                    border_width_mm=float(args.get("border_width_mm", 0.12)),
                    radial_lines=int(float(args.get("radial_lines", 24))),
                    tick_major=int(float(args.get("tick_major", 16))),
                    tick_minor=int(float(args.get("tick_minor", 32))),
                    core_rings=int(float(args.get("core_rings", 4))),
                    core_radials=int(float(args.get("core_radials", 24))),
                    core_letter_every=int(float(args.get("core_letter_every", 2))),
                    cardinal_markers=str(args.get("cardinal_markers", "true")).lower() == "true",
                    stroke_only=str(args.get("stroke_only", "false")).lower() == "true",
                    stroke_color=str(args.get("stroke_color", "#1a1a1a")),
                    stroke_color_secondary=str(args.get("stroke_color_secondary", "#1a1a1a")),
                    flat_glyphs=str(args.get("flat_glyphs", "false")).lower() == "true",
                    glyph_fill=str(args.get("glyph_fill", "#e6e6e6")),
                    glyph_stroke=str(args.get("glyph_stroke", "#1a1a1a")),
                    glyph_stroke_width_scale=float(args.get("glyph_stroke_width_scale", 1.0)),
                    min_cols_per_sector=int(float(args.get("min_cols_per_sector", 3))),
                    taper_outer_strength=float(args.get("taper_outer_strength", 0.35)),
                    taper_radial_strength=float(args.get("taper_radial_strength", 0.55)),
                    ring_label_every=int(float(args.get("ring_label_every", 0))),
                    ring_label_alternate=str(args.get("ring_label_alternate", "true")).lower() == "true",
                    ring_label_text=str(args.get("ring_label_text", "123456789")),
                    ring_label_size_scale=float(args.get("ring_label_size_scale", 0.9)),
                    sector_padding_deg=float(args.get("sector_padding_deg", 0.0)),
                    ring_padding_mm=float(args.get("ring_padding_mm", 0.0)),
                    sector_outline=str(args.get("sector_outline", "false")).lower() == "true",
                    sector_outline_color=str(args.get("sector_outline_color", "#1a1a1a")),
                    sector_outline_width_mm=float(args.get("sector_outline_width_mm", 0.08)),
                    ring_pattern_mode=str(args.get("ring_pattern_mode", "false")).lower() == "true",
                    sm2_row_variance=int(float(args.get("sm2_row_variance", 0))),
                    use_roygbiv=str(args.get("use_roygbiv", "true")).lower() == "true",
                    label_every=int(float(args.get("label_every", 4))),
                    label_radius_ratio=float(args.get("label_radius_ratio", 0.86)),
                    label_font_size_mm=float(args.get("label_font_size_mm", 1.0)),
                    label_stroke_width_mm=float(args.get("label_stroke_width_mm", 0.06)),
                    sector_boxes=str(args.get("sector_boxes", "true")).lower() == "true",
                    sector_box_size_mm=float(args.get("sector_box_size_mm", 1.4)),
                    center_digit=int(float(args.get("center_digit", 0))),
                    center_digit_size_mm=float(args.get("center_digit_size_mm", 6.0)),
                    center_digit_fill_background=str(args.get("center_digit_fill_background", "true")).lower() == "true",
                ),
            )
        elif op.op == "hash_mandala_rect":
            args = op.args
            add_hash_mandala_rect_mm(
                dwg,
                x_mm=float(args.get("x_mm", 10)),
                y_mm=float(args.get("y_mm", 10)),
                width_mm=float(args.get("width_mm", 60)),
                height_mm=float(args.get("height_mm", 60)),
                data_text=str(args.get("data", args.get("data_text", "LUNAMINT"))),
                data_path=str(args.get("data_path")) if args.get("data_path") else None,
                data_type=str(args.get("data_type")) if args.get("data_type") else None,
                options=HashMandalaOptions(
                    font_name=str(args.get("font", "Daemon Full Working")),
                    font_dir=str(args.get("font_dir", "./fonts")),
                    font_size_mm=float(args.get("font_size_mm", 1.2)),
                    charset=str(args.get("charset", "LUNAMINT")),
                    rings=int(float(args.get("rings", 7))),
                    sectors=int(float(args.get("sectors", 12))),
                    opacity=float(args.get("opacity", 0.85)),
                    stroke_width_mm=float(args.get("stroke_width_mm", 0.08)),
                    colorize=str(args.get("colorize", "true")).lower() == "true",
                    grid_density=int(float(args.get("grid_density", 10))),
                    inset_scale=float(args.get("inset_scale", 0.85)),
                    outset_scale=float(args.get("outset_scale", 1.15)),
                    snap_grid_px=float(args.get("snap_grid_px", 8.0)),
                    ring_rows=int(float(args.get("ring_rows", 3))),
                    sector_density=float(args.get("sector_density", 1.5)),
                    fill_empty=str(args.get("fill_empty", "true")).lower() == "true",
                    background_color=str(args.get("background_color", "#0f1114")),
                    background_opacity=float(args.get("background_opacity", 0.25)),
                    border_color=str(args.get("border_color", "#111111")),
                    border_width_mm=float(args.get("border_width_mm", 0.12)),
                    radial_lines=int(float(args.get("radial_lines", 24))),
                    tick_major=int(float(args.get("tick_major", 16))),
                    tick_minor=int(float(args.get("tick_minor", 32))),
                    core_rings=int(float(args.get("core_rings", 4))),
                    core_radials=int(float(args.get("core_radials", 24))),
                    core_letter_every=int(float(args.get("core_letter_every", 2))),
                    cardinal_markers=str(args.get("cardinal_markers", "true")).lower() == "true",
                    stroke_only=str(args.get("stroke_only", "false")).lower() == "true",
                    stroke_color=str(args.get("stroke_color", "#1a1a1a")),
                    stroke_color_secondary=str(args.get("stroke_color_secondary", "#1a1a1a")),
                    flat_glyphs=str(args.get("flat_glyphs", "false")).lower() == "true",
                    glyph_fill=str(args.get("glyph_fill", "#e6e6e6")),
                    glyph_stroke=str(args.get("glyph_stroke", "#1a1a1a")),
                    glyph_stroke_width_scale=float(args.get("glyph_stroke_width_scale", 1.0)),
                    min_cols_per_sector=int(float(args.get("min_cols_per_sector", 3))),
                    taper_outer_strength=float(args.get("taper_outer_strength", 0.35)),
                    taper_radial_strength=float(args.get("taper_radial_strength", 0.55)),
                    ring_label_every=int(float(args.get("ring_label_every", 0))),
                    ring_label_alternate=str(args.get("ring_label_alternate", "true")).lower() == "true",
                    ring_label_text=str(args.get("ring_label_text", "123456789")),
                    ring_label_size_scale=float(args.get("ring_label_size_scale", 0.9)),
                    sector_padding_deg=float(args.get("sector_padding_deg", 0.0)),
                    ring_padding_mm=float(args.get("ring_padding_mm", 0.0)),
                    sector_outline=str(args.get("sector_outline", "false")).lower() == "true",
                    sector_outline_color=str(args.get("sector_outline_color", "#1a1a1a")),
                    sector_outline_width_mm=float(args.get("sector_outline_width_mm", 0.08)),
                    ring_pattern_mode=str(args.get("ring_pattern_mode", "false")).lower() == "true",
                    sm2_row_variance=int(float(args.get("sm2_row_variance", 0))),
                    use_roygbiv=str(args.get("use_roygbiv", "true")).lower() == "true",
                    label_every=int(float(args.get("label_every", 4))),
                    label_radius_ratio=float(args.get("label_radius_ratio", 0.86)),
                    label_font_size_mm=float(args.get("label_font_size_mm", 1.0)),
                    label_stroke_width_mm=float(args.get("label_stroke_width_mm", 0.06)),
                    sector_boxes=str(args.get("sector_boxes", "true")).lower() == "true",
                    sector_box_size_mm=float(args.get("sector_box_size_mm", 1.4)),
                    center_digit=int(float(args.get("center_digit", 0))),
                    center_digit_size_mm=float(args.get("center_digit_size_mm", 6.0)),
                    center_digit_fill_background=str(args.get("center_digit_fill_background", "true")).lower() == "true",
                ),
            )
        elif op.op == "midi_dial":
            args = op.args
            data_path = args.get("file") or args.get("path") or args.get("data_path")
            if not data_path:
                raise ValueError("midi_dial requires file=<path to MIDI>")
            add_midi_dial_mm(
                dwg,
                cx_mm=float(args.get("cx_mm", 80)),
                cy_mm=float(args.get("cy_mm", 45)),
                radius_mm=float(args.get("radius_mm", 22)),
                midi_path=str(data_path),
                options=MidiDialOptions(
                    font_name=str(args.get("font", "Daemon Full Working")),
                    font_dir=str(args.get("font_dir", "./fonts")),
                    font_size_mm=float(args.get("font_size_mm", 2.2)),
                    note_charset=str(args.get("note_charset", "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz")),
                    cc_charset=str(args.get("cc_charset", "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789")),
                    note_opacity=float(args.get("note_opacity", 0.95)),
                    cc_opacity=float(args.get("cc_opacity", 0.9)),
                    background_color=str(args.get("background_color", "#000000")),
                    background_opacity=float(args.get("background_opacity", 0.35)),
                    outer_stroke=str(args.get("outer_stroke", "#111111")),
                    outer_stroke_width_mm=float(args.get("outer_stroke_width_mm", 0.5)),
                    note_stroke=str(args.get("note_stroke", "#111111")),
                    note_stroke_width_mm=float(args.get("note_stroke_width_mm", 0.12)),
                    cc_mark_length_mm=float(args.get("cc_mark_length_mm", 1.0)),
                    cc_mark_width_mm=float(args.get("cc_mark_width_mm", 0.08)),
                    cc_ring_offset_mm=float(args.get("cc_ring_offset_mm", 1.2)),
                    inner_radius_ratio=float(args.get("inner_radius_ratio", 0.12)),
                    outer_radius_ratio=float(args.get("outer_radius_ratio", 0.92)),
                    rotation_deg=float(args.get("rotation_deg", 0.0)),
                ),
            )


def render_svg(program: ScriptProgram, out_path: Path) -> Path:
    front_ops = [op for op in program.ops if op.op == "front_banknote"]
    back_ops = [op for op in program.ops if op.op == "back_banknote"]

    if back_ops:
        overlay_ops = [op for op in program.ops if op.op != "back_banknote"]
        params = _normalize_back_params(back_ops[-1].args)
        W = int(mm_to_px(float(params["width_mm"]), 300.0))
        H = int(mm_to_px(float(params["height_mm"]), 300.0))
        generate_backside_svg(
            outfile=str(out_path),
            denomination=params["denomination"],
            title_text=str(params["title"]),
            phrase_text=str(params["phrase"]),
            size_px=(W, H),
            serial_id=params["serial_id"],
            timestamp_ms=params["timestamp_ms"],
            seed_text=str(params["seed_text"]),
        )

        if overlay_ops:
            overlay = svgwrite.Drawing(size=(W, H), viewBox=f"0 0 {W} {H}")
            _render_ops(overlay, overlay_ops, W, H)
            overlay_svg = overlay.tostring()
            start = overlay_svg.find(">")
            end = overlay_svg.rfind("</svg>")
            inner = overlay_svg[start + 1 : end] if start != -1 and end != -1 else overlay_svg
            svg_text = out_path.read_text(encoding="utf-8")
            out_path.write_text(svg_text.replace("</svg>", inner + "</svg>"), encoding="utf-8")
        return out_path

    overlay_ops = [op for op in program.ops if op.op != "front_banknote"]
    if front_ops:
        params = _normalize_front_params(front_ops[-1].args)
        generate_fantasy_banknote(
            seed_text=str(params["seed_text"]),
            input_image_path=str(params["input_image_path"]),
            outfile_svg=str(out_path),
            width_mm=float(params["width_mm"]),
            height_mm=float(params["height_mm"]),
            title=str(params["title"]),
            subtitle=str(params["subtitle"]),
            serial_id=params["serial_id"],
            timestamp=params["timestamp"],
            denomination=params["denomination"],
            specimen=bool(params["specimen"]),
            bg_dir=str(params["bg_dir"]),
            background_prompt=str(params["background_prompt"]),
            border_inset_mm=float(params["border_inset_mm"]),
            border_thickness_mm=float(params["border_thickness_mm"]),
            enable_qr_border=bool(params["enable_qr_border"]),
            enable_background=bool(params["enable_background"]),
            background_filter=str(params["background_filter"]),
            background_margin=int(params["background_margin"]),
            background_segments=int(params["background_segments"]),
            mosaic_font=str(params["mosaic_font"]),
            mosaic_font_dir=str(params["mosaic_font_dir"]),
            mosaic_font_size_mm=float(params["mosaic_font_size_mm"]),
            mosaic_charset=str(params["mosaic_charset"]),
            mosaic_invert=bool(params["mosaic_invert"]),
            mosaic_snap_grid_px=float(params["mosaic_snap_grid_px"]),
            mosaic_opacity=float(params["mosaic_opacity"]),
            glyph_font=str(params["glyph_font"]),
            glyph_font_dir=str(params["glyph_font_dir"]),
            glyph_font_size_mm=float(params["glyph_font_size_mm"]),
            glyph_charset=str(params["glyph_charset"]),
            glyph_invert=bool(params["glyph_invert"]),
            glyph_snap_grid_px=float(params["glyph_snap_grid_px"]),
            glyph_opacity=float(params["glyph_opacity"]),
            glyph_fill_dark=str(params["glyph_fill_dark"]),
            glyph_fill_light=str(params["glyph_fill_light"]),
            glyph_stroke_dark=str(params["glyph_stroke_dark"]),
            glyph_stroke_light=str(params["glyph_stroke_light"]),
            glyph_stroke_width_mm=float(params["glyph_stroke_width_mm"]),
            glyph_inset_scale=float(params["glyph_inset_scale"]),
            glyph_outset_scale=float(params["glyph_outset_scale"]),
            glyph_threshold=int(params["glyph_threshold"]),
            glyph_colorize=bool(params["glyph_colorize"]),
            glyph_cell_padding_mm=float(params["glyph_cell_padding_mm"]),
            enable_microgrid=bool(params["enable_microgrid"]),
            enable_decorative_border=bool(params["enable_decorative_border"]),
            enable_center_seal=bool(params["enable_center_seal"]),
            enable_center_text=bool(params["enable_center_text"]),
            enable_corner_decorations=bool(params["enable_corner_decorations"]),
            enable_corner_denoms=bool(params["enable_corner_denoms"]),
            enable_microprint=bool(params["enable_microprint"]),
            microprint_repetitions=int(params["microprint_repetitions"]),
            microprint_text=params["microprint_text"],
            center_radius_scale=float(params["center_radius_scale"]),
            small_radius_scale=float(params["small_radius_scale"]),
            text_seal_scale=float(params["text_seal_scale"]),
            secondary_ring_scale=float(params["secondary_ring_scale"]),
            center_seal_scale=float(params["center_seal_scale"]),
            title_font=str(params["title_font"]),
            subtitle_font=str(params["subtitle_font"]),
            corner_font=str(params["corner_font"]),
            seal_chinese_font=str(params["seal_chinese_font"]),
            seal_english_font=str(params["seal_english_font"]),
            showcase_widgets=bool(params["showcase_widgets"]),
            ascii_stamp_prompt=params["ascii_stamp_prompt"],
            showcase_labels=bool(params["showcase_labels"]),
            label_font=str(params["label_font"]),
            label_size_mm=float(params["label_size_mm"]),
            qr_url=params["qr_url"],
            require_signed_qr=bool(params["require_signed_qr"]),
            sm2_private_key=params["sm2_private_key"],
            sm2_public_key=params["sm2_public_key"],
            verify_base_url=params["verify_base_url"],
            issuer_id=params["issuer_id"],
            validity_days=int(params["validity_days"]),
            pow_difficulty=int(params["pow_difficulty"]),
            sm4_key=params["sm4_key"],
            sm4_enable=bool(params["sm4_enable"]),
            qr_stamp_width=int(params["qr_stamp_width"]),
            qr_stamp_height=int(params["qr_stamp_height"]),
            qr_rows=int(params["qr_rows"]),
            qr_side=str(params["qr_side"]),
            qr_stamp=bool(params["qr_stamp"]),
            aztec=bool(params["aztec"]),
            aztec_scale=float(params["aztec_scale"]),
            aztec_border=float(params["aztec_border"]),
            aztec_rotation_base=float(params["aztec_rotation_base"]),
            aztec_offset_x=float(params["aztec_offset_x"]),
            aztec_offset_y=float(params["aztec_offset_y"]),
            aztec_border_opacity=float(params["aztec_border_opacity"]),
        )

        if overlay_ops:
            W = int(float(params["width_mm"]) * 300 / 25.4)
            H = int(float(params["height_mm"]) * 300 / 25.4)
            overlay = svgwrite.Drawing(size=(W, H), viewBox=f"0 0 {W} {H}")
            _render_ops(overlay, overlay_ops, W, H)
            overlay_svg = overlay.tostring()
            start = overlay_svg.find(">")
            end = overlay_svg.rfind("</svg>")
            inner = overlay_svg[start + 1 : end] if start != -1 and end != -1 else overlay_svg
            svg_text = out_path.read_text(encoding="utf-8")
            out_path.write_text(svg_text.replace("</svg>", inner + "</svg>"), encoding="utf-8")
        return out_path

    dwg = svgwrite.Drawing(str(out_path), size=(program.state.width, program.state.height))
    dwg.add(dwg.rect(insert=(0, 0), size=(program.state.width, program.state.height), fill=program.state.background))
    _render_ops(dwg, program.ops, program.state.width, program.state.height)
    dwg.save()
    return out_path


def render_html(program: ScriptProgram, out_path: Path, svg_path: Optional[Path] = None) -> Path:
    if svg_path and svg_path.exists():
        svg_text = svg_path.read_text(encoding="utf-8")
        html = f"""<!doctype html>
<html>
<head><meta charset=\"utf-8\"><title>EisenScript Render</title></head>
<body style=\"margin:0;display:flex;justify-content:center;align-items:center;background:#111;\">
<div style=\"width:100%;max-width:1200px;\">{svg_text}</div>
</body>
</html>"""
        out_path.write_text(html, encoding="utf-8")
        return out_path

        ops = [{"op": op.op, **op.args} for op in program.ops]
        html = f"""<!doctype html>
<html>
<head><meta charset=\"utf-8\"><title>EisenScript Render</title></head>
<body style=\"margin:0;\">
<canvas id=\"c\" width=\"{program.state.width}\" height=\"{program.state.height}\" style=\"width:100%;max-width:{program.state.width}px;\"></canvas>
<script>
const ops = {json.dumps(ops)};
const canvas = document.getElementById('c');
const ctx = canvas.getContext('2d');
ctx.fillStyle = {json.dumps(program.state.background)};
ctx.fillRect(0,0,canvas.width,canvas.height);
ops.forEach(op => {{
    if (op.op === 'rect') {{
        ctx.fillStyle = op.fill;
        ctx.fillRect(op.x, op.y, op.w, op.h);
    }} else if (op.op === 'circle') {{
        ctx.fillStyle = op.fill;
        ctx.beginPath();
        ctx.arc(op.x, op.y, op.r, 0, Math.PI * 2);
        ctx.fill();
    }} else if (op.op === 'line') {{
        ctx.strokeStyle = op.stroke;
        ctx.lineWidth = op.width;
        ctx.beginPath();
        ctx.moveTo(op.x1, op.y1);
        ctx.lineTo(op.x2, op.y2);
        ctx.stroke();
    }} else if (op.op === 'text') {{
        ctx.fillStyle = op.fill;
        ctx.font = `${{op.size}}px sans-serif`;
        ctx.fillText(op.text, op.x, op.y);
    }}
}});
</script>
</body>
</html>"""
        out_path.write_text(html, encoding="utf-8")
        return out_path


def render_script_to_svg_html(source: str, out_dir: Path) -> Tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    program = parse_script(source)
    svg_path = out_dir / "eisen.svg"
    html_path = out_dir / "eisen.html"
    render_svg(program, svg_path)
    render_html(program, html_path, svg_path=svg_path)
    return svg_path, html_path

"""EisenScript: simple script-to-SVG + HTML/Canvas renderer."""
from __future__ import annotations

import base64
import json
import shlex
import os
import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import math
import svgwrite
import re
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
from ..graphics.generate_banknote_front import (
    add_text_seal as add_front_text_seal,
    add_secondary_ring as add_front_secondary_ring,
    add_center_seal as add_front_center_seal,
    add_center_text as add_front_center_text,
    add_functional_corner_decorations as add_front_corner_decorations,
    add_corner_denoms as add_front_corner_denoms,
    add_chinese_microprint as add_front_chinese_microprint,
)
from ..widgets import add_qr_like_border_front
from ..graphics.modules.qr import safe_make_matrix, denomination_to_color, add_roygbiv_qr_style
from PIL import Image
from ..filters import (
    add_vectorized_background,
    add_vectorized_background_sm2_crosshatch,
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
    add_daemon_security_pattern_mm,
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


_KNOWN_COMMANDS = {
    "size",
    "background",
    "rect",
    "circle",
    "dot",
    "pix",
    "polygon",
    "text_dial",
    "text_grid",
    "letter_border",
    "hash_mandala",
    "hash_mandala_rect",
    "daemon_security",
    "front_qr_border",
    "front_corner_denoms",
    "front_corner_decorations",
    "front_center_seal",
    "front_microprint_seal",
    "front_center_text",
    "front_color_qr",
    "front_aztec",
    "line",
    "midi_dial",
    "text",
    "qr_code",
    "pixel_art",
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
    "cutout_circle",
    "mask_circle",
    "sd_background",
    "front_banknote",
    "back_banknote",
    "group",
    "endgroup",
    "end_group",
    "group_end",
}


def _format_value(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int,)):
        return str(value)
    if isinstance(value, (float,)):
        if abs(value - round(value)) < 1e-6:
            return str(int(round(value)))
        return f"{value:.2f}"
    if isinstance(value, str):
        if any(ch.isspace() for ch in value):
            return f"\"{value}\""
        return value
    return str(value)


def _eval_expr(expr: str, env: dict[str, object]) -> object:
    def _cos_deg(x: float) -> float:
        return math.cos(math.radians(x))

    def _sin_deg(x: float) -> float:
        return math.sin(math.radians(x))

    def _tan_deg(x: float) -> float:
        return math.tan(math.radians(x))

    def _if_func(cond: object, yes: object, no: object) -> object:
        return yes if bool(cond) else no

    allowed_funcs: dict[str, object] = {
        "cos": _cos_deg,
        "sin": _sin_deg,
        "tan": _tan_deg,
        "sqrt": math.sqrt,
        "abs": abs,
        "min": min,
        "max": max,
        "pow": pow,
        "chr": lambda x: chr(int(x)),
        "iff": _if_func,
    }
    allowed_names: dict[str, object] = {"pi": math.pi, "e": math.e}
    allowed_names.update(env)

    expr = re.sub(r"\bif\s*\(", "iff(", expr)
    node = ast.parse(expr, mode="eval")

    def _eval(node_obj: ast.AST) -> object:
        if isinstance(node_obj, ast.Expression):
            return _eval(node_obj.body)
        if isinstance(node_obj, ast.Constant) and isinstance(node_obj.value, (int, float, str)):
            return node_obj.value
        if isinstance(node_obj, ast.Name):
            if node_obj.id in allowed_names:
                return allowed_names[node_obj.id]
            raise ValueError(f"Unknown name '{node_obj.id}' in expression")
        if isinstance(node_obj, ast.UnaryOp) and isinstance(node_obj.op, (ast.UAdd, ast.USub)):
            val = _eval(node_obj.operand)
            if not isinstance(val, (int, float)):
                raise ValueError("Unary op requires numeric value")
            return val if isinstance(node_obj.op, ast.UAdd) else -val
        if isinstance(node_obj, ast.BinOp) and isinstance(
            node_obj.op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.Mod)
        ):
            left = _eval(node_obj.left)
            right = _eval(node_obj.right)
            if not isinstance(left, (int, float)) or not isinstance(right, (int, float)):
                raise ValueError("Binary op requires numeric values")
            if isinstance(node_obj.op, ast.Add):
                return left + right
            if isinstance(node_obj.op, ast.Sub):
                return left - right
            if isinstance(node_obj.op, ast.Mult):
                return left * right
            if isinstance(node_obj.op, ast.Div):
                return left / right
            if isinstance(node_obj.op, ast.Pow):
                return left**right
            if isinstance(node_obj.op, ast.Mod):
                return left % right
        if isinstance(node_obj, ast.Compare):
            if len(node_obj.ops) != 1 or len(node_obj.comparators) != 1:
                raise ValueError("Only single comparisons are supported")
            left = _eval(node_obj.left)
            right = _eval(node_obj.comparators[0])
            op = node_obj.ops[0]
            if isinstance(op, ast.Eq):
                return left == right
            if isinstance(op, ast.NotEq):
                return left != right
            if isinstance(op, ast.Lt):
                return left < right
            if isinstance(op, ast.LtE):
                return left <= right
            if isinstance(op, ast.Gt):
                return left > right
            if isinstance(op, ast.GtE):
                return left >= right
            raise ValueError("Unsupported comparison")
        if isinstance(node_obj, ast.Call) and isinstance(node_obj.func, ast.Name):
            fn = allowed_funcs.get(node_obj.func.id)
            if fn is None:
                raise ValueError(f"Function '{node_obj.func.id}' not allowed")
            args = [_eval(arg) for arg in node_obj.args]
            return fn(*args)
        raise ValueError("Unsupported expression")

    return _eval(node)


def _expand_for_loops(source: str) -> List[str]:
    lines = source.splitlines()

    def _strip_inline_comment(line: str) -> str:
        if "{{" in line or "{%" in line:
            return line
        in_single = False
        in_double = False
        for idx, ch in enumerate(line):
            if ch == "'" and not in_double:
                in_single = not in_single
            elif ch == '"' and not in_single:
                in_double = not in_double
            elif ch == "#" and not in_single and not in_double:
                return line[:idx]
        return line

    def _process_block(block_lines: List[str], env: dict[str, object]) -> List[str]:
        out: List[str] = []
        idx = 0
        while idx < len(block_lines):
            raw = _strip_inline_comment(block_lines[idx])
            stripped = raw.strip()
            if "{{" in raw or "{%" in raw:
                out.append(raw)
                idx += 1
                continue
            if not stripped or stripped.startswith("#"):
                out.append(raw)
                idx += 1
                continue

            if stripped.lower().startswith("for ") and "[" in stripped and stripped.endswith("]"):
                base_indent = len(raw) - len(raw.lstrip())
                clause = stripped[stripped.find("[") + 1 : stripped.rfind("]")]
                parts = [p.strip() for p in clause.split(";") if p.strip()]
                if len(parts) != 3:
                    raise ValueError(f"Invalid for clause: {clause}")
                init_part, cond_part, incr_part = parts
                if "=" not in init_part:
                    raise ValueError(f"Invalid for init: {init_part}")
                var_name, init_expr = [p.strip() for p in init_part.split("=", 1)]
                block: List[str] = []
                idx += 1
                while idx < len(block_lines):
                    raw_line = _strip_inline_comment(block_lines[idx])
                    if raw_line.strip() == "":
                        block.append(raw_line)
                        idx += 1
                        continue
                    indent = len(raw_line) - len(raw_line.lstrip())
                    if indent <= base_indent:
                        break
                    block.append(raw_line)
                    idx += 1

                loop_env = dict(env)
                loop_env[var_name] = _eval_expr(init_expr, loop_env)

                def _check_condition() -> bool:
                    for op in ("<=", ">=", "<", ">", "==", "!="):
                        if op in cond_part:
                            left, right = [p.strip() for p in cond_part.split(op, 1)]
                            lval = _eval_expr(left, loop_env)
                            rval = _eval_expr(right, loop_env)
                            return {
                                "<": lval < rval,
                                ">": lval > rval,
                                "<=": lval <= rval,
                                ">=": lval >= rval,
                                "==": lval == rval,
                                "!=": lval != rval,
                            }[op]
                    raise ValueError(f"Invalid for condition: {cond_part}")

                def _apply_increment() -> None:
                    if incr_part.endswith("++"):
                        name = incr_part[:-2].strip()
                        loop_env[name] = float(loop_env.get(name, 0.0)) + 1.0
                        return
                    if incr_part.endswith("--"):
                        name = incr_part[:-2].strip()
                        loop_env[name] = float(loop_env.get(name, 0.0)) - 1.0
                        return
                    if "+=" in incr_part:
                        name, expr = [p.strip() for p in incr_part.split("+=", 1)]
                        loop_env[name] = float(loop_env.get(name, 0.0)) + float(
                            _eval_expr(expr, loop_env)
                        )
                        return
                    if "-=" in incr_part:
                        name, expr = [p.strip() for p in incr_part.split("-=", 1)]
                        loop_env[name] = float(loop_env.get(name, 0.0)) - float(
                            _eval_expr(expr, loop_env)
                        )
                        return
                    if "=" in incr_part:
                        name, expr = [p.strip() for p in incr_part.split("=", 1)]
                        loop_env[name] = _eval_expr(expr, loop_env)
                        return
                    raise ValueError(f"Invalid for increment: {incr_part}")

                safe_guard = 0
                while _check_condition():
                    safe_guard += 1
                    if safe_guard > 10000:
                        raise ValueError("for loop exceeded safe iteration limit")
                    out.extend(_process_block(block, dict(loop_env)))
                    _apply_increment()
                continue

            if stripped.lower().startswith("for ") and " in " in stripped:
                base_indent = len(raw) - len(raw.lstrip())
                header = stripped[4:]
                var_name, values_expr = [p.strip() for p in header.split(" in ", 1)]
                values = shlex.split(values_expr)
                block: List[str] = []
                idx += 1
                while idx < len(block_lines):
                    raw_line = _strip_inline_comment(block_lines[idx])
                    if raw_line.strip() == "":
                        block.append(raw_line)
                        idx += 1
                        continue
                    indent = len(raw_line) - len(raw_line.lstrip())
                    if indent <= base_indent:
                        break
                    block.append(raw_line)
                    idx += 1

                for raw_val in values:
                    loop_env = dict(env)
                    try:
                        loop_env[var_name] = _eval_expr(raw_val, loop_env)
                    except Exception:
                        loop_env[var_name] = raw_val
                    out.extend(_process_block(block, loop_env))
                continue

            assign_match = re.match(r"^([A-Za-z_]\w*)\s*=\s*(.+)$", stripped)
            if assign_match and assign_match.group(1).lower() not in _KNOWN_COMMANDS:
                name = assign_match.group(1)
                expr = assign_match.group(2)
                env[name] = _eval_expr(expr, env)
                idx += 1
                continue

            def _replace_var(match: re.Match) -> str:
                var = match.group(1)
                if var in env:
                    return _format_value(env[var])
                return match.group(0)

            expanded = re.sub(r"\$([A-Za-z_]\w*)", _replace_var, stripped)
            out.append(expanded)
            idx += 1
        return out

    return _process_block(lines, {})


def parse_script(source: str) -> ScriptProgram:
    program = ScriptProgram()
    logical_lines: List[str] = []
    buffer = ""
    last_op: DrawOp | None = None
    ops_stack: list[list[DrawOp]] = [program.ops]
    group_stack: list[dict[str, object]] = []

    expanded_lines = _expand_for_loops(source)
    for raw_line in expanded_lines:
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
        current_ops = ops_stack[-1]
        if cmd == "group":
            boolean = ""
            if any("=" in arg for arg in args):
                values = _parse_kv_args(args)
                boolean = str(values.get("boolean") or values.get("op") or values.get("type") or "")
            elif args:
                boolean = str(args[0])
            children: list[DrawOp] = []
            group_stack.append({"boolean": boolean.strip().lower(), "children": children})
            ops_stack.append(children)
            last_op = None
            continue
        if cmd in {"endgroup", "end_group", "group_end"}:
            if not group_stack:
                raise ValueError("endgroup without an open group")
            group_info = group_stack.pop()
            ops_stack.pop()
            last_op = DrawOp("group", group_info)
            ops_stack[-1].append(last_op)
            continue
        if cmd == "size":
            if len(args) < 2:
                continue
            program.state.width = int(float(args[0]))
            program.state.height = int(float(args[1]))
        elif cmd == "background":
            if not args:
                continue
            program.state.background = str(args[0]).strip().strip('"').strip("'")
        elif cmd == "rect":
            if len(args) < 4:
                continue
            x, y, w, h = map(float, args[:4])
            fill = args[4] if len(args) > 4 else "#000"
            last_op = DrawOp("rect", {"x": x, "y": y, "w": w, "h": h, "fill": fill})
            current_ops.append(last_op)
        elif cmd == "circle":
            if len(args) < 3:
                continue
            x, y, r = map(float, args[:3])
            fill = args[3] if len(args) > 3 else "#000"
            last_op = DrawOp("circle", {"x": x, "y": y, "r": r, "fill": fill})
            current_ops.append(last_op)
        elif cmd == "dot":
            if len(args) < 2:
                continue
            x, y = map(float, args[:2])
            fill = args[2] if len(args) > 2 else "#000"
            last_op = DrawOp("dot", {"x": x, "y": y, "fill": fill})
            current_ops.append(last_op)
        elif cmd == "pix":
            if len(args) < 2:
                continue
            x, y = map(float, args[:2])
            fill = args[2] if len(args) > 2 else "#000"
            last_op = DrawOp("pix", {"x": x, "y": y, "fill": fill})
            current_ops.append(last_op)
        elif cmd == "polygon":
            values = _parse_kv_args(args)
            points = _parse_points(values.get("points"))
            if not points:
                raise ValueError("polygon requires points=\"x,y x,y ...\"")
            fill = values.get("fill", "#000")
            stroke = values.get("stroke")
            stroke_width = values.get("stroke_width")
            last_op = DrawOp(
                "polygon",
                {
                    "points": points,
                    "fill": fill,
                    "stroke": stroke,
                    "stroke_width": float(stroke_width) if stroke_width is not None else None,
                },
            )
            current_ops.append(last_op)
        elif cmd == "text_dial":
            values = _parse_kv_args(args)
            last_op = DrawOp("text_dial", values)
            current_ops.append(last_op)
        elif cmd == "text_grid":
            values = _parse_kv_args(args)
            last_op = DrawOp("text_grid", values)
            current_ops.append(last_op)
        elif cmd == "letter_border":
            values = _parse_kv_args(args)
            last_op = DrawOp("letter_border", values)
            current_ops.append(last_op)
        elif cmd == "hash_mandala":
            values = _parse_kv_args(args)
            last_op = DrawOp("hash_mandala", values)
            current_ops.append(last_op)
        elif cmd == "hash_mandala_rect":
            values = _parse_kv_args(args)
            last_op = DrawOp("hash_mandala_rect", values)
            current_ops.append(last_op)
        elif cmd == "daemon_security":
            values = _parse_kv_args(args)
            last_op = DrawOp("daemon_security", values)
            current_ops.append(last_op)
        elif cmd in {
            "front_qr_border",
            "front_corner_denoms",
            "front_corner_decorations",
            "front_center_seal",
            "front_microprint_seal",
            "front_center_text",
            "front_color_qr",
            "front_aztec",
        }:
            values = _parse_kv_args(args)
            last_op = DrawOp(cmd, values)
            current_ops.append(last_op)
        elif cmd == "line":
            if len(args) < 4:
                continue
            x1, y1, x2, y2 = map(float, args[:4])
            stroke = args[4] if len(args) > 4 else "#000"
            width = float(args[5]) if len(args) > 5 else 1.0
            last_op = DrawOp("line", {"x1": x1, "y1": y1, "x2": x2, "y2": y2, "stroke": stroke, "width": width})
            current_ops.append(last_op)
        elif cmd == "midi_dial":
            values = _parse_kv_args(args)
            last_op = DrawOp("midi_dial", values)
            current_ops.append(last_op)
        elif cmd == "text":
            if len(args) < 5:
                continue
            x, y = map(float, args[:2])
            size = float(args[2])
            fill = args[3]
            content = " ".join(args[4:])
            last_op = DrawOp("text", {"x": x, "y": y, "size": size, "fill": fill, "text": content})
            current_ops.append(last_op)
        elif cmd == "qr_code":
            values = _parse_kv_args(args)
            last_op = DrawOp("qr_code", values)
            current_ops.append(last_op)
        elif cmd == "pixel_art":
            values = _parse_kv_args(args)
            last_op = DrawOp("pixel_art", values)
            current_ops.append(last_op)
        elif cmd == "cutout_circle":
            values = _parse_kv_args(args)
            last_op = DrawOp("cutout_circle", values)
            current_ops.append(last_op)
        elif cmd == "mask_circle":
            values = _parse_kv_args(args)
            last_op = DrawOp("mask_circle", values)
            current_ops.append(last_op)
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
            current_ops.append(last_op)
        elif cmd == "sd_background":
            values = _parse_kv_args(args)
            last_op = DrawOp("sd_background", values)
            current_ops.append(last_op)
        elif cmd == "sd_background_circle":
            values = _parse_kv_args(args)
            values.setdefault("background_clip", "circle")
            if "cx" in values and "background_clip_cx" not in values:
                values["background_clip_cx"] = values.get("cx")
            if "cy" in values and "background_clip_cy" not in values:
                values["background_clip_cy"] = values.get("cy")
            if "r" in values and "background_clip_r" not in values:
                values["background_clip_r"] = values.get("r")
            last_op = DrawOp("sd_background", values)
            current_ops.append(last_op)
        elif cmd == "front_banknote":
            values = _parse_kv_args(args)
            last_op = DrawOp("front_banknote", values)
            current_ops.append(last_op)
        elif cmd == "back_banknote":
            values = _parse_kv_args(args)
            last_op = DrawOp("back_banknote", values)
            current_ops.append(last_op)
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


def _add_image_background(
    dwg: svgwrite.Drawing,
    W: int,
    H: int,
    image_path: Path,
    opacity: float | None = None,
) -> svgwrite.base.BaseElement | None:
    data = image_path.read_bytes()
    mime = _image_mime_type(image_path)
    b64 = base64.b64encode(data).decode("ascii")
    href = f"data:{mime};base64,{b64}"
    img = dwg.image(href=href, insert=(0, 0), size=(W, H))
    if opacity is not None:
        img.update({"opacity": float(opacity)})
    dwg.add(img)
    return img


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


def _split_hex_alpha(color: str | None) -> tuple[str | None, float | None]:
    if not color:
        return None, None
    match = re.fullmatch(r"#([0-9a-fA-F]{8})", color.strip())
    if not match:
        return color, None
    hex_value = match.group(1)
    base = f"#{hex_value[:6]}"
    alpha = int(hex_value[6:], 16) / 255.0
    return base, alpha


def _parse_points(value: str | None) -> list[tuple[float, float]]:
    if not value:
        return []
    cleaned = value.replace(";", " ").strip()
    if not cleaned:
        return []
    points: list[tuple[float, float]] = []
    for part in re.split(r"\s+", cleaned):
        if not part:
            continue
        if "," not in part:
            continue
        x_str, y_str = part.split(",", 1)
        try:
            points.append((float(x_str), float(y_str)))
        except ValueError:
            continue
    return points


def _require_shapely():
    try:
        import shapely.geometry as geometry
        import shapely.ops as ops
    except Exception as exc:
        raise RuntimeError("shapely is required for boolean groups. Install it with pip install shapely.") from exc
    return geometry, ops


def _is_shape_op(op: DrawOp) -> bool:
    if op.op in {"rect", "circle", "polygon", "dot", "pix"}:
        return True
    if op.op == "group" and str(op.args.get("boolean", "")).strip():
        return True
    return False


def _op_to_geometry(op: DrawOp):
    geometry, _ = _require_shapely()
    if op.op == "rect":
        geom = geometry.box(op.args["x"], op.args["y"], op.args["x"] + op.args["w"], op.args["y"] + op.args["h"])
        return geom, str(op.args.get("fill", "#000"))
    if op.op == "circle":
        geom = geometry.Point(op.args["x"], op.args["y"]).buffer(op.args["r"], resolution=32)
        return geom, str(op.args.get("fill", "#000"))
    if op.op == "dot":
        geom = geometry.Point(op.args["x"], op.args["y"]).buffer(0.5, resolution=16)
        return geom, str(op.args.get("fill", "#000"))
    if op.op == "pix":
        geom = geometry.box(op.args["x"], op.args["y"], op.args["x"] + 1.0, op.args["y"] + 1.0)
        return geom, str(op.args.get("fill", "#000"))
    if op.op == "polygon":
        points = op.args.get("points", [])
        if len(points) < 3:
            return None, None
        geom = geometry.Polygon(points)
        return geom, str(op.args.get("fill", "#000"))
    return None, None


def _apply_boolean(boolean: str, geometries: list):
    if not geometries:
        return None
    geometry, ops = _require_shapely()
    op_name = boolean.lower()
    if op_name == "union":
        return ops.unary_union(geometries)
    if op_name in {"difference", "divide"}:
        result = geometries[0]
        for geom in geometries[1:]:
            result = result.difference(geom)
        return result
    if op_name in {"punchout", "subtract"}:
        result = geometries[-1]
        for geom in geometries[:-1]:
            result = result.difference(geom)
        return result
    if op_name == "intersection":
        result = geometries[0]
        for geom in geometries[1:]:
            result = result.intersection(geom)
        return result
    return ops.unary_union(geometries)


def _geometry_to_paths(geom) -> list[str]:
    geometry, _ = _require_shapely()
    if geom is None or geom.is_empty:
        return []
    polygons = []
    if isinstance(geom, geometry.Polygon):
        polygons = [geom]
    elif isinstance(geom, geometry.MultiPolygon):
        polygons = list(geom.geoms)
    elif isinstance(geom, geometry.GeometryCollection):
        polygons = [g for g in geom.geoms if isinstance(g, geometry.Polygon)]
    paths: list[str] = []
    for poly in polygons:
        parts: list[str] = []
        exterior = list(poly.exterior.coords)
        if exterior:
            parts.append("M" + " L".join(f"{x:.3f},{y:.3f}" for x, y in exterior) + " Z")
        for interior in poly.interiors:
            coords = list(interior.coords)
            if coords:
                parts.append("M" + " L".join(f"{x:.3f},{y:.3f}" for x, y in coords) + " Z")
        if parts:
            paths.append(" ".join(parts))
    return paths


def _draw_geometry(dwg: svgwrite.Drawing, geom, fill_color: str) -> None:
    fill, fill_opacity = _split_hex_alpha(fill_color)
    paths = _geometry_to_paths(geom)
    for path in paths:
        path_kwargs = {"d": path, "fill": fill, "fill_rule": "evenodd"}
        if fill_opacity is not None:
            path_kwargs["fill_opacity"] = fill_opacity
        dwg.add(dwg.path(**path_kwargs))


def _collect_geometries(ops: list[DrawOp]) -> list[tuple[object, str]]:
    shapes: list[tuple[object, str]] = []
    for op in ops:
        if op.op == "group":
            boolean = str(op.args.get("boolean", "")).strip().lower()
            children = op.args.get("children", [])
            if not isinstance(children, list):
                continue
            if boolean:
                child_shapes = _collect_geometries(children)
                if child_shapes:
                    geom = _apply_boolean(boolean, [g for g, _ in child_shapes])
                    fill = child_shapes[0][1]
                    if geom is not None and not geom.is_empty:
                        shapes.append((geom, fill))
            else:
                shapes.extend(_collect_geometries(children))
            continue
        geom, fill = _op_to_geometry(op)
        if geom is not None:
            shapes.append((geom, fill))
    return shapes


def _render_ops(dwg: svgwrite.Drawing, ops: List[DrawOp], canvas_w: int, canvas_h: int) -> None:
    last_element: svgwrite.base.BaseElement | None = None
    last_background_element: svgwrite.base.BaseElement | None = None
    clip_idx = 0
    mask_idx = 0
    for op in ops:
        if op.op == "rect":
            fill, fill_opacity = _split_hex_alpha(str(op.args.get("fill")))
            rect_kwargs = {"insert": (op.args["x"], op.args["y"]), "size": (op.args["w"], op.args["h"]), "fill": fill}
            if fill_opacity is not None:
                rect_kwargs["fill_opacity"] = fill_opacity
            element = dwg.rect(**rect_kwargs)
            dwg.add(element)
            last_element = element
        elif op.op == "circle":
            fill, fill_opacity = _split_hex_alpha(str(op.args.get("fill")))
            circle_kwargs = {"center": (op.args["x"], op.args["y"]), "r": op.args["r"], "fill": fill}
            if fill_opacity is not None:
                circle_kwargs["fill_opacity"] = fill_opacity
            element = dwg.circle(**circle_kwargs)
            dwg.add(element)
            last_element = element
        elif op.op == "dot":
            fill, fill_opacity = _split_hex_alpha(str(op.args.get("fill")))
            dot_kwargs = {"center": (op.args["x"], op.args["y"]), "r": 0.5, "fill": fill}
            if fill_opacity is not None:
                dot_kwargs["fill_opacity"] = fill_opacity
            element = dwg.circle(**dot_kwargs)
            dwg.add(element)
            last_element = element
        elif op.op == "pix":
            fill, fill_opacity = _split_hex_alpha(str(op.args.get("fill")))
            pix_kwargs = {"insert": (op.args["x"], op.args["y"]), "size": (1.0, 1.0), "fill": fill}
            if fill_opacity is not None:
                pix_kwargs["fill_opacity"] = fill_opacity
            element = dwg.rect(**pix_kwargs)
            dwg.add(element)
            last_element = element
        elif op.op == "polygon":
            points = op.args["points"]
            fill, fill_opacity = _split_hex_alpha(str(op.args.get("fill", "#000")))
            stroke = op.args.get("stroke", None)
            stroke_width = op.args.get("stroke_width", None)
            polygon_kwargs = {"fill": fill}
            if fill_opacity is not None:
                polygon_kwargs["fill_opacity"] = fill_opacity
            if stroke:
                polygon_kwargs["stroke"] = stroke
            if stroke_width:
                polygon_kwargs["stroke_width"] = stroke_width
            element = dwg.polygon(points=points, **polygon_kwargs)
            dwg.add(element)
            last_element = element
        elif op.op == "line":
            element = dwg.line(
                start=(op.args["x1"], op.args["y1"]),
                end=(op.args["x2"], op.args["y2"]),
                stroke=op.args["stroke"],
                stroke_width=op.args["width"],
            )
            dwg.add(element)
            last_element = element
        elif op.op == "text":
            fill, fill_opacity = _split_hex_alpha(str(op.args.get("fill")))
            text_kwargs = {"insert": (op.args["x"], op.args["y"]), "fill": fill, "font_size": op.args["size"]}
            if fill_opacity is not None:
                text_kwargs["fill_opacity"] = fill_opacity
            element = dwg.text(op.args["text"], **text_kwargs)
            dwg.add(element)
            last_element = element
        elif op.op == "pixel_art":
            args = op.args
            from ..widgets.pixel_art import add_pixel_art_stamp_mm

            add_pixel_art_stamp_mm(
                dwg,
                x_mm=float(args.get("x_mm", 0.0)),
                y_mm=float(args.get("y_mm", 0.0)),
                image_path=str(args.get("image") or args.get("path") or args.get("image_path") or ""),
                pixel_size_mm=float(args.get("pixel_size_mm", 0.5)),
                alpha_threshold=float(args.get("alpha_threshold", 0.05)),
                compress=str(args.get("compress", "true")).lower() == "true",
            )
            last_element = None
        elif op.op == "cutout_circle":
            target = str(op.args.get("target", "last")).strip().lower()
            if target == "document":
                continue
            element = last_element if target != "background" else last_background_element
            if element is None:
                continue
            cx = float(op.args.get("cx", canvas_w / 2))
            cy = float(op.args.get("cy", canvas_h / 2))
            radius = float(op.args.get("r", min(canvas_w, canvas_h) / 2))
            clip_id = f"cutout_{clip_idx}"
            clip_idx += 1
            clip = dwg.defs.add(dwg.clipPath(id=clip_id))
            clip.add(dwg.circle(center=(cx, cy), r=radius))
            element.update({"clip-path": f"url(#{clip_id})"})
        elif op.op == "mask_circle":
            target = str(op.args.get("target", "last")).strip().lower()
            if target == "document":
                continue
            element = last_element if target != "background" else last_background_element
            if element is None:
                continue
            cx = float(op.args.get("cx", canvas_w / 2))
            cy = float(op.args.get("cy", canvas_h / 2))
            radius = float(op.args.get("r", min(canvas_w, canvas_h) / 2))
            invert = str(op.args.get("invert", "false")).lower() == "true"
            mask_id = f"mask_{mask_idx}"
            mask_idx += 1
            mask = dwg.defs.add(
                dwg.mask(id=mask_id, maskUnits="userSpaceOnUse", maskContentUnits="userSpaceOnUse")
            )
            if invert:
                mask.add(dwg.rect(insert=(0, 0), size=(canvas_w, canvas_h), fill="#ffffff"))
                mask.add(dwg.circle(center=(cx, cy), r=radius, fill="#000000"))
            else:
                mask.add(dwg.rect(insert=(0, 0), size=(canvas_w, canvas_h), fill="#000000"))
                mask.add(dwg.circle(center=(cx, cy), r=radius, fill="#ffffff"))
            element.update({"mask": f"url(#{mask_id})"})
        elif op.op == "group":
            boolean = str(op.args.get("boolean", "")).strip().lower()
            children = op.args.get("children", [])
            if not isinstance(children, list):
                continue
            if boolean:
                shapes = []
                for shape_op in _collect_geometries(children):
                    shapes.append(shape_op)
                if shapes:
                    geometries = [geom for geom, _ in shapes]
                    fill_color = shapes[0][1]
                    result = _apply_boolean(boolean, geometries)
                    if result is not None and not result.is_empty:
                        _draw_geometry(dwg, result, fill_color)
                        last_element = None
                non_shapes = [child for child in children if not _is_shape_op(child)]
                if non_shapes:
                    _render_ops(dwg, non_shapes, canvas_w, canvas_h)
            else:
                _render_ops(dwg, children, canvas_w, canvas_h)
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
                element = dwg.rect(insert=(x, y), size=(size, size), fill=bg)
                dwg.add(element)
                last_element = element

            for r in range(cells):
                for c in range(cells):
                    if not matrix[r][c]:
                        continue
                    element = dwg.rect(
                        insert=(x + c * cell_size, y + r * cell_size),
                        size=(cell_size, cell_size),
                        fill=fg,
                    )
                    dwg.add(element)
                    last_element = element
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
            last_element = None
        elif op.op == "back_corner_denoms":
            args = op.args
            denom = args.get("denomination", "100")
            big_scale = float(args.get("big_scale", 1.0))
            small_scale = float(args.get("small_scale", 1.0))
            add_corner_denoms(
                dwg,
                canvas_w,
                canvas_h,
                str(denom),
                big_scale=big_scale,
                small_scale=small_scale,
            )
            last_element = None
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
            last_element = None
        elif op.op == "back_holographic_seals":
            args = op.args
            serial_id = str(args.get("serial_id", ""))
            denom = args.get("denomination", 100)
            radius = int(float(args.get("radius", min(canvas_w, canvas_h) * 0.25)))
            add_holographic_seals(dwg, canvas_w, canvas_h, serial_id=serial_id, denomination=denom, radius=radius)
            last_element = None
        elif op.op == "back_center_text":
            args = op.args
            title = str(args.get("title", "灵国国库"))
            phrase = str(args.get("phrase", "灵之意志，天下共识"))
            denom = args.get("denomination", 100)
            denom_int = denom_to_int(denom)
            denom_exp = int(round(math.log10(max(1, denom_int)))) if denom_int > 0 else 0
            denom_color = str(args.get("denom_color", denomination_to_color(denom_exp)))
            add_center_text(dwg, canvas_w, canvas_h, title, phrase, denom_color)
            last_element = None
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
            last_element = None
        elif op.op == "back_qr_border":
            args = op.args
            seed = str(args.get("seed", args.get("seed_text", "")))
            serial_id = args.get("serial_id")
            timestamp_ms = args.get("timestamp_ms")
            add_qr_like_border(dwg, seed, canvas_w, canvas_h, serial_id=serial_id, timestamp_ms=timestamp_ms)
            last_element = None
        elif op.op == "back_verification_text":
            args = op.args
            serial_id = args.get("serial_id", "")
            timestamp_ms = args.get("timestamp_ms") or generate_timestamp_ms_precise()
            add_verification_text(dwg, canvas_w, canvas_h, serial_id, timestamp_ms)
            last_element = None
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
            last_element = None
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
            last_element = None
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
            last_element = None
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
            last_element = None
        elif op.op == "sd_background":
            args = op.args
            filter_name = str(args.get("filter", args.get("background_filter", "vectorize"))).strip().lower()
            seed_text = str(args.get("seed_text", args.get("seed", "")))
            bg_dir = _clean_path(args.get("bg_dir", "./backgrounds"))
            margin = int(float(args.get("margin", args.get("background_margin", 60))))
            background_prompt = str(args.get("background_prompt", ""))
            background_segments = int(float(args.get("background_segments", 1024)))
            clear_bg = _coerce_bool(str(args.get("background_clear", args.get("clear", "false"))))
            clear_color = str(args.get("background_clear_color", args.get("clear_color", "#ffffff")))
            clear_opacity = args.get("background_clear_opacity", args.get("clear_opacity"))
            background_opacity = args.get("background_opacity")
            if background_opacity is not None:
                background_opacity = float(background_opacity)
            clip_shape = str(args.get("background_clip", "")).strip().lower()
            clip_cx = float(args.get("background_clip_cx", canvas_w / 2))
            clip_cy = float(args.get("background_clip_cy", canvas_h / 2))
            clip_r = float(args.get("background_clip_r", min(canvas_w, canvas_h) / 2))
            if clear_bg:
                rect_kwargs = {"insert": (0, 0), "size": (canvas_w, canvas_h), "fill": clear_color}
                if clear_opacity is not None:
                    rect_kwargs["fill_opacity"] = float(clear_opacity)
                element = dwg.rect(**rect_kwargs)
                dwg.add(element)
                last_element = element
                last_background_element = element

            def _apply_background_filter(name: str) -> None:
                nonlocal last_element

                def _apply_clip(element: svgwrite.base.BaseElement) -> None:
                    if clip_shape != "circle":
                        return
                    clip_id = f"bg_clip_{abs(hash((clip_cx, clip_cy, clip_r)))}"
                    clip = dwg.defs.add(dwg.clipPath(id=clip_id))
                    clip.add(dwg.circle(center=(clip_cx, clip_cy), r=clip_r))
                    element.update({"clip-path": f"url(#{clip_id})"})

                if name in {"none", "image", "raw"}:
                    sd_config = None
                    model_name = args.get("sd_model") or args.get("sd_model_name") or args.get("model")
                    cfg_scale = args.get("sd_cfg_scale") or args.get("cfg_scale")
                    if model_name or cfg_scale:
                        sd_config = SDAPIConfig(
                            model_name=str(model_name) if model_name is not None else None,
                            cfg_scale=float(cfg_scale) if cfg_scale is not None else None,
                        )
                    background_path = generate_sd_background(
                        prompt=background_prompt,
                        width=canvas_w - 2 * margin,
                        height=canvas_h - 2 * margin,
                        save_path=bg_dir,
                        seed_text=seed_text,
                        sdapi_config=sd_config,
                    )
                    if background_path:
                        img = _add_image_background(
                            dwg,
                            canvas_w,
                            canvas_h,
                            Path(background_path),
                            opacity=background_opacity,
                        )
                        if img is not None:
                            _apply_clip(img)
                            last_element = img
                            last_background_element = img
                elif name in {"letter_mosaic", "letter-mosaic", "mosaic", "letters"}:
                    sd_config = None
                    model_name = args.get("sd_model") or args.get("sd_model_name") or args.get("model")
                    cfg_scale = args.get("sd_cfg_scale") or args.get("cfg_scale")
                    if model_name or cfg_scale:
                        sd_config = SDAPIConfig(
                            model_name=str(model_name) if model_name is not None else None,
                            cfg_scale=float(cfg_scale) if cfg_scale is not None else None,
                        )
                    group = add_letter_mosaic_background(
                        dwg=dwg,
                        W=canvas_w,
                        H=canvas_h,
                        seed_text=seed_text,
                        bg_dir=bg_dir,
                        margin=margin,
                        background_prompt=background_prompt,
                        sdapi_config=sd_config,
                    )
                    if group is not None and background_opacity is not None:
                        group.update({"opacity": background_opacity})
                    if group is not None:
                        _apply_clip(group)
                        last_element = group
                        last_background_element = group
                elif name in {"glyph_grid", "glyph-grid", "glyphs", "grid"}:
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
                    sd_config = None
                    model_name = args.get("sd_model") or args.get("sd_model_name") or args.get("model")
                    cfg_scale = args.get("sd_cfg_scale") or args.get("cfg_scale")
                    if model_name or cfg_scale:
                        sd_config = SDAPIConfig(
                            model_name=str(model_name) if model_name is not None else None,
                            cfg_scale=float(cfg_scale) if cfg_scale is not None else None,
                        )
                    group = add_glyph_grid_background(
                        dwg=dwg,
                        W=canvas_w,
                        H=canvas_h,
                        seed_text=seed_text,
                        bg_dir=bg_dir,
                        margin=margin,
                        background_prompt=background_prompt,
                        config=GlyphGridConfig(options=glyph_options),
                        sdapi_config=sd_config,
                    )
                    if group is not None and background_opacity is not None:
                        group.update({"opacity": background_opacity})
                    if group is not None:
                        _apply_clip(group)
                        last_element = group
                        last_background_element = group
                elif name in {"triangle_mosaic", "triangle-mosaic", "triangles"}:
                    sd_config = None
                    model_name = args.get("sd_model") or args.get("sd_model_name") or args.get("model")
                    cfg_scale = args.get("sd_cfg_scale") or args.get("cfg_scale")
                    if model_name or cfg_scale:
                        sd_config = SDAPIConfig(
                            model_name=str(model_name) if model_name is not None else None,
                            cfg_scale=float(cfg_scale) if cfg_scale is not None else None,
                        )
                    group = add_triangle_mosaic_background(
                        dwg=dwg,
                        W=canvas_w,
                        H=canvas_h,
                        seed_text=seed_text,
                        bg_dir=bg_dir,
                        margin=margin,
                        background_prompt=background_prompt,
                        sdapi_config=sd_config,
                    )
                    if group is not None and background_opacity is not None:
                        group.update({"opacity": background_opacity})
                    if group is not None:
                        _apply_clip(group)
                        last_element = group
                        last_background_element = group
                elif name in {
                    "vectorize_sm2",
                    "sm2_vectorize",
                    "vectorize_sm2_crosshatch",
                    "sm2_crosshatch",
                    "crosshatch_sm2",
                    "vectorize_crosshatch",
                }:
                    sd_config = None
                    model_name = args.get("sd_model") or args.get("sd_model_name") or args.get("model")
                    cfg_scale = args.get("sd_cfg_scale") or args.get("cfg_scale")
                    if model_name or cfg_scale:
                        sd_config = SDAPIConfig(
                            model_name=str(model_name) if model_name is not None else None,
                            cfg_scale=float(cfg_scale) if cfg_scale is not None else None,
                        )
                    group = add_vectorized_background_sm2_crosshatch(
                        dwg=dwg,
                        W=canvas_w,
                        H=canvas_h,
                        seed_text=seed_text,
                        bg_dir=bg_dir,
                        margin=margin,
                        n_segments=background_segments,
                        background_prompt=background_prompt,
                        sdapi_config=sd_config,
                        sm2_private_key=str(args.get("sm2_private_key"))
                        if args.get("sm2_private_key") is not None
                        else None,
                        sm2_public_key=str(args.get("sm2_public_key"))
                        if args.get("sm2_public_key") is not None
                        else None,
                        crosshatch_spacing=float(args.get("crosshatch_spacing", 6.0)),
                        crosshatch_stroke_width=float(args.get("crosshatch_stroke_width", 0.5)),
                        crosshatch_opacity=float(args.get("crosshatch_opacity", 0.45)),
                        crosshatch_alpha=float(args.get("crosshatch_alpha"))
                        if args.get("crosshatch_alpha") is not None
                        else None,
                        crosshatch_h=float(args.get("crosshatch_h"))
                        if args.get("crosshatch_h") is not None
                        else None,
                        crosshatch_s=float(args.get("crosshatch_s", 0.9)),
                        crosshatch_l=float(args.get("crosshatch_l", 0.65)),
                        crosshatch_v=float(args.get("crosshatch_v", 1.0)),
                        crosshatch_hue_range=float(args.get("crosshatch_hue_range", 0.28)),
                        transparent_threshold=int(float(args.get("transparent_threshold", 248)))
                        if args.get("transparent_threshold") is not None
                        else 248,
                        outline_stroke=str(
                            args.get("outline_stroke", args.get("crosshatch_outline_stroke", ""))
                        )
                        or None,
                        outline_stroke_width=float(
                            args.get("outline_stroke_width", args.get("crosshatch_outline_width", 0.8))
                        ),
                        outline_stroke_opacity=float(
                            args.get("outline_stroke_opacity", args.get("crosshatch_outline_opacity", 1.0))
                        ),
                        outline_stroke_linecap=str(
                            args.get("outline_stroke_linecap", args.get("crosshatch_outline_linecap", "round"))
                        ),
                        outline_stroke_linejoin=str(
                            args.get("outline_stroke_linejoin", args.get("crosshatch_outline_linejoin", "round"))
                        ),
                        crosshatch_use_mask=str(
                            args.get("crosshatch_use_mask", args.get("hatch_use_mask", "false"))
                        ).lower()
                        == "true",
                        crosshatch_flatten=str(
                            args.get("crosshatch_flatten", args.get("hatch_flatten", "true"))
                        ).lower()
                        == "true",
                        merge_similar_colors=str(
                            args.get("merge_similar_colors", args.get("merge_colors", "false"))
                        ).lower()
                        == "true",
                        merge_color_bin=int(args.get("merge_color_bin", 16)),
                        crosshatch_on_merged=str(
                            args.get("crosshatch_on_merged", args.get("hatch_on_merged", "true"))
                        ).lower()
                        == "true",
                        vectorize_mode=str(args.get("vectorize_mode", args.get("vectorize_by", "slic"))),
                        color_quantize_colors=int(args.get("color_quantize_colors"))
                        if args.get("color_quantize_colors") is not None
                        else None,
                        color_quantize_bin=int(args.get("color_quantize_bin", 16)),
                        color_quantize_dither=str(args.get("color_quantize_dither", "false")).lower()
                        == "true",
                        anime_mode=str(args.get("anime_mode", "false")).lower() == "true",
                    )
                    if group is not None and background_opacity is not None:
                        group.update({"opacity": background_opacity})
                    if group is not None:
                        _apply_clip(group)
                        last_element = group
                        last_background_element = group
                else:
                    sd_config = None
                    model_name = args.get("sd_model") or args.get("sd_model_name") or args.get("model")
                    cfg_scale = args.get("sd_cfg_scale") or args.get("cfg_scale")
                    if model_name or cfg_scale:
                        sd_config = SDAPIConfig(
                            model_name=str(model_name) if model_name is not None else None,
                            cfg_scale=float(cfg_scale) if cfg_scale is not None else None,
                        )
                    group = add_vectorized_background(
                        dwg=dwg,
                        W=canvas_w,
                        H=canvas_h,
                        seed_text=seed_text,
                        bg_dir=bg_dir,
                        margin=margin,
                        n_segments=background_segments,
                        background_prompt=background_prompt,
                        sdapi_config=sd_config,
                    )
                    if group is not None and background_opacity is not None:
                        group.update({"opacity": background_opacity})
                    if group is not None:
                        _apply_clip(group)
                        last_element = group
                        last_background_element = group

            filter_chain = [
                part.strip().lower()
                for part in filter_name.split("+")
                if part.strip()
            ] or ["vectorize"]
            for name in filter_chain:
                _apply_background_filter(name)
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
                inset_mm=float(args.get("inset_mm", 0.0)),
                outset_mm=float(args.get("outset_mm", 0.0)),
                offset_x_mm=float(args.get("offset_x_mm", 0.0)),
                offset_y_mm=float(args.get("offset_y_mm", 0.0)),
                layout=str(args.get("layout", "band")),
                palette=str(args.get("palette")) if args.get("palette") is not None else None,
                cycle_mode=str(args.get("cycle_mode", "sequential")),
                cycle_seed=str(args.get("cycle_seed", "")),
                encoding_algo=str(args.get("encoding_algo", "sha3_256")),
                packed_spacing_x_mm=float(args.get("packed_spacing_x_mm")) if args.get("packed_spacing_x_mm") is not None else None,
                packed_spacing_y_mm=float(args.get("packed_spacing_y_mm")) if args.get("packed_spacing_y_mm") is not None else None,
                packed_glyph_scale=float(args.get("packed_glyph_scale", 1.0)),
                fill_color=str(args.get("fill_color", "#111111")),
                opacity=float(args.get("opacity", 1.0)),
                case=str(args.get("case", "upper")).lower(),
                base_fill=str(args.get("base_fill", "#ffffff")) if args.get("base_fill") is not None else None,
                pattern=str(args.get("pattern", "stripes")),
                pattern_color=str(args.get("pattern_color", "#222222")),
                pattern_opacity=float(args.get("pattern_opacity", 0.35)),
            )
        elif op.op == "daemon_security":
            args = op.args
            add_daemon_security_pattern_mm(
                dwg,
                x_mm=float(args.get("x_mm", 0)),
                y_mm=float(args.get("y_mm", 0)),
                width_mm=float(args.get("width_mm", 160)),
                height_mm=float(args.get("height_mm", 60)),
                text=str(args.get("text", "LUNAMINT")),
                font_name=str(args.get("font", "Daemon Full Working")),
                font_dir=str(args.get("font_dir", "./fonts")),
                font_size_mm=float(args.get("font_size_mm", 1.2)),
                spacing_mm=float(args.get("spacing_mm", 0.6)),
                row_spacing_mm=float(args.get("row_spacing_mm")) if args.get("row_spacing_mm") is not None else None,
                angle_deg=float(args.get("angle_deg", 0.0)),
                opacity=float(args.get("opacity", 0.35)),
                color_seed=str(args.get("color_seed", "")),
                stagger=str(args.get("stagger", "true")).lower() == "true",
                density=float(args.get("density", 1.0)),
                letter_scale=float(args.get("letter_scale", 1.0)),
                hash_algo=str(args.get("hash_algo", "sha256")),
                sm2_private_key=str(args.get("sm2_private_key")) if args.get("sm2_private_key") is not None else None,
                sm2_public_key=str(args.get("sm2_public_key")) if args.get("sm2_public_key") is not None else None,
                sm4_key=str(args.get("sm4_key")) if args.get("sm4_key") is not None else None,
                render_as_shapes=str(
                    args.get("render_as_shapes", args.get("shape_text", "true"))
                ).lower()
                == "true",
            )
        elif op.op == "front_qr_border":
            args = op.args
            seed_text = str(args.get("seed_text", ""))
            serial_id = args.get("serial_id") or None
            timestamp_ms = args.get("timestamp_ms")
            inset_mm = float(args.get("inset_mm", 0.5))
            border_thickness_mm = float(args.get("border_thickness_mm", 3.0))
            add_qr_like_border_front(
                dwg,
                seed_text,
                canvas_w,
                canvas_h,
                serial_id=serial_id,
                timestamp_ms=timestamp_ms,
                inset_mm=inset_mm,
                border_thickness_mm=border_thickness_mm,
            )
        elif op.op == "front_corner_denoms":
            args = op.args
            denom = str(args.get("denomination", "100"))
            font_family = str(args.get("font_family", "Daemon Full Working"))
            add_front_corner_denoms(dwg, canvas_w, canvas_h, denom, font_family=font_family)
        elif op.op == "front_corner_decorations":
            args = op.args
            denom = str(args.get("denomination", "100"))
            timestamp = args.get("timestamp_ms") or generate_timestamp_ms_precise()
            serial_id = str(args.get("serial_id", ""))
            size = int(float(args.get("size", 100)))
            padding = int(float(args.get("padding", 75)))
            stroke_width = float(args.get("stroke_width", 1))
            add_front_corner_decorations(
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
        elif op.op == "front_center_seal":
            args = op.args
            seed_text = str(args.get("seed_text", "LUNAMINT"))
            serial_id = str(args.get("serial_id", ""))
            denom = str(args.get("denomination", "100"))
            center_radius_scale = float(args.get("center_radius_scale", 0.32))
            small_radius_scale = float(args.get("small_radius_scale", 0.25))
            text_seal_scale = float(args.get("text_seal_scale", 0.65))
            secondary_ring_scale = float(args.get("secondary_ring_scale", 0.88))
            center_seal_scale = float(args.get("center_seal_scale", 1.2))
            chinese_font = str(args.get("chinese_font", "FengGuangMingRui"))
            english_font = str(args.get("english_font", "Daemon Full Working"))
            input_image_path = str(args.get("input_image_path", ""))

            denom_value = denom_to_int(denom)
            denom_exponent = int(round(math.log10(denom_value))) if denom_value > 0 else 0
            denom_color = denomination_to_color(denom_exponent)

            center_px_radius = int(min(canvas_w, canvas_h) * center_radius_scale)
            small_radius = min(canvas_w, canvas_h) * small_radius_scale
            cx = canvas_w // 2
            cy = canvas_h // 2

            if input_image_path and os.path.exists(input_image_path):
                im = Image.open(input_image_path).convert("RGB")
            else:
                im = Image.new("RGB", (512, 512), color=(235, 235, 235))

            add_front_text_seal(
                dwg,
                cy=cy,
                radius=small_radius * text_seal_scale,
                text_left=seed_text,
                text_right=serial_id,
                denom_color=denom_color,
                inner_text="日",
                include_datetime=True,
                seed_text=seed_text,
                serial_id=serial_id,
                canvas_width=canvas_w,
                chinese_font=chinese_font,
                english_font=english_font,
            )
            add_front_secondary_ring(
                dwg,
                cx,
                cy,
                radius=center_px_radius * secondary_ring_scale,
                seed=seed_text.encode("utf-8"),
                segments=360,
                d_color=denom_color,
            )
            add_front_center_seal(dwg, im, cx, cy, center_px_radius * center_seal_scale)
        elif op.op == "front_microprint_seal":
            args = op.args
            cx = float(args.get("cx", canvas_w / 2))
            cy = float(args.get("cy", canvas_h / 2))
            radius = args.get("radius")
            repetitions = int(float(args.get("repetitions", 16)))
            text = str(args.get("text", "LUNAMINT"))

            if radius is None:
                center_px_radius = int(min(canvas_w, canvas_h) * 0.32)
                radius = int(center_px_radius * 0.7)
            else:
                radius = int(float(radius))

            add_front_chinese_microprint(
                dwg,
                int(cx),
                int(cy),
                int(radius),
                text=text,
                repetitions=repetitions,
            )
        elif op.op == "front_center_text":
            args = op.args
            title = str(args.get("title", "灵国国库"))
            subtitle = str(args.get("subtitle", "天圆地方"))
            denom = str(args.get("denomination", "100"))
            title_font = str(args.get("title_font", "FengGuangMingRui"))
            subtitle_font = str(args.get("subtitle_font", "FengGuangMingRui"))
            denom_value = denom_to_int(denom)
            denom_exponent = int(round(math.log10(denom_value))) if denom_value > 0 else 0
            denom_color = str(args.get("denom_color", denomination_to_color(denom_exponent)))
            add_front_center_text(
                dwg,
                canvas_w,
                canvas_h,
                title,
                subtitle,
                denom_color=denom_color,
                title_font=title_font,
                phrase_font=subtitle_font,
            )
        elif op.op == "front_color_qr":
            args = op.args
            url = str(args.get("url", ""))
            stamp_width = int(float(args.get("stamp_width", 60)))
            stamp_height = int(float(args.get("stamp_height", 60)))
            rows = int(float(args.get("rows", 6)))
            side = str(args.get("side", "both"))
            add_roygbiv_qr_style(
                dwg,
                W=canvas_w,
                H=canvas_h,
                url=url,
                stamp_width=stamp_width,
                stamp_height=stamp_height,
                rows=rows,
                side=side,
            )
        elif op.op == "front_aztec":
            args = op.args
            url = str(args.get("url", ""))
            denom = str(args.get("denomination", "100"))
            cx = float(args.get("cx", canvas_w / 2))
            cy = float(args.get("cy", canvas_h / 2))
            scale = float(args.get("scale", 3))
            border = float(args.get("border", 12))
            rotation = float(args.get("rotation", 0))
            border_opacity = float(args.get("border_opacity", 0.5))

            matrix = safe_make_matrix(url)
            if matrix is not None:
                denom_value = denom_to_int(denom)
                denom_exponent = int(round(math.log10(denom_value))) if denom_value > 0 else 0
                add_colored_aztec_to_canvas(
                    dwg,
                    cx=cx,
                    cy=cy,
                    matrix=matrix,
                    scale=scale,
                    border=border,
                    denom_exponent=denom_exponent,
                    rotation=rotation,
                    border_opacity=border_opacity,
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

    def _extract_svg_inner(svg_text: str) -> tuple[int, int, str]:
        svg_start = svg_text.find("<svg")
        if svg_start == -1:
            return -1, -1, ""
        start = svg_text.find(">", svg_start)
        end = svg_text.rfind("</svg>")
        if start == -1 or end == -1 or end <= start:
            return -1, -1, ""
        inner = svg_text[start + 1 : end]
        return start, end, inner

    def _apply_document_mask(svg_text: str, op: DrawOp) -> str:
        if op.op not in {"mask_circle", "cutout_circle"}:
            return svg_text
        if "mask_doc" in svg_text or "clip_doc" in svg_text:
            return svg_text
        cx = float(op.args.get("cx", 0))
        cy = float(op.args.get("cy", 0))
        r = float(op.args.get("r", 0))
        if r <= 0:
            return svg_text
        svg_tag_match = re.search(r"<svg[^>]*>", svg_text, re.IGNORECASE)
        svg_tag = svg_tag_match.group(0) if svg_tag_match else ""
        viewbox_match = re.search(r"viewBox=\"([^\"]+)\"", svg_tag, re.IGNORECASE)
        width_match = re.search(r"width=\"([^\"]+)\"", svg_tag, re.IGNORECASE)
        height_match = re.search(r"height=\"([^\"]+)\"", svg_tag, re.IGNORECASE)

        def _parse_svg_number(value: str) -> Optional[float]:
            if not value:
                return None
            m = re.match(r"\s*([0-9]+(?:\.[0-9]+)?)", value)
            if not m:
                return None
            try:
                return float(m.group(1))
            except ValueError:
                return None

        svg_w = None
        svg_h = None
        if viewbox_match:
            parts = viewbox_match.group(1).replace(",", " ").split()
            if len(parts) == 4:
                svg_w = _parse_svg_number(parts[2])
                svg_h = _parse_svg_number(parts[3])
        if svg_w is None and width_match:
            svg_w = _parse_svg_number(width_match.group(1))
        if svg_h is None and height_match:
            svg_h = _parse_svg_number(height_match.group(1))
        invert = str(op.args.get("invert", "false")).lower() == "true"
        flatten_lines = str(op.args.get("flatten_lines", op.args.get("flatten", "true"))).lower() == "true"
        mask_id = "mask_doc"
        clip_id = "clip_doc"
        start, end, inner = _extract_svg_inner(svg_text)
        if start == -1 or end == -1:
            return svg_text
        if op.op == "mask_circle" and flatten_lines:
            def _clip_segment_to_circle(
                x1: float,
                y1: float,
                x2: float,
                y2: float,
                cx: float,
                cy: float,
                r: float,
                invert: bool,
            ) -> list[tuple[float, float, float, float]]:
                dx = x2 - x1
                dy = y2 - y1
                a = dx * dx + dy * dy
                if a == 0:
                    return []
                b = 2.0 * (dx * (x1 - cx) + dy * (y1 - cy))
                c = (x1 - cx) * (x1 - cx) + (y1 - cy) * (y1 - cy) - r * r
                disc = b * b - 4.0 * a * c
                ts = [0.0, 1.0]
                if disc >= 0.0:
                    sqrt_disc = math.sqrt(disc)
                    t1 = (-b - sqrt_disc) / (2.0 * a)
                    t2 = (-b + sqrt_disc) / (2.0 * a)
                    if 0.0 <= t1 <= 1.0:
                        ts.append(t1)
                    if 0.0 <= t2 <= 1.0:
                        ts.append(t2)
                ts = sorted(set(ts))

                def _inside(t: float) -> bool:
                    px = x1 + dx * t
                    py = y1 + dy * t
                    return (px - cx) * (px - cx) + (py - cy) * (py - cy) <= r * r + 1e-9

                segments: list[tuple[float, float, float, float]] = []
                for i in range(len(ts) - 1):
                    t0 = ts[i]
                    t1 = ts[i + 1]
                    if t1 - t0 <= 1e-9:
                        continue
                    mid = (t0 + t1) * 0.5
                    inside = _inside(mid)
                    keep = not inside if invert else inside
                    if keep:
                        sx1 = x1 + dx * t0
                        sy1 = y1 + dy * t0
                        sx2 = x1 + dx * t1
                        sy2 = y1 + dy * t1
                        if abs(sx1 - sx2) + abs(sy1 - sy2) > 1e-6:
                            segments.append((sx1, sy1, sx2, sy2))
                return segments

            def _clip_lines_to_circle(inner_svg: str) -> str:
                if r <= 0:
                    return inner_svg
                line_pattern = re.compile(r"<line\b[^>]*?/?>", re.IGNORECASE)
                attr_pattern = re.compile(r'(\w+)\s*=\s*"([^"]*)"')

                def _repl(match: re.Match) -> str:
                    tag = match.group(0)
                    attrs = attr_pattern.findall(tag)
                    if not attrs:
                        return tag
                    attr_map = {k: v for k, v in attrs}
                    if not all(k in attr_map for k in ("x1", "y1", "x2", "y2")):
                        return tag
                    try:
                        x1 = float(attr_map["x1"])
                        y1 = float(attr_map["y1"])
                        x2 = float(attr_map["x2"])
                        y2 = float(attr_map["y2"])
                    except ValueError:
                        return tag
                    segments = _clip_segment_to_circle(x1, y1, x2, y2, cx, cy, r, invert)
                    if not segments:
                        return ""
                    rendered = []
                    for seg in segments:
                        seg_map = dict(attr_map)
                        seg_map["x1"] = f"{seg[0]:.2f}"
                        seg_map["y1"] = f"{seg[1]:.2f}"
                        seg_map["x2"] = f"{seg[2]:.2f}"
                        seg_map["y2"] = f"{seg[3]:.2f}"
                        parts = []
                        for k, v in attrs:
                            parts.append(f'{k}="{seg_map[k]}"')
                        rendered.append("<line " + " ".join(parts) + " />")
                    return "".join(rendered)

                return line_pattern.sub(_repl, inner_svg)

            inner = _clip_lines_to_circle(inner)
        defs = ""
        if op.op == "mask_circle":
            base_color = "#ffffff" if invert else "#000000"
            circle_color = "#000000" if invert else "#ffffff"
            rect_width = f"{svg_w}" if svg_w is not None else "100%"
            rect_height = f"{svg_h}" if svg_h is not None else "100%"
            defs = (
                f"<defs><mask id=\"{mask_id}\" maskUnits=\"userSpaceOnUse\" maskContentUnits=\"userSpaceOnUse\">"
                f"<rect x=\"0\" y=\"0\" width=\"{rect_width}\" height=\"{rect_height}\" fill=\"{base_color}\"/>"
                f"<circle cx=\"{cx}\" cy=\"{cy}\" r=\"{r}\" fill=\"{circle_color}\"/>"
                "</mask></defs>"
            )
            wrapped = f"<g mask=\"url(#{mask_id})\">{inner}</g>"
        else:
            defs = (
                f"<defs><clipPath id=\"{clip_id}\" clipPathUnits=\"userSpaceOnUse\">"
                f"<circle cx=\"{cx}\" cy=\"{cy}\" r=\"{r}\"/>"
                "</clipPath></defs>"
            )
            wrapped = f"<g clip-path=\"url(#{clip_id})\">{inner}</g>"
        return svg_text[: start + 1] + defs + wrapped + svg_text[end:]

    if back_ops:
        overlay_ops = [op for op in program.ops if op.op != "back_banknote"]
        doc_mask_ops = [
            op
            for op in overlay_ops
            if op.op in {"mask_circle", "cutout_circle"}
            and str(op.args.get("target", "")).lower() == "document"
        ]
        overlay_ops = [
            op
            for op in overlay_ops
            if op not in doc_mask_ops
        ]
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
            _, _, inner = _extract_svg_inner(overlay_svg)
            if not inner:
                inner = overlay_svg
            svg_text = out_path.read_text(encoding="utf-8")
            out_path.write_text(svg_text.replace("</svg>", inner + "</svg>"), encoding="utf-8")
        if doc_mask_ops:
            svg_text = out_path.read_text(encoding="utf-8")
            svg_text = _apply_document_mask(svg_text, doc_mask_ops[-1])
            out_path.write_text(svg_text, encoding="utf-8")
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

        doc_mask_ops = [
            op
            for op in overlay_ops
            if op.op in {"mask_circle", "cutout_circle"}
            and str(op.args.get("target", "")).lower() == "document"
        ]
        overlay_ops = [
            op
            for op in overlay_ops
            if op not in doc_mask_ops
        ]

        if overlay_ops:
            W = int(float(params["width_mm"]) * 300 / 25.4)
            H = int(float(params["height_mm"]) * 300 / 25.4)
            overlay = svgwrite.Drawing(size=(W, H), viewBox=f"0 0 {W} {H}")
            _render_ops(overlay, overlay_ops, W, H)
            overlay_svg = overlay.tostring()
            _, _, inner = _extract_svg_inner(overlay_svg)
            if not inner:
                inner = overlay_svg
            svg_text = out_path.read_text(encoding="utf-8")
            out_path.write_text(svg_text.replace("</svg>", inner + "</svg>"), encoding="utf-8")
        if doc_mask_ops:
            svg_text = out_path.read_text(encoding="utf-8")
            svg_text = _apply_document_mask(svg_text, doc_mask_ops[-1])
            out_path.write_text(svg_text, encoding="utf-8")
        return out_path

    dwg = svgwrite.Drawing(
        str(out_path),
        size=(program.state.width, program.state.height),
        viewBox=f"0 0 {program.state.width} {program.state.height}",
    )
    dwg.update({"shape-rendering": "geometricPrecision", "text-rendering": "geometricPrecision"})
    bg = program.state.background
    if bg and str(bg).strip().lower() not in {"none", "transparent"}:
        fill, fill_opacity = _split_hex_alpha(str(bg))
        rect_kwargs = {"insert": (0, 0), "size": (program.state.width, program.state.height), "fill": fill}
        if fill_opacity is not None:
            rect_kwargs["fill_opacity"] = fill_opacity
        dwg.add(dwg.rect(**rect_kwargs))
    doc_mask_ops = [
        op
        for op in program.ops
        if op.op in {"mask_circle", "cutout_circle"}
        and str(op.args.get("target", "")).lower() == "document"
    ]
    render_ops = [op for op in program.ops if op not in doc_mask_ops]
    _render_ops(dwg, render_ops, program.state.width, program.state.height)
    dwg.save()
    if doc_mask_ops:
        svg_text = out_path.read_text(encoding="utf-8")
        svg_text = _apply_document_mask(svg_text, doc_mask_ops[-1])
        out_path.write_text(svg_text, encoding="utf-8")
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

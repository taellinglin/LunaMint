"""ASCII stamp widgets (image → glyph mosaic)."""
from __future__ import annotations

import base64
import io
import os
from dataclasses import dataclass
from typing import Iterable, Optional, Sequence

from PIL import Image, ImageFont
import requests

import svgwrite

from .config import SDAPIConfig, sdapi_txt2img
from .measure import mm_to_px


@dataclass
class AsciiStampOptions:
    font_name: str = "Daemon Full Working"
    font_dir: str = "./fonts"
    font_size_mm: float = 1.2
    charset: str = "abcdefghijklmnopqrstuvwxyz"
    fill: str = "#111111"
    opacity: float = 0.65
    invert: bool = False
    mask_threshold: int = 230


@dataclass
class AsciiStampLayer:
    min_value: int = 0
    max_value: int = 255
    charset: str = "abcdefghijklmnopqrstuvwxyz"
    fill: str = "#111111"
    opacity: float = 0.7


@dataclass
class AsciiStampMaskOptions:
    font_name: str = "Daemon Full Working"
    font_dir: str = "./fonts"
    font_size_mm: float = 1.0
    invert: bool = False
    snap_grid_px: float = 0.0
    layers: Sequence[AsciiStampLayer] = (
        AsciiStampLayer(0, 85, "@#$%", "#0b0b0b", 0.9),
        AsciiStampLayer(86, 170, "*+=-", "#333333", 0.7),
        AsciiStampLayer(171, 255, ".:;", "#666666", 0.5),
    )


def _find_font_path(font_name: str, font_dir: str) -> Optional[str]:
    if font_name and os.path.isfile(font_name):
        return font_name
    if not os.path.isdir(font_dir):
        return None
    target = font_name.lower().replace(" ", "")
    for fn in os.listdir(font_dir):
        if not fn.lower().endswith((".ttf", ".otf")):
            continue
        name = os.path.splitext(fn)[0].lower().replace(" ", "")
        if target and target in name:
            return os.path.join(font_dir, fn)
    return None


def _load_font(font_name: str, font_dir: str, size_px: float) -> ImageFont.FreeTypeFont:
    font_path = _find_font_path(font_name, font_dir)
    if not font_path:
        raise FileNotFoundError(f"Font '{font_name}' not found in {font_dir}")
    return ImageFont.truetype(font_path, int(max(1, round(size_px))))


def _pixel_to_char(value: int, charset: str, invert: bool) -> str:
    if not charset:
        return ""
    idx = int((value / 255) * (len(charset) - 1))
    if invert:
        idx = (len(charset) - 1) - idx
    return charset[idx]


def _ascii_lines(img: Image.Image, cols: int, rows: int, charset: str, invert: bool, mask_threshold: int) -> Iterable[str]:
    gray = img.convert("L").resize((cols, rows))
    pixels = gray.load()
    for y in range(rows):
        line = []
        for x in range(cols):
            v = pixels[x, y]
            if v >= mask_threshold:
                line.append(" ")
            else:
                line.append(_pixel_to_char(v, charset, invert))
        yield "".join(line)


def _ascii_lines_ranged(
    img: Image.Image,
    cols: int,
    rows: int,
    charset: str,
    invert: bool,
    min_value: int,
    max_value: int,
) -> Iterable[str]:
    gray = img.convert("L").resize((cols, rows))
    pixels = gray.load()
    for y in range(rows):
        line = []
        for x in range(cols):
            v = pixels[x, y]
            if v < min_value or v > max_value:
                line.append(" ")
            else:
                line.append(_pixel_to_char(v, charset, invert))
        yield "".join(line)


def add_ascii_stamp_from_image_mm(
    dwg: svgwrite.Drawing,
    image: Image.Image,
    x_mm: float,
    y_mm: float,
    width_mm: float,
    height_mm: float,
    options: Optional[AsciiStampOptions] = None,
    dpi: float = 300.0,
) -> svgwrite.container.Group:
    opts = options or AsciiStampOptions()
    x = mm_to_px(x_mm, dpi)
    y = mm_to_px(y_mm, dpi)
    width = mm_to_px(width_mm, dpi)
    height = mm_to_px(height_mm, dpi)
    font_size_px = mm_to_px(opts.font_size_mm, dpi)
    font = _load_font(opts.font_name, opts.font_dir, font_size_px)

    ascent, descent = font.getmetrics()
    line_height = max(1, ascent + descent)
    sample_box = font.getbbox("M")
    avg_width = max(1, sample_box[2] - sample_box[0])

    cols = max(1, int(width / avg_width))
    rows = max(1, int(height / line_height))

    group = dwg.g(opacity=opts.opacity)
    for row_idx, line in enumerate(_ascii_lines(image, cols, rows, opts.charset, opts.invert, opts.mask_threshold)):
        cursor_x = x
        baseline_y = y + row_idx * line_height + ascent
        for ch in line:
            if ch == " ":
                cursor_x += avg_width
                continue
            box = font.getbbox(ch)
            if not box:
                cursor_x += avg_width
                continue
            x0, _y0, x1, _y1 = box
            advance = max(1, x1 - x0)
            draw_x = cursor_x - x0
            group.add(
                dwg.text(
                    ch,
                    insert=(draw_x, baseline_y),
                    font_size=font_size_px,
                    font_family=opts.font_name,
                    fill=opts.fill,
                )
            )
            cursor_x += advance
    dwg.add(group)
    return group


def add_ascii_stamp_masked_layers_from_image_mm(
    dwg: svgwrite.Drawing,
    image: Image.Image,
    x_mm: float,
    y_mm: float,
    width_mm: float,
    height_mm: float,
    options: Optional[AsciiStampMaskOptions] = None,
    dpi: float = 300.0,
) -> svgwrite.container.Group:
    opts = options or AsciiStampMaskOptions()
    x = mm_to_px(x_mm, dpi)
    y = mm_to_px(y_mm, dpi)
    width = mm_to_px(width_mm, dpi)
    height = mm_to_px(height_mm, dpi)
    font_size_px = mm_to_px(opts.font_size_mm, dpi)
    font = _load_font(opts.font_name, opts.font_dir, font_size_px)

    ascent, descent = font.getmetrics()
    line_height = max(1, ascent + descent)
    sample_box = font.getbbox("M")
    avg_width = max(1, sample_box[2] - sample_box[0])

    cols = max(1, int(width / avg_width))
    rows = max(1, int(height / line_height))

    group = dwg.g()
    for layer in opts.layers:
        layer_group = dwg.g(opacity=layer.opacity)
        for row_idx, line in enumerate(
            _ascii_lines_ranged(
                image,
                cols,
                rows,
                layer.charset,
                opts.invert,
                int(layer.min_value),
                int(layer.max_value),
            )
        ):
            cursor_x = x
            baseline_y = y + row_idx * line_height + ascent
            for ch in line:
                if ch == " ":
                    cursor_x += avg_width
                    continue
                box = font.getbbox(ch)
                if not box:
                    cursor_x += avg_width
                    continue
                x0, _y0, x1, _y1 = box
                advance = max(1, x1 - x0)
                draw_x = cursor_x - x0
                if opts.snap_grid_px > 0:
                    draw_x = snap_px(draw_x, opts.snap_grid_px)
                    baseline_y = snap_px(baseline_y, opts.snap_grid_px)
                layer_group.add(
                    dwg.text(
                        ch,
                        insert=(draw_x, baseline_y),
                        font_size=font_size_px,
                        font_family=opts.font_name,
                        fill=layer.fill,
                    )
                )
                cursor_x += advance
        group.add(layer_group)

    dwg.add(group)
    return group


def add_ascii_stamp_from_file_mm(
    dwg: svgwrite.Drawing,
    image_path: str,
    x_mm: float,
    y_mm: float,
    width_mm: float,
    height_mm: float,
    options: Optional[AsciiStampOptions] = None,
    dpi: float = 300.0,
) -> svgwrite.container.Group:
    img = Image.open(image_path).convert("RGB")
    return add_ascii_stamp_from_image_mm(dwg, img, x_mm, y_mm, width_mm, height_mm, options, dpi)


def add_ascii_stamp_masked_layers_from_file_mm(
    dwg: svgwrite.Drawing,
    image_path: str,
    x_mm: float,
    y_mm: float,
    width_mm: float,
    height_mm: float,
    options: Optional[AsciiStampMaskOptions] = None,
    dpi: float = 300.0,
) -> svgwrite.container.Group:
    img = Image.open(image_path).convert("RGB")
    return add_ascii_stamp_masked_layers_from_image_mm(dwg, img, x_mm, y_mm, width_mm, height_mm, options, dpi)


def add_ascii_stamp_from_prompt_mm(
    dwg: svgwrite.Drawing,
    prompt: str,
    x_mm: float,
    y_mm: float,
    width_mm: float,
    height_mm: float,
    negative_prompt: str = "text, words, watermark, blurry",
    steps: int = 20,
    cfg_scale: float = 7.5,
    sampler_name: str = "Euler a",
    seed: int | None = None,
    options: Optional[AsciiStampOptions] = None,
    config: Optional[SDAPIConfig] = None,
    dpi: float = 300.0,
) -> svgwrite.container.Group:
    cfg = config or SDAPIConfig()
    try:
        requests.get(cfg.progress_url, timeout=2)
    except Exception:
        return dwg.g()

    width_px = int(mm_to_px(width_mm, dpi))
    height_px = int(mm_to_px(height_mm, dpi))

    payload = {
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "width": width_px,
        "height": height_px,
        "steps": steps,
        "cfg_scale": cfg_scale,
        "sampler_name": sampler_name,
        "batch_size": 1,
        "n_iter": 1,
        "restore_faces": False,
        "tiling": False,
    }
    if seed is not None:
        payload["seed"] = int(seed)

    result = sdapi_txt2img(payload, config=cfg)
    images = result.get("images", [])
    if not images:
        raise RuntimeError("SDAPI returned no images for ASCII stamp")
    raw = base64.b64decode(images[0])
    img = Image.open(io.BytesIO(raw)).convert("RGB")
    return add_ascii_stamp_from_image_mm(dwg, img, x_mm, y_mm, width_mm, height_mm, options, dpi)

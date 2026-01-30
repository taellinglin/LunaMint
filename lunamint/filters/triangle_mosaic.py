"""Triangle mosaic filter for SDAPI-generated backgrounds."""
from __future__ import annotations

import os
import random
from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np
import svgwrite
from PIL import Image

from .vectorize import generate_sd_background
from ..widgets.config import SDAPIConfig


@dataclass
class TriangleMosaicConfig:
    base_cell: int = 32
    min_cell: int = 8
    max_depth: int = 4
    variance_threshold: float = 220.0
    opacity: float = 0.8


def _avg_color(arr: np.ndarray) -> Tuple[int, int, int]:
    if arr.size == 0:
        return (240, 240, 240)
    avg = np.mean(arr.reshape(-1, 3), axis=0)
    return int(avg[0]), int(avg[1]), int(avg[2])


def _variance(arr: np.ndarray) -> float:
    if arr.size == 0:
        return 0.0
    return float(np.var(arr.reshape(-1, 3)))


def _tint(color: Tuple[int, int, int], factor: float) -> Tuple[int, int, int]:
    r, g, b = color
    return (
        max(0, min(255, int(r * factor))),
        max(0, min(255, int(g * factor))),
        max(0, min(255, int(b * factor))),
    )


def _draw_cell(
    group: svgwrite.container.Group,
    x: float,
    y: float,
    size: float,
    color: Tuple[int, int, int],
    flip: bool,
) -> None:
    c1 = svgwrite.rgb(*_tint(color, 1.0))
    c2 = svgwrite.rgb(*_tint(color, 0.85))
    if flip:
        points_a = [(x, y), (x + size, y), (x + size, y + size)]
        points_b = [(x, y), (x, y + size), (x + size, y + size)]
    else:
        points_a = [(x, y), (x + size, y), (x, y + size)]
        points_b = [(x + size, y), (x + size, y + size), (x, y + size)]
    group.add(svgwrite.shapes.Polygon(points=points_a, fill=c1, stroke="none"))
    group.add(svgwrite.shapes.Polygon(points=points_b, fill=c2, stroke="none"))


def _subdivide(
    group: svgwrite.container.Group,
    arr: np.ndarray,
    x: int,
    y: int,
    size: int,
    depth: int,
    cfg: TriangleMosaicConfig,
    offset_x: int,
    offset_y: int,
    seed: bytes,
) -> None:
    region = arr[y : y + size, x : x + size]
    variance = _variance(region)
    if depth >= cfg.max_depth or size <= cfg.min_cell or variance <= cfg.variance_threshold:
        color = _avg_color(region)
        flip = seed[(x + y) % len(seed)] % 2 == 0
        _draw_cell(group, x + offset_x, y + offset_y, size, color, flip)
        return

    half = size // 2
    if half < cfg.min_cell:
        color = _avg_color(region)
        flip = seed[(x + y + depth) % len(seed)] % 2 == 0
        _draw_cell(group, x + offset_x, y + offset_y, size, color, flip)
        return

    _subdivide(group, arr, x, y, half, depth + 1, cfg, offset_x, offset_y, seed)
    _subdivide(group, arr, x + half, y, half, depth + 1, cfg, offset_x, offset_y, seed)
    _subdivide(group, arr, x, y + half, half, depth + 1, cfg, offset_x, offset_y, seed)
    _subdivide(group, arr, x + half, y + half, half, depth + 1, cfg, offset_x, offset_y, seed)


def add_triangle_mosaic_background(
    dwg,
    W: int,
    H: int,
    seed_text: str = "",
    bg_dir: str = "./backgrounds",
    margin: int = 60,
    background_prompt: str = "",
    denomination=None,
    prompt_file: str = "./background_prompt.txt",
    negative_prompt_file: str = "negative_prompt.txt",
    sdapi_config: Optional[SDAPIConfig] = None,
    config: Optional[TriangleMosaicConfig] = None,
):
    cfg = config or TriangleMosaicConfig()

    if not background_prompt:
        if os.path.exists(prompt_file):
            with open(prompt_file, "r", encoding="utf-8") as f:
                background_prompt = f.read().strip()
        else:
            background_prompt = "kawaii oekaki Chinese DMT Studio Ghibli style banknote background"

    background_path = generate_sd_background(
        prompt=background_prompt,
        width=W - 2 * margin,
        height=H - 2 * margin,
        save_path=bg_dir,
        seed_text=seed_text,
        denomination=denomination,
        negative_prompt_file=negative_prompt_file,
        sdapi_config=sdapi_config,
    )

    if not background_path or not os.path.exists(background_path):
        files = [f for f in os.listdir(bg_dir) if f.lower().endswith((".png", ".jpg", ".jpeg"))]
        if files:
            background_path = os.path.join(bg_dir, random.choice(files))
        else:
            dwg.add(dwg.rect(insert=(0, 0), size=(W, H), fill="#f0f0f0"))
            return None

    img = Image.open(background_path).convert("RGB")
    img = img.resize((W - 2 * margin, H - 2 * margin), Image.LANCZOS)
    arr = np.array(img)

    group = dwg.g(opacity=cfg.opacity)
    seed = (seed_text or "lunamint").encode("utf-8")

    size = cfg.base_cell
    max_size = min(arr.shape[0], arr.shape[1])
    while size < max_size:
        size *= 2
    size = min(size, max_size)

    for y in range(0, arr.shape[0], cfg.base_cell):
        for x in range(0, arr.shape[1], cfg.base_cell):
            cell_size = min(cfg.base_cell, arr.shape[1] - x, arr.shape[0] - y)
            _subdivide(
                group,
                arr,
                x,
                y,
                cell_size,
                0,
                cfg,
                margin,
                margin,
                seed,
            )

    dwg.add(group)
    return group

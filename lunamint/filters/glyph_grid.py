"""Glyph grid filter for SDAPI-generated backgrounds."""
from __future__ import annotations

import os
import random
import time
from dataclasses import dataclass, field
from typing import Optional

import svgwrite
from PIL import Image

from .vectorize import generate_sd_background
from ..widgets.config import SDAPIConfig
from ..widgets.glyph_grid import add_glyph_grid_from_image_mm, GlyphGridOptions


@dataclass
class GlyphGridConfig:
    options: GlyphGridOptions = field(default_factory=GlyphGridOptions)


def add_glyph_grid_background(
    dwg: svgwrite.Drawing,
    W: int,
    H: int,
    seed_text: str = "",
    bg_dir: str = "./backgrounds",
    margin: int = 30,
    background_prompt: str = "",
    denomination=None,
    prompt_file: str = "./background_prompt.txt",
    negative_prompt_file: str = "negative_prompt.txt",
    sdapi_config: Optional[SDAPIConfig] = None,
    config: Optional[GlyphGridConfig] = None,
):
    cfg = config or GlyphGridConfig()

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

    max_retries = 10
    retry_delay = 0.5
    img = None
    for attempt in range(max_retries):
        try:
            with Image.open(background_path) as test_img:
                test_img.verify()
            img = Image.open(background_path).convert("RGB")
            break
        except Exception:
            if attempt == max_retries - 1:
                dwg.add(dwg.rect(insert=(0, 0), size=(W, H), fill="#f0f0f0"))
                return None
            time.sleep(retry_delay)

    if img is None:
        dwg.add(dwg.rect(insert=(0, 0), size=(W, H), fill="#f0f0f0"))
        return None

    px_to_mm = 25.4 / cfg.options.dpi
    x_mm = margin * px_to_mm
    y_mm = margin * px_to_mm
    width_mm = max(1.0, (W - 2 * margin) * px_to_mm)
    height_mm = max(1.0, (H - 2 * margin) * px_to_mm)

    return add_glyph_grid_from_image_mm(
        dwg=dwg,
        image_path=background_path,
        x_mm=x_mm,
        y_mm=y_mm,
        width_mm=width_mm,
        height_mm=height_mm,
        options=cfg.options,
        dpi=cfg.options.dpi,
    )

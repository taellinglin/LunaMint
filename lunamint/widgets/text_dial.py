"""Text dial widgets (concentric text rings)."""
from __future__ import annotations

import hashlib
import math
from pathlib import Path
from typing import Iterable, Optional

import svgwrite

from .measure import mm_to_px


def _iter_ring_text(source: str, max_chars: int) -> Iterable[str]:
    if not source:
        return [""]
    text = source.replace("\n", " ").strip()
    if not text:
        return [""]
    chunks = []
    idx = 0
    while idx < len(text):
        chunks.append(text[idx : idx + max_chars])
        idx += max_chars
    return chunks


def _load_text_from_file(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def add_text_dial_mm(
    dwg: svgwrite.Drawing,
    cx_mm: float,
    cy_mm: float,
    radius_mm: float,
    text: str = "LUNAMINT",
    text_file: Optional[str] = None,
    rings: int = 6,
    font_family: str = "Daemon Full Working",
    font_size_mm: float = 1.1,
    stroke: str = "#111111",
    stroke_width_mm: float = 0.08,
    fill: str = "#111111",
    opacity: float = 0.6,
    encoding_seed: Optional[str] = None,
    dpi: float = 300.0,
) -> svgwrite.container.Group:
    """Draw concentric text rings. Optional file input overrides text.

    Rings are sized with a deterministic encoding seeded by `encoding_seed`.
    """
    if text_file:
        text = _load_text_from_file(text_file)

    cx = mm_to_px(cx_mm, dpi)
    cy = mm_to_px(cy_mm, dpi)
    radius = mm_to_px(radius_mm, dpi)
    font_size = mm_to_px(font_size_mm, dpi)
    stroke_width = mm_to_px(stroke_width_mm, dpi)

    seed = encoding_seed or text or "LUNAMINT"
    digest = hashlib.sha3_256(seed.encode("utf-8")).digest()

    group = dwg.g(opacity=opacity)
    max_chars = max(8, int(radius / max(1, font_size)))
    ring_texts = list(_iter_ring_text(text, max_chars))

    for ring_idx in range(rings):
        ratio = (ring_idx + 1) / (rings + 1)
        wobble = (digest[ring_idx % len(digest)] / 255.0) * 0.08
        ring_radius = radius * (0.25 + ratio * (0.75 - wobble))

        ring_text = ring_texts[ring_idx % len(ring_texts)]
        if not ring_text:
            continue
        chars = len(ring_text)
        angle_step = 360.0 / max(1, chars)

        for i, ch in enumerate(ring_text):
            angle = math.radians(i * angle_step - 90)
            x = cx + ring_radius * math.cos(angle)
            y = cy + ring_radius * math.sin(angle)
            rotate = math.degrees(angle) + 90
            group.add(
                dwg.text(
                    ch,
                    insert=(x, y),
                    text_anchor="middle",
                    font_size=font_size,
                    font_family=font_family,
                    fill=fill,
                    stroke=stroke,
                    stroke_width=stroke_width,
                    transform=f"rotate({rotate},{x},{y})",
                )
            )

    dwg.add(group)
    return group

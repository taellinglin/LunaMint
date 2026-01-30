"""Security thread widget."""
from __future__ import annotations

import svgwrite

from .measure import mm_to_px


def add_security_thread_mm(
    dwg: svgwrite.Drawing,
    x_mm: float,
    y_mm: float,
    height_mm: float,
    width_mm: float = 1.5,
    color: str = "#111111",
    opacity: float = 0.25,
    microtext: str = "LUNAMINT",
    microtext_size_mm: float = 0.9,
    microtext_spacing_mm: float = 3.0,
    font_family: str = "Daemon Full Working",
    dpi: float = 300.0,
) -> svgwrite.container.Group:
    x = mm_to_px(x_mm, dpi)
    y = mm_to_px(y_mm, dpi)
    width = mm_to_px(width_mm, dpi)
    height = mm_to_px(height_mm, dpi)

    group = dwg.g(opacity=opacity)
    group.add(dwg.rect(insert=(x, y), size=(width, height), fill=color))

    if microtext:
        text_size = mm_to_px(microtext_size_mm, dpi)
        spacing = mm_to_px(microtext_spacing_mm, dpi)
        cursor = y + spacing
        while cursor < y + height - spacing:
            group.add(
                dwg.text(
                    microtext,
                    insert=(x + width / 2, cursor),
                    text_anchor="middle",
                    font_size=text_size,
                    font_family=font_family,
                    fill="#ffffff",
                    transform=f"rotate(-90,{x + width / 2},{cursor})",
                )
            )
            cursor += spacing

    dwg.add(group)
    return group

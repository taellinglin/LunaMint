"""QR/Aztec rendering helpers (shared by front/back)."""
from __future__ import annotations

import hashlib
from typing import Optional

try:
    import segno
    SEGNO_AVAILABLE = True
except Exception:
    segno = None
    SEGNO_AVAILABLE = False

try:
    from aztec import aztec_matrix_from_segno, build_colored_aztec_svg
    AZTEC_AVAILABLE = True
except Exception:
    aztec_matrix_from_segno = None
    build_colored_aztec_svg = None
    AZTEC_AVAILABLE = False


def denomination_to_color(denom_exponent: int) -> str:
    """Map denomination exponent (0-8) to a color in a 9-color spectrum."""
    spectrum = [
        "#FF0000",
        "#FF7F00",
        "#FFFF00",
        "#00FF00",
        "#00FFFF",
        "#0000FF",
        "#4B0082",
        "#8F00FF",
        "#FF00FF",
    ]
    idx = max(0, min(denom_exponent, len(spectrum) - 1))
    return spectrum[idx]


def safe_make_matrix(data: str):
    if not SEGNO_AVAILABLE:
        return None
    return segno.make(data).matrix


def add_colored_aztec_to_canvas(
    dwg,
    cx,
    cy,
    matrix,
    denom_exponent,
    scale=12,
    border=12,
    rotation=0,
    border_opacity=0.5,
):
    if matrix is None:
        return dwg
    nrows = len(matrix)
    ncols = len(matrix[0])
    qr_size = ncols * scale
    border_color = denomination_to_color(denom_exponent)

    qr_group = dwg.g(transform=f"rotate({rotation},{cx},{cy})")
    qr_group.add(
        dwg.rect(
            insert=(cx - (qr_size / 2 + border), cy - (qr_size / 2 + border)),
            size=(qr_size + 2 * border, qr_size + 2 * border),
            fill=border_color,
            opacity=border_opacity,
        )
    )
    qr_group.add(
        dwg.rect(
            insert=(cx - qr_size / 2, cy - qr_size / 2),
            size=(qr_size, qr_size),
            fill="white",
            opacity=border_opacity,
        )
    )
    for r in range(nrows):
        for c in range(ncols):
            if matrix[r][c]:
                x = cx - qr_size / 2 + c * scale
                y = cy - qr_size / 2 + r * scale
                qr_group.add(dwg.rect(insert=(x, y), size=(scale, scale), fill="black"))

    dwg.add(qr_group)
    return dwg


def add_roygbiv_qr_style(
    dwg,
    W: int,
    H: int,
    url: str = "https://linglin.art",
    stamp_width: int = 40,
    stamp_height: int = 40,
    rows: int = 3,
    side: str = "both",
):
    colors = ["#FF0000", "#FF7F00", "#FFFF00", "#00FF00", "#0000FF", "#4B0082", "#8B00FF"]
    n_colors = len(colors)
    hash_bytes = hashlib.sha3_512(url.encode("utf-8")).digest()
    cols = stamp_width // (stamp_width // rows)
    bar_w = stamp_width / cols
    bar_h = stamp_height / rows
    bar_colors = [colors[b % n_colors] for b in hash_bytes]

    def draw_stamp(x_offset: int):
        idx = 0
        for row in range(rows):
            for col in range(cols):
                color = bar_colors[idx % len(bar_colors)]
                dwg.add(
                    dwg.rect(
                        insert=(x_offset + col * bar_w, (H - stamp_height) / 2 + row * bar_h),
                        size=(bar_w, bar_h),
                        fill=color,
                    )
                )
                idx += 1

    if side in ("left", "both"):
        draw_stamp(0)
    if side in ("right", "both"):
        draw_stamp(W - stamp_width)

    return dwg

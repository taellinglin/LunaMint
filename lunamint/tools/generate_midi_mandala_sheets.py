"""Generate EisenScript sheets of hash mandalas for MIDI files."""
from __future__ import annotations

from pathlib import Path


def _mm_to_px(mm: float, dpi: float) -> float:
    return (mm / 25.4) * dpi


def _sanitize_label(text: str, max_len: int = 22) -> str:
    cleaned = "".join(ch for ch in text if ch.isalnum() or ch in {" ", "-", "_"}).strip()
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[: max_len - 1].rstrip() + "…"


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    midi_dir = root / "MIDI Collection"
    out_dir = root / "lunamint" / "my_mints" / "midi_mandala_sheets"
    out_dir.mkdir(parents=True, exist_ok=True)

    midi_files = sorted(
        [p for p in midi_dir.iterdir() if p.suffix.lower() in {".mid", ".midi"}],
        key=lambda p: p.name.lower(),
    )

    if not midi_files:
        raise SystemExit("No MIDI files found in MIDI Collection")

    sheet_px = 2048
    dpi = 300.0
    sheet_mm = (sheet_px / dpi) * 25.4

    cols = 4
    rows = 4
    margin_mm = 8.0
    cell_w = (sheet_mm - 2 * margin_mm) / cols
    cell_h = (sheet_mm - 2 * margin_mm) / rows
    radius_mm = min(cell_w, cell_h) / 2 - 2.0

    label_size_px = 24
    label_offset_px = 26

    per_sheet = cols * rows
    total_sheets = (len(midi_files) + per_sheet - 1) // per_sheet

    for sheet_idx in range(total_sheets):
        start = sheet_idx * per_sheet
        chunk = midi_files[start : start + per_sheet]
        lines: list[str] = []
        lines.append(f"# MIDI mandala sheet {sheet_idx + 1}/{total_sheets}")
        lines.append(f"size {sheet_px} {sheet_px}")
        lines.append("background #202020")
        lines.append("")

        for idx, midi_path in enumerate(chunk):
            row = idx // cols
            col = idx % cols
            cx_mm = margin_mm + cell_w * (col + 0.5)
            cy_mm = margin_mm + cell_h * (row + 0.5)

            label = _sanitize_label(midi_path.stem)
            x_px = _mm_to_px(cx_mm, dpi)
            y_px = _mm_to_px(cy_mm, dpi) + _mm_to_px(radius_mm, dpi) + label_offset_px

            data_path = midi_path.relative_to(root).as_posix()

            lines.append(f"# {label}")
            lines.append(
                "hash_mandala "
                f"cx_mm={cx_mm:.2f} cy_mm={cy_mm:.2f} radius_mm={radius_mm:.2f} "
                f"data_path=\"{data_path}\" data_type=midi "
                "font=\"Daemon Full Working\" font_size_mm=2.2 "
                "charset=\"QWERTYUIOPASDFGHJKLZXCVBNM1234567890\" "
                "rings=0 sectors=0 ring_rows=1 sector_density=2.0 fill_empty=true colorize=true use_roygbiv=true "
                "opacity=1.0 stroke_width_mm=0.12 inset_scale=0.9 outset_scale=1.22 snap_grid_px=0 "
                "background_color=\"#000000\" background_opacity=0.45 "
                "stroke_only=false stroke_color=\"#111111\" stroke_color_secondary=\"#111111\" "
                "flat_glyphs=true glyph_fill=\"#e6e6e6\" glyph_stroke=\"#111111\" glyph_stroke_width_scale=0.7 "
                "min_cols_per_sector=1 taper_outer_strength=0.35 taper_radial_strength=0.55 "
                "ring_label_every=4 ring_label_alternate=true ring_label_text=\"123456789\" ring_label_size_scale=0.85 "
                "sector_padding_deg=0.2 ring_padding_mm=0.04 sector_outline=true sector_outline_color=\"#111111\" "
                "sector_outline_width_mm=0.08 ring_pattern_mode=true sm2_row_variance=2 "
                "radial_lines=24 tick_major=16 tick_minor=32 core_rings=4 core_radials=24 core_letter_every=2 "
                "cardinal_markers=true label_every=4 label_radius_ratio=0.86 label_font_size_mm=0.9 "
                "label_stroke_width_mm=0.08 sector_boxes=false center_digit=0 center_digit_fill_background=false"
            )
            lines.append(f"text {x_px:.0f} {y_px:.0f} {label_size_px} #dddddd {label}")
            lines.append("")

        out_path = out_dir / f"midi_mandala_sheet_{sheet_idx + 1:02d}.eisen"
        out_path.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()

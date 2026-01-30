"""Generate Yisen (EisenScript) mandala dial sheets from MIDI files."""
from __future__ import annotations

from pathlib import Path
import re

try:
    import mido  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    mido = None


ALNUM_CC = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
NOTE_ALPHA = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"


def _mm_to_px(mm: float, dpi: float) -> float:
    return (mm / 25.4) * dpi


def _title_case(name: str) -> str:
    cleaned = re.sub(r"[_\-]+", " ", name).strip()
    return " ".join(word.capitalize() for word in cleaned.split())


def _note_to_alpha(note: int) -> str:
    return NOTE_ALPHA[note % len(NOTE_ALPHA)]


def _analyze_midi(path: Path) -> dict:
    if mido is None:
        return {
            "vel_norm": 0.6,
            "cc_norm": 0.5,
            "note_label": "AaBbCc",
            "note_count": 0,
            "cc_count": 0,
        }

    midi = mido.MidiFile(path)
    velocities = []
    cc_values = []
    notes = []

    for track in midi.tracks:
        for msg in track:
            if msg.type == "note_on" and msg.velocity > 0:
                velocities.append(msg.velocity)
                notes.append(msg.note)
            elif msg.type == "control_change":
                cc_values.append(msg.value)

    vel_avg = sum(velocities) / max(1, len(velocities))
    vel_norm = min(1.0, vel_avg / 127.0)

    if cc_values:
        cc_avg = sum(cc_values) / len(cc_values)
        cc_norm = min(1.0, cc_avg / 127.0)
    else:
        cc_norm = 0.5

    unique_notes = sorted(set(notes))
    note_label = "".join(_note_to_alpha(n) for n in unique_notes[:32]) or "Aa"

    return {
        "vel_norm": vel_norm,
        "cc_norm": cc_norm,
        "note_label": note_label,
        "note_count": len(unique_notes),
        "cc_count": len(cc_values),
    }


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    midi_dir = root / "MIDI Collection"
    out_dir = root / "lunamint" / "my_mints" / "midi_yisen_sheets"
    out_dir.mkdir(parents=True, exist_ok=True)

    midi_files = sorted(
        [p for p in midi_dir.iterdir() if p.suffix.lower() in {".mid", ".midi"}],
        key=lambda p: p.name.lower(),
    )
    if not midi_files:
        raise SystemExit("No MIDI files found in MIDI Collection")

    sheet_px = 4096
    dpi = 300.0
    sheet_mm = (sheet_px / dpi) * 25.4

    cols = 5
    rows = 5
    margin_mm = 8.0
    cell_w = (sheet_mm - 2 * margin_mm) / cols
    cell_h = (sheet_mm - 2 * margin_mm) / rows
    radius_mm = min(cell_w, cell_h) / 2 - 2.0

    label_size_px = 22
    label_offset_px = 22

    per_sheet = cols * rows
    total_sheets = (len(midi_files) + per_sheet - 1) // per_sheet

    for sheet_idx in range(total_sheets):
        start = sheet_idx * per_sheet
        chunk = midi_files[start : start + per_sheet]
        lines: list[str] = []
        lines.append(f"# Yisen MIDI dial sheet {sheet_idx + 1}/{total_sheets}")
        lines.append(f"size {sheet_px} {sheet_px}")
        lines.append("background #1f1f1f")
        lines.append("")

        for idx, midi_path in enumerate(chunk):
            row = idx // cols
            col = idx % cols
            cx_mm = margin_mm + cell_w * (col + 0.5)
            cy_mm = margin_mm + cell_h * (row + 0.5)

            title = _title_case(midi_path.stem)
            data_path = midi_path.relative_to(root).as_posix()

            stats = _analyze_midi(midi_path)
            sector_density = 1.4 + stats["vel_norm"] * 1.2
            sm2_row_variance = 1 + int(stats["cc_norm"] * 4)
            ring_label_every = 3 + int(stats["vel_norm"] * 3)
            ring_label_text = stats["note_label"]
            font_size = 1.8 + stats["vel_norm"] * 1.2

            x_px = _mm_to_px(cx_mm, dpi)
            y_px = _mm_to_px(cy_mm, dpi) + _mm_to_px(radius_mm, dpi) + label_offset_px

            lines.append(f"# {title}")
            lines.append(
                "midi_dial "
                f"cx_mm={cx_mm:.2f} cy_mm={cy_mm:.2f} radius_mm={radius_mm:.2f} "
                f"file=\"{data_path}\" "
                f"font=\"Daemon Full Working\" font_size_mm={font_size:.2f} "
                f"note_charset=\"{NOTE_ALPHA}\" cc_charset=\"{ALNUM_CC}\" "
                f"note_opacity=0.95 cc_opacity=0.9 "
                "background_color=\"#000000\" background_opacity=0.35 "
                "outer_stroke=\"#111111\" outer_stroke_width_mm=0.5 "
                "note_stroke=\"#111111\" note_stroke_width_mm=0.12 "
                "cc_mark_length_mm=1.0 cc_mark_width_mm=0.08 cc_ring_offset_mm=1.2 "
                "inner_radius_ratio=0.12 outer_radius_ratio=0.92 rotation_deg=0"
            )
            lines.append(f"text {x_px:.0f} {y_px:.0f} {label_size_px} #dddddd {title}")
            lines.append("")

        out_path = out_dir / f"yisen_midi_dials_{sheet_idx + 1:02d}.eisen"
        out_path.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()

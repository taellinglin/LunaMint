"""EisenScript checker: reports syntax and common errors with line numbers."""
from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path
from typing import List, Tuple

from lunamint.scripting.eisen import parse_script, render_svg, _split_script_line


KNOWN_CMDS = {
    "size",
    "background",
    "rect",
    "circle",
    "dot",
    "pix",
    "polygon",
    "line",
    "text",
    "group",
    "endgroup",
    "end_group",
    "group_end",
    "cutout_circle",
    "mask_circle",
    "qr_code",
    "pixel_art",
    "midi_dial",
    "text_dial",
    "text_grid",
    "letter_border",
    "hash_mandala",
    "hash_mandala_rect",
    "sd_background",
    "front_banknote",
    "back_banknote",
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
}


def _logical_lines(source: str) -> List[Tuple[int, str]]:
    logical: List[Tuple[int, str]] = []
    buffer = ""
    start_line = 1
    for idx, raw_line in enumerate(source.splitlines(), start=1):
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("{#") or stripped.startswith("{%"):
            continue
        if stripped.endswith("\\"):
            if not buffer:
                start_line = idx
            buffer += stripped[:-1].rstrip() + " "
            continue
        if buffer:
            buffer += stripped
            logical.append((start_line, buffer))
            buffer = ""
        else:
            logical.append((idx, stripped))
    if buffer:
        logical.append((start_line, buffer))
    return logical


def check_script(path: Path, render: bool) -> int:
    source = path.read_text(encoding="utf-8")
    errors: List[str] = []

    for line_no, line in _logical_lines(source):
        try:
            parts = _split_script_line(line)
        except Exception as exc:
            errors.append(f"Line {line_no}: {exc}")
            continue
        if not parts:
            continue
        cmd = parts[0].lower()
        if cmd not in KNOWN_CMDS:
            errors.append(f"Line {line_no}: Unknown command '{cmd}'")

    if errors:
        print("EisenScript check failed:\n" + "\n".join(errors))
        return 2

    try:
        program = parse_script(source)
    except Exception as exc:
        print(f"EisenScript parse error: {exc}")
        return 3

    if render:
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                out_path = Path(tmpdir) / "eisen.svg"
                render_svg(program, out_path)
        except Exception as exc:
            print(f"EisenScript render error: {exc}")
            return 4

    print("EisenScript OK")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="EisenScript checker")
    parser.add_argument("path", help="Path to .eisen file")
    parser.add_argument("--render", action="store_true", help="Also attempt render to catch runtime errors")
    args = parser.parse_args()

    path = Path(args.path)
    if not path.exists():
        print(f"File not found: {path}")
        return 1

    return check_script(path, render=args.render)


if __name__ == "__main__":
    raise SystemExit(main())

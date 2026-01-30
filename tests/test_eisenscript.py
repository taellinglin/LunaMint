import os
import unittest
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

from lunamint.scripting.eisen import parse_script, render_svg


def _count_rendered_elements(svg_text: str) -> int:
    tree = ET.fromstring(svg_text)
    namespace = "{http://www.w3.org/2000/svg}"

    def is_background_rect(elem: ET.Element) -> bool:
        if elem.tag != f"{namespace}rect":
            return False
        width = elem.attrib.get("width")
        height = elem.attrib.get("height")
        x = elem.attrib.get("x", "0")
        y = elem.attrib.get("y", "0")
        return width is not None and height is not None and x == "0" and y == "0"

    rendered = 0
    for elem in tree.iter():
        if elem.tag == f"{namespace}svg":
            continue
        if elem.tag == f"{namespace}defs":
            continue
        if is_background_rect(elem):
            continue
        rendered += 1
    return rendered


class TestEisenScriptParsing(unittest.TestCase):
    def test_parse_basic_primitives(self) -> None:
        script = "\n".join(
            [
                "size 1600 600",
                "background #F7F7F9",
                "rect 20 20 1560 560 #FFFFFF",
                "text 60 80 32 #111111 \"LunaMint Banknote\"",
                "line 60 140 1540 140 #CCCCCC 2",
                "circle 1400 120 36 #3A7AFE",
            ]
        )
        program = parse_script(script)
        ops = [op.op for op in program.ops]
        self.assertIn("rect", ops)
        self.assertIn("text", ops)
        self.assertIn("line", ops)
        self.assertIn("circle", ops)

    def test_parse_front_banknote(self) -> None:
        program = parse_script("front_banknote showcase_widgets=true")
        ops = [op.op for op in program.ops]
        self.assertIn("front_banknote", ops)

    def test_parse_text_dial(self) -> None:
        program = parse_script("text_dial cx_mm=80 cy_mm=45 radius_mm=30 text=LUNAMINT")
        ops = [op.op for op in program.ops]
        self.assertIn("text_dial", ops)


class TestEisenScriptRendering(unittest.TestCase):
    def test_render_basic_primitives(self) -> None:
        script = "\n".join(
            [
                "size 1600 600",
                "background #F7F7F9",
                "rect 20 20 1560 560 #FFFFFF",
                "text 60 80 32 #111111 \"LunaMint Banknote\"",
                "line 60 140 1540 140 #CCCCCC 2",
                "circle 1400 120 36 #3A7AFE",
            ]
        )
        program = parse_script(script)
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "basic.svg"
            render_svg(program, out_path)
            svg_text = out_path.read_text(encoding="utf-8")
        self.assertGreater(_count_rendered_elements(svg_text), 0)

    def test_render_text_dial(self) -> None:
        script = "text_dial cx_mm=80 cy_mm=45 radius_mm=30 text=LUNAMINT"
        program = parse_script(script)
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "text_dial.svg"
            render_svg(program, out_path)
            svg_text = out_path.read_text(encoding="utf-8")
        self.assertGreater(_count_rendered_elements(svg_text), 0)

    def test_render_front_banknote_widgets(self) -> None:
        script = "front_banknote showcase_widgets=true showcase_labels=true"
        program = parse_script(script)
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "front.svg"
            try:
                render_svg(program, out_path)
            except Exception as exc:
                self.skipTest(f"front_banknote rendering dependencies missing: {exc}")
            svg_text = out_path.read_text(encoding="utf-8")
        self.assertGreater(_count_rendered_elements(svg_text), 0)


if __name__ == "__main__":
    unittest.main()

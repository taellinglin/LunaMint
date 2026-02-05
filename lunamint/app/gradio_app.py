"""
Simple Gradio UI/API for lunamint.

Run:
  python gradio_app.py

Then open the printed URL. The interface also exposes a JSON API.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List

import gradio as gr

from lunamint.scripting import render_script_to_svg_html


MINTS_DIR = Path(__file__).resolve().parents[1] / "my_mints"


def _list_mint_scripts() -> List[str]:
  if not MINTS_DIR.exists():
    return []
  scripts = sorted(p.relative_to(MINTS_DIR).as_posix() for p in MINTS_DIR.rglob("*.eisen"))
  return scripts


def _load_mint_script(relative_path: str) -> str:
  if not relative_path:
    return ""
  target = (MINTS_DIR / relative_path).resolve()
  if MINTS_DIR not in target.parents and target != MINTS_DIR:
    raise gr.Error("Invalid script path")
  if not target.exists():
    raise gr.Error("Script not found")
  return target.read_text(encoding="utf-8")


WIDGET_DEFAULTS: Dict[str, Dict[str, Any]] = {
  "sd_background": {
    "seed_text": "LunaMint",
    "bg_dir": "./backgrounds",
    "background_prompt": "",
    "filter": "vectorize",
    "margin": "60",
    "background_segments": "1024",
    "glyph_colorize": "true",
  },
  "midi_dial": {
    "cx_mm": "40",
    "cy_mm": "40",
    "radius_mm": "30",
    "file": "MIDI Collection/AA - Orchestrated.mid",
    "font": "Daemon Full Working",
    "font_size_mm": "2.2",
    "note_charset": "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz",
    "cc_charset": "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789",
    "note_opacity": "0.95",
    "cc_opacity": "0.9",
    "background_color": "#000000",
    "background_opacity": "0.35",
    "outer_stroke": "#111111",
    "outer_stroke_width_mm": "0.5",
    "note_stroke": "#111111",
    "note_stroke_width_mm": "0.12",
    "cc_mark_length_mm": "1.0",
    "cc_mark_width_mm": "0.08",
    "cc_ring_offset_mm": "1.2",
    "inner_radius_ratio": "0.12",
    "outer_radius_ratio": "0.92",
    "rotation_deg": "0",
  },
  "hash_mandala": {
    "cx_mm": "80",
    "cy_mm": "45",
    "radius_mm": "22",
    "data_path": "MIDI Collection/AA - Orchestrated.mid",
    "data_type": "midi",
    "font": "Daemon Full Working",
    "font_size_mm": "1.2",
    "charset": "LUNAMINT",
    "rings": "0",
    "sectors": "0",
    "opacity": "0.85",
    "stroke_width_mm": "0.08",
    "colorize": "true",
    "use_roygbiv": "true",
  },
  "daemon_security": {
    "x_mm": "0",
    "y_mm": "0",
    "width_mm": "160",
    "height_mm": "60",
    "text": "LUNAMINT",
    "font": "Daemon Full Working",
    "font_size_mm": "1.2",
    "spacing_mm": "0.6",
    "row_spacing_mm": "0.6",
    "angle_deg": "0",
    "opacity": "0.35",
    "color_seed": "",
    "stagger": "true",
    "density": "1.0",
    "letter_scale": "1.0",
    "hash_algo": "sha256",
    "sm2_private_key": "",
    "sm2_public_key": "",
    "sm4_key": "",
  },
  "text": {
    "x": "100",
    "y": "100",
    "size": "22",
    "fill": "#dddddd",
    "text": "Label",
  },
  "qr_code": {
    "x": "120",
    "y": "120",
    "size": "180",
    "data": "https://linglin.art",
    "border": "2",
    "error": "M",
    "foreground": "#000000",
    "background": "#ffffff",
  },
  "back_vectorized_background": {
    "seed_text": "LunaMint",
    "bg_dir": "./backgrounds",
    "margin": "60",
    "n_segments": "1024",
    "background_prompt": "",
    "denomination": "100 卢纳币",
  },
  "back_corner_denoms": {
    "denomination": "100",
    "big_scale": "1.0",
    "small_scale": "1.0",
  },
  "back_corner_decorations": {
    "denomination": "100",
    "timestamp_ms": "",
    "serial_id": "",
    "size": "100",
    "padding": "75",
    "stroke_width": "1",
  },
  "back_holographic_seals": {
    "serial_id": "SN-0000-0000-0000",
    "denomination": "100",
    "radius": "160",
  },
  "back_center_text": {
    "title": "灵国国库",
    "phrase": "灵之意志，天下共识",
    "denomination": "100",
  },
  "back_circular_qr": {
    "data": "1",
    "cx": "800",
    "cy": "300",
    "inner_radius": "0",
    "outer_radius": "220",
    "segments": "4",
    "opacity": "0.5",
    "colors": "#D80027,#0052B4,#009E60",
  },
  "back_qr_border": {
    "seed_text": "100",
    "serial_id": "",
    "timestamp_ms": "",
  },
  "back_verification_text": {
    "serial_id": "SN-0000-0000-0000",
    "timestamp_ms": "",
  },
  "back_security_background": {
    "denomination": "100",
    "serial_id": "SN-0000-0000-0000",
    "margin": "60",
    "base_triangle_size": "16",
    "hierarchy_levels": "2",
  },
  "chinese_microprint": {
    "cx": "800",
    "cy": "300",
    "radius": "60",
    "text": "壹佰 卢纳币",
    "repetitions": "1",
    "font_family": "FengGuangMingRui",
    "font_size": "8",
  },
  "rainbow_microseal": {
    "cx": "800",
    "cy": "300",
    "radius": "60",
    "symbol": "",
    "repetitions": "64",
    "font_family": "Daemon Full Working",
    "font_size": "8",
  },
  "back_aztec": {
    "url": "https://linglin.art",
    "cx": "440",
    "cy": "300",
    "scale": "3",
    "border": "12",
    "rotation": "0",
    "border_opacity": "0.5",
    "denomination": "100",
  },
  "line": {
    "x1": "0",
    "y1": "0",
    "x2": "100",
    "y2": "0",
    "stroke": "#111111",
    "width": "1",
  },
  "rect": {
    "x": "0",
    "y": "0",
    "w": "100",
    "h": "100",
    "fill": "#111111",
  },
  "dot": {
    "x": "0",
    "y": "0",
    "fill": "#111111",
  },
  "pix": {
    "x": "0",
    "y": "0",
    "fill": "#111111",
  },
  "circle": {
    "x": "80",
    "y": "80",
    "r": "40",
    "fill": "#111111",
  },
  "pixel_art": {
    "x_mm": "10",
    "y_mm": "10",
    "image": "portraits/portrait_Ling_Treasury.png",
    "pixel_size_mm": "0.6",
    "alpha_threshold": "0.05",
    "compress": "true",
  },
  "text_dial": {
    "cx_mm": "80",
    "cy_mm": "45",
    "radius_mm": "30",
    "text": "LUNAMINT",
    "rings": "6",
    "font": "Daemon Full Working",
    "font_size_mm": "1.2",
  },
  "text_grid": {
    "x_mm": "10",
    "y_mm": "10",
    "width_mm": "60",
    "height_mm": "60",
    "text": "LUNAMINT",
    "font": "Daemon Full Working",
    "font_size_mm": "1.2",
  },
  "letter_border": {
    "x_mm": "0",
    "y_mm": "0",
    "width_mm": "160",
    "height_mm": "60",
    "border_thickness_mm": "3.0",
    "text": "LUNAMINT",
    "font": "Daemon Full Working",
    "font_size_mm": "1.2",
    "inset_mm": "0.0",
    "outset_mm": "0.0",
    "offset_x_mm": "0.0",
    "offset_y_mm": "0.0",
    "layout": "band",
    "palette": "",
    "cycle_mode": "sequential",
    "cycle_seed": "",
    "encoding_algo": "sha3_256",
    "packed_spacing_x_mm": "",
    "packed_spacing_y_mm": "",
    "packed_glyph_scale": "1.0",
    "fill_color": "#111111",
    "opacity": "1.0",
  },
}


def _needs_quotes(value: str) -> bool:
  return any(ch.isspace() or ch in {'"', "'", "#", "[", "]"} for ch in value)


def _format_value(value: Any) -> str:
  if value is None:
    return ""
  if isinstance(value, bool):
    return "true" if value else "false"
  text = str(value)
  if text == "":
    return ""
  if _needs_quotes(text):
    return f"\"{text.replace('"', '\\"')}\""
  return text


def _props_to_lines(widget_type: str, props: Dict[str, Any]) -> List[str]:
  if widget_type == "text":
    return [
      f"text {props.get('x', '0')} {props.get('y', '0')} {props.get('size', '12')} {props.get('fill', '#000')} {props.get('text', '')}".rstrip()
    ]
  if widget_type == "line":
    return [
      f"line {props.get('x1', '0')} {props.get('y1', '0')} {props.get('x2', '0')} {props.get('y2', '0')} {props.get('stroke', '#000')} {props.get('width', '1')}".rstrip()
    ]
  if widget_type == "rect":
    return [
      f"rect {props.get('x', '0')} {props.get('y', '0')} {props.get('w', '10')} {props.get('h', '10')} {props.get('fill', '#000')}".rstrip()
    ]
  if widget_type == "dot":
    return [
      f"dot {props.get('x', '0')} {props.get('y', '0')} {props.get('fill', '#000')}".rstrip()
    ]
  if widget_type == "pix":
    return [
      f"pix {props.get('x', '0')} {props.get('y', '0')} {props.get('fill', '#000')}".rstrip()
    ]
  if widget_type == "circle":
    return [
      f"circle {props.get('x', '0')} {props.get('y', '0')} {props.get('r', '5')} {props.get('fill', '#000')}".rstrip()
    ]

  parts = [widget_type]
  for key, value in props.items():
    if value is None or str(value) == "":
      continue
    parts.append(f"{key}={_format_value(value)}")
  return [" ".join(parts)]


def _elements_to_script(elements: List[Dict[str, Any]]) -> str:
  lines: List[str] = []
  for element in elements:
    widget_type = element.get("type", "")
    props = element.get("props", {})
    if not widget_type:
      continue
    lines.extend(_props_to_lines(widget_type, props))
    lines.append("")
  return "\n".join(lines).strip()


def _add_widget(elements: List[Dict[str, Any]], widget_type: str, insert_after: str) -> List[Dict[str, Any]]:
  new_elements = list(elements or [])
  props = dict(WIDGET_DEFAULTS.get(widget_type, {}))
  new_item = {"type": widget_type, "props": props}
  if not insert_after or insert_after == "Top":
    new_elements.insert(0, new_item)
    return new_elements
  try:
    idx = int(insert_after.split(" ", 1)[0])
  except ValueError:
    new_elements.append(new_item)
    return new_elements
  insert_at = min(len(new_elements), max(0, idx + 1))
  new_elements.insert(insert_at, new_item)
  return new_elements


def _update_element(elements: List[Dict[str, Any]], index: int, rows: Any) -> List[Dict[str, Any]]:
  if not elements or index < 0 or index >= len(elements):
    return elements
  if rows is None:
    return elements
  if hasattr(rows, "to_dict"):
    rows = rows.values.tolist()
  props: Dict[str, Any] = {}
  for row in rows:
    if not row or len(row) < 2:
      continue
    key = str(row[0]).strip()
    if not key:
      continue
    props[key] = row[1]
  updated = list(elements)
  item = dict(updated[index])
  item["props"] = props
  updated[index] = item
  return updated


def _element_choices(elements: List[Dict[str, Any]]) -> List[str]:
  choices = ["Top"]
  for idx, element in enumerate(elements or []):
    widget_type = element.get("type", "element")
    choices.append(f"{idx} {widget_type}")
  return choices


def _generate(script: str, export_png: bool, sd_api_url: str | None):
  if not script or not script.strip():
    raise gr.Error("Script is required")

  if sd_api_url and sd_api_url.strip():
    os.environ["SD_API_BASE_URL"] = sd_api_url.strip()
    os.environ["SD_API_URL"] = sd_api_url.strip()

  out_dir = Path(tempfile.mkdtemp(prefix="eisen_"))
  svg_path, html_path = render_script_to_svg_html(script, out_dir)
  png_path = None
  if export_png:
    try:
      import cairosvg

      png_path = out_dir / "eisen.png"
      cairosvg.svg2png(url=str(svg_path), write_to=str(png_path))
    except Exception as exc:
      raise gr.Error(f"PNG export failed: {exc}")

  preview_html = (
    "<div style='display:flex;align-items:center;justify-content:center;height:100%;'>"
    "<div style='border:1px solid #ddd;border-radius:12px;padding:12px;background:#fff;max-width:95%;max-height:95%;'>"
    f"{svg_path.read_text(encoding='utf-8')}"
    "</div></div>"
  )

  return preview_html, str(svg_path), str(png_path) if png_path else None


ROYGBIV_SYNTAX_CSS = """
.cm-editor { background: #0b0b0b; color: #f2f2f2; }
.cm-content { caret-color: #ffffff; }
.cm-line { font-family: "Consolas", "Fira Code", monospace; }
.cm-gutters { background: #0b0b0b; color: #666; border-right: 1px solid #222; }
.cm-keyword { color: #FF0000; }   /* red */
.cm-operator { color: #FF7F00; }  /* orange */
.cm-number { color: #FFFF00; }    /* yellow */
.cm-string { color: #00FF00; }    /* green */
.cm-variableName { color: #0000FF; } /* blue */
.cm-comment { color: #4B0082; }   /* indigo */
.cm-builtin, .cm-def { color: #8B00FF; } /* violet */
"""


def build_ui():
  with gr.Blocks(title="Banknote Generator") as demo:
        gr.Markdown("# Banknote Generator\nGenerate front/back SVG+PNG using lunamint.")

        with gr.Tab("Editor"):
            default_script = ""
            script_path = Path(__file__).resolve().parents[1] / "my_mints" / "eisen.sample"
            if script_path.exists():
                default_script = script_path.read_text(encoding="utf-8")

            elements_state = gr.State([])

            with gr.Row():
                with gr.Column(scale=1, min_width=320):
                  with gr.Accordion("Navigator", open=True):
                    gr.Markdown("### Eisen Settings")
                    sd_api_url = gr.Textbox(
                        label="SD API URL",
                        placeholder="http://127.0.0.1:7777",
                        value=os.getenv("SD_API_BASE_URL", ""),
                    )
                    gr.Markdown("### My Mints")
                    mint_scripts = gr.Dropdown(
                      label="Eisen files",
                      choices=_list_mint_scripts(),
                      value=None,
                    )
                  with gr.Row():
                    load_mint_btn = gr.Button("Load")
                    refresh_mint_btn = gr.Button("Refresh")
                    widget_type = gr.Dropdown(
                        label="Add widget",
                        choices=sorted(WIDGET_DEFAULTS.keys()),
                        value="midi_dial",
                    )
                    insert_after = gr.Dropdown(
                        label="Insert after",
                        choices=["Top"],
                        value="Top",
                    )
                    add_widget_btn = gr.Button("Add")
                    apply_btn = gr.Button("Apply to editor")

                    @gr.render(inputs=elements_state)
                    def _render_elements(elements: List[Dict[str, Any]]):
                      for idx, element in enumerate(elements or []):
                        widget_label = element.get("type", "element")
                        with gr.Accordion(f"{idx} · {widget_label}", open=False):
                          rows = [[k, v] for k, v in (element.get("props") or {}).items()]
                          df = gr.Dataframe(
                            headers=["property", "value"],
                            value=rows,
                            datatype=["str", "str"],
                            row_count=(max(1, len(rows)), "fixed"),
                            col_count=(2, "fixed"),
                            interactive=True,
                            wrap=True,
                          )

                          def _on_change(rows, elements, i=idx):
                            return _update_element(elements, i, rows)

                          df.change(_on_change, inputs=[df, elements_state], outputs=elements_state)

                with gr.Column(scale=2):
                  script_editor = gr.Code(
                    label="EisenScript",
                    value=default_script,
                    language="markdown",
                    lines=20,
                  )

            def _on_add(elements, widget_choice, after_choice):
              updated = _add_widget(elements, widget_choice, after_choice)
              return updated, gr.Dropdown(choices=_element_choices(updated))

            def _on_apply(elements, current_script):
              script_block = _elements_to_script(elements)
              if not script_block:
                return current_script
              if current_script and current_script.strip():
                return current_script.rstrip() + "\n\n" + script_block
              return script_block

            add_widget_btn.click(
              _on_add,
              inputs=[elements_state, widget_type, insert_after],
              outputs=[elements_state, insert_after],
            )
            load_mint_btn.click(
              _load_mint_script,
              inputs=[mint_scripts],
              outputs=[script_editor],
            )
            refresh_mint_btn.click(
              lambda: gr.Dropdown(choices=_list_mint_scripts()),
              inputs=[],
              outputs=[mint_scripts],
            )
            apply_btn.click(
              _on_apply,
              inputs=[elements_state, script_editor],
              outputs=[script_editor],
            )

            elements_state.change(
              lambda elements: gr.Dropdown(choices=_element_choices(elements)),
              inputs=[elements_state],
              outputs=[insert_after],
            )

        with gr.Tab("Preview"):
            preview_panel = gr.HTML(
                "<div style='height:100%;display:flex;align-items:center;justify-content:center;color:#888;'>Generate to preview</div>",
                sanitize=False,
            )

        with gr.Tab("Save"):
            export_png = gr.Checkbox(label="Export PNG", value=False)
            run_btn = gr.Button("Generate")
            svg_file = gr.File(label="SVG output")
            png_file = gr.File(label="PNG output")

        run_btn.click(
            _generate,
            inputs=[
            script_editor,
            export_png,
            sd_api_url,
            ],
          outputs=[preview_panel, svg_file, png_file],
        )

        return demo


if __name__ == "__main__":
  app = build_ui()
  app.launch(css=ROYGBIV_SYNTAX_CSS)

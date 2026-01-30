#!/usr/bin/env python3
"""
fantasy_banknote.py — Enhanced procedural fantasy banknote generator
----------------------------------------------------------------------
Creates a stylized, clearly-marked "banknote" from an input image.
Outputs an SVG (vector) and optional PNG preview.
Requires: Pillow, svgwrite. Optional: fontTools for glyph paths.

Author: RingMaster Lin
"""
from io import BytesIO
import os
import sys
import math
import io
import base64
import argparse
import hashlib
import re
from typing import Tuple, List
import binascii
from PIL import Image, ImageOps
import numpy as np
from sklearn.cluster import KMeans
import requests
import os
import time
import tqdm
try:
    from ..filters.vectorize import add_vectorized_background
    from ..filters.triangle_mosaic import add_triangle_mosaic_background, TriangleMosaicConfig
    from ..filters.letter_mosaic import add_letter_mosaic_background, LetterMosaicConfig
    from ..filters.glyph_grid import add_glyph_grid_background, GlyphGridConfig
    from ..widgets.glyph_grid import GlyphGridOptions
    from ..graphics.modules.qr import (
        add_colored_aztec_to_canvas,
        add_roygbiv_qr_style,
        denomination_to_color,
        safe_make_matrix,
    )
    from ..widgets.border_front import (
        add_decorative_border,
        add_qr_like_border,
        add_subtle_frame_and_microgrid as _widget_add_subtle_frame_and_microgrid,
    )
    from ..widgets import (
        AsciiStampOptions,
        add_ascii_stamp_from_prompt_mm,
        add_barcode_border_mm,
        add_fractal_stamp_mm,
        add_godseye_mm,
        add_guilloche_band_mm,
        add_iris_lines_mm,
        add_microtext_line_mm,
        add_rosette_mm,
        add_security_thread_mm,
        add_serial_panel_mm,
        add_tile_border_mm,
        add_watermark_medallion_mm,
    )
    from ..widgets.crypto import build_qr_url, load_crypto_config
except ImportError:
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from lunamint.filters.vectorize import add_vectorized_background
    from lunamint.filters.triangle_mosaic import add_triangle_mosaic_background, TriangleMosaicConfig
    from lunamint.filters.letter_mosaic import add_letter_mosaic_background, LetterMosaicConfig
    from lunamint.filters.glyph_grid import add_glyph_grid_background, GlyphGridConfig
    from lunamint.widgets.glyph_grid import GlyphGridOptions
    from lunamint.graphics.modules.qr import (
        add_colored_aztec_to_canvas,
        add_roygbiv_qr_style,
        denomination_to_color,
        safe_make_matrix,
    )
    from lunamint.widgets.border_front import (
        add_decorative_border,
        add_qr_like_border,
        add_subtle_frame_and_microgrid as _widget_add_subtle_frame_and_microgrid,
    )
    from lunamint.widgets import (
        AsciiStampOptions,
        add_ascii_stamp_from_prompt_mm,
        add_barcode_border_mm,
        add_fractal_stamp_mm,
        add_godseye_mm,
        add_guilloche_band_mm,
        add_iris_lines_mm,
        add_microtext_line_mm,
        add_rosette_mm,
        add_security_thread_mm,
        add_serial_panel_mm,
        add_tile_border_mm,
        add_watermark_medallion_mm,
    )
    from lunamint.widgets.crypto import build_qr_url, load_crypto_config
try:
    import svgwrite
except Exception:
    print("[!] svgwrite required: pip install svgwrite")
    raise

USE_FONTTOOLS = True
try:
    from fontTools.ttLib import TTFont
    from fontTools.pens.svgPathPen import SVGPathPen
except Exception:
    USE_FONTTOOLS = False

# ----------------------
# Utility / conversions
# ----------------------
MM_TO_PX = 300.0 / 25.4
def mm_to_px(mm: float, dpi: float = 300.0) -> int:
    return int(round(mm * dpi / 25.4))


def generate_security_pattern(bg_path, output_path=None, seed_data=None, font_path=None, pattern_density=0.1):
    """
    Overlay a colored pattern on a background image, using SHA3-512 hashing for deterministic patterns.
    If output_path is a directory, auto-generate a filename inside it.
    If output_path is None, overwrite the background.
    """

    # Load background
    bg = Image.open(bg_path).convert("RGBA")
    width, height = bg.size

    # Generate seed from data using SHA3-512
    if seed_data is None:
        seed_data = datetime.now().isoformat()
    seed_hash = sha3_512_salted(str(seed_data))
    seed_int = int.from_bytes(seed_hash[:8], "big")

    # Deterministic RNG
    class DeterministicRandom:
        def __init__(self, seed):
            self.state = seed
        def random(self):
            self.state = (self.state * 1103515245 + 12345) & 0x7fffffff
            return self.state / 0x7fffffff
        def randint(self, a, b):
            return a + int(self.random() * (b - a + 1))

    det_random = DeterministicRandom(seed_int)

    # Create overlay
    overlay = Image.new("RGBA", bg.size, (0,0,0,0))
    draw = ImageDraw.Draw(overlay)

    # Microtext option
    font, text = None, None
    if font_path:
        try:
            font_size = max(6, int(min(width, height) * 0.02))
            font = ImageFont.truetype(font_path, font_size)
            text = str(seed_data)
        except Exception as e:
            print(f"[!] Font load failed: {e}")

    # Draw pattern
    for x in range(0, width, 5):
        for y in range(0, height, 5):
            if det_random.random() < pattern_density:
                color_seed = (x * y + seed_int) % 0xffffff
                r, g, b = (color_seed >> 16) & 0xff, (color_seed >> 8) & 0xff, color_seed & 0xff
                color = (r, g, b, det_random.randint(50, 100))
                if font and text:
                    draw.text((x, y), text, font=font, fill=color)
                else:
                    draw.point((x, y), fill=color)

    # Combine
    result = Image.alpha_composite(bg, overlay)

    # Handle output path
    if output_path is None:
        output_path = bg_path  # overwrite
    elif os.path.isdir(output_path):
        base = os.path.splitext(os.path.basename(bg_path))[0]
        output_path = os.path.join(output_path, f"{base}_pattern_{int(time.time())}.png")

    result.save(output_path)
    print(f"[+] Saved patterned image → {output_path}")

def sha3_512_salted(s: str, salt: str = None) -> bytes:

    hash_obj = hashlib.sha3_512()
    if salt is not None:
        hash_obj.update(str(salt).encode("utf-8"))
    hash_obj.update(str(s).encode("utf-8"))
    return hash_obj.digest()




def load_fonts(font_dir="./fonts"):
    fonts = {}
    if not os.path.isdir(font_dir):
        return fonts
    for fn in os.listdir(font_dir):
        if fn.lower().endswith((".otf", ".ttf")):
            try:
                font_name = os.path.splitext(fn)[0]
                fonts[font_name] = TTFont(os.path.join(font_dir, fn))
                print(f"[+] Loaded font: {fn}")
            except Exception as e:
                print(f"[!] Could not load font {fn}: {e}")
    return fonts

from svgwrite import path


# ------------------------
# Center seal as concentric colored dots
# ------------------------
def add_center_seal(dwg: svgwrite.Drawing, im: Image.Image, cx: float, cy: float, size_px: float, frame=True, step=4):
    im = im.convert("RGB").resize((int(size_px), int(size_px)), Image.LANCZOS)
    pixels = im.load()
    radius = size_px/2

    for row in range(0, im.height, step):
        for col in range(0, im.width, step):
            dx = col - radius
            dy = row - radius
            if dx*dx + dy*dy > radius*radius:
                continue  # omit dots outside circle
            r, g, b = pixels[col, row]
            dwg.add(dwg.circle(
                center=(cx - radius + col, cy - radius + row),
                r=step/2,
                fill=svgwrite.rgb(r, g, b),
                stroke="none",
                opacity=1.0
            ))

    if frame:
        dwg.add(dwg.circle(center=(cx, cy), r=radius+8, fill="none", stroke="#000", stroke_width=2.0))
        dwg.add(dwg.circle(center=(cx, cy), r=radius+16, fill="none", stroke="#000", stroke_width=1.0))



# Alternative version for more precise control with text elements
def add_mixed_font_text_precise(dwg, text, insert_pos, text_anchor="middle", font_size=12, 
                               chinese_font="FengGuangMingRui", english_font="Daemon Full Working",
                               chinese_padding=3, english_padding=1, fill_color="currentColor", stroke: str = "#000", stroke_width: float = 1 ):
    """
    More precise version with different padding for Chinese and English
    """
    
    chinese_pattern = r'[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]+'
    x, y = insert_pos
    segments = []
    last_end = 0
    
    # Split text
    for match in re.finditer(chinese_pattern, text):
        if match.start() > last_end:
            segments.append(('english', text[last_end:match.start()]))
        segments.append(('chinese', match.group()))
        last_end = match.end()
    
    if last_end < len(text):
        segments.append(('english', text[last_end:]))
    
    # Calculate positions
    segment_data = []
    total_width = 0
    
    for lang_type, segment_text in segments:
        if segment_text.strip():
            char_width = font_size * (0.85 if lang_type == 'chinese' else 0.55)
            width = len(segment_text) * char_width
            padding = chinese_padding if lang_type == 'chinese' else english_padding
            segment_data.append({
                'type': lang_type,
                'text': segment_text,
                'width': width,
                'padding': padding,
                'font': chinese_font if lang_type == 'chinese' else english_font,
                'offset': font_size * (0.01 if lang_type == 'chinese' else 0)
            })
            total_width += width + padding
        else:
            segment_data.append({'width': 0, 'padding': 0})
    
    if segment_data:
        total_width -= segment_data[-1]['padding']  # Remove last padding
    
    # Determine starting position
    if text_anchor == "middle":
        current_x = x - total_width / 2
    elif text_anchor == "end":
        current_x = x - total_width
    else:
        current_x = x
    
    # Render segments
    for i, segment in enumerate(segment_data):
        if segment.get('text'):
            dwg.add(dwg.text(segment['text'],
                            insert=(current_x, y + segment['offset'] - 20),
                            text_anchor="start",
                            font_size=font_size,
                            font_family=segment['font'],
                            fill=fill_color,
                            stroke=stroke,
                            stroke_width=stroke_width,
                            alignment_baseline="middle"))
            
            current_x += segment['width'] + segment['padding']
def add_mixed_font_text(dwg, text, insert_pos, text_anchor="middle", font_size=12, 
                       chinese_font="FengGuangMingRui", english_font="Daemon Full Working"):
    """
    Add text with mixed Chinese and English fonts to SVG drawing
    
    Parameters:
    dwg: svgwrite Drawing object
    text: input text containing mixed Chinese and English
    insert_pos: (x, y) position to insert text
    text_anchor: text anchor position
    font_size: base font size
    chinese_font: font family for Chinese characters
    english_font: font family for English characters
    """
    
    # Pattern to match Chinese characters (CJK Unified Ideographs)
    chinese_pattern = r'[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]+'
    
    x, y = insert_pos
    segments = []
    last_end = 0
    
    # Split text into Chinese and non-Chinese segments
    for match in re.finditer(chinese_pattern, text):
        # Add non-Chinese text before the match
        if match.start() > last_end:
            segments.append(('english', text[last_end:match.start()]))
        
        # Add Chinese text
        segments.append(('chinese', match.group()))
        last_end = match.end()
    
    # Add remaining non-Chinese text
    if last_end < len(text):
        segments.append(('english', text[last_end:]))
    
    # Calculate total text width for centering
    total_width = 0
    for lang_type, segment_text in segments:
        # Simple width estimation (adjust multiplier as needed)
        char_width = font_size * 0.6 if lang_type == 'chinese' else font_size * 0.5
        total_width += len(segment_text) * char_width
    
    # Starting position based on text anchor
    current_x = x
    if text_anchor == "middle":
        current_x = x - total_width / 2
    elif text_anchor == "end":
        current_x = x - total_width
    
    # Add each segment with appropriate font
    for lang_type, segment_text in segments:
        if segment_text.strip():  # Skip empty segments
            font_family = chinese_font if lang_type == 'chinese' else english_font
            
            dwg.add(dwg.text(segment_text, 
                            insert=(current_x, y),
                            text_anchor="start",
                            font_size=font_size,
                            font_family=font_family,
                            fill="currentColor"))
            
            # Update current position (simple width estimation)
            char_width = font_size * 0.6 if lang_type == 'chinese' else font_size * 0.6
            current_x += len(segment_text) * char_width
            
            
            

def clean_string(s: str) -> str:
    chinese_chars = re.findall(r'[\u4e00-\u9fff]', s)
    if chinese_chars:
        chinese_unicode = ''.join(str(ord(ch)) for ch in chinese_chars)
        latin_part = re.sub(r'[\d\W_]+', '', s, flags=re.UNICODE)
        latin_part = ''.join(ch for ch in latin_part if ch not in chinese_chars)
        return latin_part + chinese_unicode
    else:
        return re.sub(r'[\d\W_]+', '', s, flags=re.UNICODE)
# ----------------------
# Text seal with optional datetime
# ----------------------
from datetime import datetime
import math
from datetime import datetime

import math
from datetime import datetime

def add_text_seal(
    dwg, cy, radius, text_left, text_right, denom_color,
    inner_text=None, include_datetime=False,
    seed_text=None, serial_id=None,
    canvas_width=1600,
    chinese_font="FengGuangMingRui",
    english_font="Daemon Full Working",
):
    """
    Draws two seals at 1/4 and 3/4 of canvas width.
      - Left: 0.5 white bg, black text/circles, denom_color border
      - Right: 0.5 black bg, white text
    Optionally encodes seed_text/serial_id into rotary star patterns.
    """

    cx_left = canvas_width * 0.15
    cx_right = canvas_width * 0.85

    # --- Background Circles ---
    dwg.add(dwg.circle(center=(cx_left, cy), r=radius,
                       fill="white", fill_opacity=0.5,
                       stroke="black", stroke_width=2, stroke_opacity=1))

    dwg.add(dwg.circle(center=(cx_right, cy), r=radius-0.2,
                       fill="black", fill_opacity=0.5,
                       stroke="white", stroke_width=0.5, stroke_opacity=1))

   # --- Inner Decorative Circles ---
    for cx, txtcol, fillcol, symbol in [
        (cx_left, "black", "white", u"日"),  # Left = Sun
        (cx_right, "white", "black", u"月")  # Right = Moon
    ]:
        dwg.add(dwg.circle(center=(cx, cy), r=radius*0.95,
                        fill="none", stroke=denom_color, stroke_width=2))
        dwg.add(dwg.circle(center=(cx, cy), r=radius*0.85,
                        fill="none", stroke=denom_color, stroke_width=1))

        # Center symbol (Sun or Moon)
        dwg.add(dwg.text(symbol, insert=(cx, cy+radius*0.15),
                        text_anchor="middle", font_size=int(radius*0.5),
                        font_family="FengGuangMingRui", fill=txtcol))

    # Title text with precise mixed font alignment
    add_mixed_font_text_precise(dwg, clean_string(text_left), (cx_left, cy-radius-6.1), 
                            text_anchor="middle", 
                            font_size=int(radius*0.2),
                            chinese_font=chinese_font, 
                            english_font=english_font,
                            chinese_padding=32,    # More padding for Chinese segments
                            english_padding=32,
                            stroke="#FFF",
                            stroke_width=0.5,
                            fill_color="#000")

    add_mixed_font_text_precise(dwg, text_right, (cx_right, cy-radius-6.1),
                            text_anchor="middle",
                            font_size=int(radius*0.2),
                            chinese_font=chinese_font, 
                            english_font=english_font,
                            chinese_padding=32,
                            english_padding=32,
                            stroke="#000",
                            stroke_width=0.5,
                            fill_color="#FFF")


    # --- Rotary Dial Numbers ---
    if include_datetime:
        dt_string = datetime.now().strftime("%Y%m%d%H%M%S")
        n = len(dt_string)
        for cx, txtcol, code in [
            (cx_left, "black", seed_text),
            (cx_right, "white", serial_id)
        ]:
            points = []
            for i, char in enumerate(dt_string):
                angle = 2 * math.pi * i / n
                r = radius * 0.65
                x = cx + r * math.cos(angle)
                y = cy + r * math.sin(angle)
                dwg.add(dwg.text(char, insert=(x, y),
                                 font_size=int(radius*0.08), fill=txtcol,
                                 font_family="Daemon Full Working",
                                 text_anchor="middle", opacity=1))
                if code and char in code:
                    dwg.add(dwg.circle(center=(x, y), r=radius*0.05,
                                       fill=txtcol, opacity=0.6))
                    points.append((x, y))
            if len(points) > 1:
                for i in range(len(points)):
                    x1, y1 = points[i]
                    x2, y2 = points[(i+1) % len(points)]
                    dwg.add(dwg.line(start=(x1, y1), end=(x2, y2),
                                     stroke=txtcol, stroke_width=1, opacity=0.7))

def add_secondary_ring(dwg: svgwrite.Drawing, cx: float, cy: float, radius: float, seed: bytes, segments: int = 360, d_color: str = None):
    """
    Creates a geometric mandala-style ring with seed-colored shapes and black outlines.
    Features colored datapoints with black borders and adjusted ring thickness.
    """
    import random
    random.seed(int.from_bytes(seed, 'big'))
    
    # Use seed bytes for deterministic pattern generation
    seed_values = [b for b in seed]
    
    # Define ring thickness for geometric patterns
    ring_thickness = radius * 0.15
    inner_radius = radius - ring_thickness / 2
    outer_radius = radius + ring_thickness / 2
    
    # Color palette based on seed values
    def get_color_from_seed(seed_val):
        # Create deterministic colors from seed values
        hue = (seed_val * 137) % 360  # Golden ratio inspired
        saturation = 80 + (seed_val % 20)
        lightness = 40 + (seed_val % 15)
        
        # Convert HSL to HEX
        return hsl_to_hex(hue, saturation, lightness)

    def hsl_to_hex(h, s, l):
        """Convert HSL color values to HEX format"""
        h = h % 360
        s = max(0, min(100, s)) / 100
        l = max(0, min(100, l)) / 100
        
        # HSL to RGB conversion
        c = (1 - abs(2 * l - 1)) * s
        x = c * (1 - abs((h / 60) % 2 - 1))
        m = l - c / 2
        
        if 0 <= h < 60:
            r, g, b = c, x, 0
        elif 60 <= h < 120:
            r, g, b = x, c, 0
        elif 120 <= h < 180:
            r, g, b = 0, c, x
        elif 180 <= h < 240:
            r, g, b = 0, x, c
        elif 240 <= h < 300:
            r, g, b = x, 0, c
        else:
            r, g, b = c, 0, x
        
        # Convert RGB to HEX
        r = int((r + m) * 255)
        g = int((g + m) * 255)
        b = int((b + m) * 255)
        
        return f"#{r:02x}{g:02x}{b:02x}"
    dwg.add(dwg.circle(center=(cx, cy), r=outer_radius, fill=d_color, 
                    stroke="#000000", stroke_width=ring_thickness * 0.14, fill_opacity=0.5))  # Thicker
    dwg.add(dwg.circle(center=(cx, cy), r=inner_radius, fill="#FFF", 
                    stroke="#000000", stroke_width=ring_thickness * 0.06, fill_opacity=0.5))  # Thinner
    dwg.add(dwg.circle(center=(cx, cy), r=(inner_radius-40), fill="#000", 
                    stroke="#000000", stroke_width=ring_thickness * 0.03, fill_opacity=0.5))  # Thicker
    # Create geometric patterns with radial alignment
    for i in range(segments):
        angle = 2 * math.pi * i / segments
        
        # Use seed for deterministic pattern spacing
        spacing_seed = seed_values[i % len(seed_values)]
        
        # Only draw elements at specific radial intervals based on seed
        should_draw = (spacing_seed % 8) < 3  # 3/8 elements drawn
        
        if should_draw:
            # Seed-based radial positioning
            position_seed = seed_values[(i + 17) % len(seed_values)]
            radial_position = 0.2 + 0.6 * (position_seed / 255)
            r = inner_radius + (outer_radius - inner_radius) * radial_position
            x = cx + r * math.cos(angle)
            y = cy + r * math.sin(angle)
            
            # Geometric elements only - seed-based selection
            shape_seed = seed_values[(i + 7) % len(seed_values)]
            shape_type = shape_seed % 4
            
            # Get color from seed
            color_seed = seed_values[(i + 11) % len(seed_values)]
            shape_color = get_color_from_seed(color_seed)
            
            # Calculate rotation angle (90 degrees to center - radial alignment)
            rotation_angle = math.degrees(angle) + 90
            
            # Determine if shape should be solid or knocked-out
            is_solid = (shape_seed % 2 == 0)
            
            if shape_type == 0:
                # Square
                size_base = ring_thickness * 0.22
                size_var = 0.3 * (shape_seed / 255)
                size = size_base * (0.7 + size_var)
                
                if is_solid:
                    # Solid colored square with black border
                    dwg.add(dwg.rect(insert=(x-size/2, y-size/2), 
                                    size=(size, size), fill=shape_color, 
                                    stroke="#000000", stroke_width=size*0.08,
                                    transform=f"rotate({rotation_angle},{x},{y})"))
                else:
                    # Square with knocked-out center and colored/black border
                    hole_size = size * 0.6
                    path_data = f"M {x-size/2} {y-size/2} " \
                              f"L {x+size/2} {y-size/2} " \
                              f"L {x+size/2} {y+size/2} " \
                              f"L {x-size/2} {y+size/2} Z " \
                              f"M {x-hole_size/2} {y-hole_size/2} " \
                              f"L {x+hole_size/2} {y-hole_size/2} " \
                              f"L {x+hole_size/2} {y+hole_size/2} " \
                              f"L {x-hole_size/2} {y+hole_size/2} Z"
                    dwg.add(dwg.path(d=path_data, fill="#ffffff", fill_rule="evenodd", 
                                    stroke=shape_color, stroke_width=size*0.12,
                                    transform=f"rotate({rotation_angle},{x},{y})"))
                
            elif shape_type == 1:
                # Diamond
                size_base = ring_thickness * 0.26
                size_var = 0.4 * (shape_seed / 255)
                size = size_base * (0.6 + size_var)
                
                if is_solid:
                    # Solid colored diamond with black border
                    points = [
                        (x, y-size/2), (x+size/2, y), 
                        (x, y+size/2), (x-size/2, y)
                    ]
                    dwg.add(dwg.polygon(points=points, fill=shape_color, 
                                       stroke="#000000", stroke_width=size*0.08,
                                       transform=f"rotate({rotation_angle},{x},{y})"))
                else:
                    # Diamond with knocked-out center and colored/black border
                    hole_size = size * 0.5
                    outer_points = [
                        (x, y-size/2), (x+size/2, y), 
                        (x, y+size/2), (x-size/2, y)
                    ]
                    inner_points = [
                        (x, y-hole_size/2), (x+hole_size/2, y), 
                        (x, y+hole_size/2), (x-hole_size/2, y)
                    ]
                    path_data = f"M {outer_points[0][0]} {outer_points[0][1]} " \
                              f"L {outer_points[1][0]} {outer_points[1][1]} " \
                              f"L {outer_points[2][0]} {outer_points[2][1]} " \
                              f"L {outer_points[3][0]} {outer_points[3][1]} Z " \
                              f"M {inner_points[0][0]} {inner_points[0][1]} " \
                              f"L {inner_points[1][0]} {inner_points[1][1]} " \
                              f"L {inner_points[2][0]} {inner_points[2][1]} " \
                              f"L {inner_points[3][0]} {inner_points[3][1]} Z"
                    dwg.add(dwg.path(d=path_data, fill="#ffffff", fill_rule="evenodd", 
                                    stroke=shape_color, stroke_width=size*0.12,
                                    transform=f"rotate({rotation_angle},{x},{y})"))
                
            elif shape_type == 2:
                # Circle
                size_base = ring_thickness * 0.18
                size_var = 0.5 * ((shape_seed + 11) % 256 / 255)
                size = size_base * (0.5 + size_var)
                
                if is_solid:
                    # Solid colored circle with black border
                    dwg.add(dwg.circle(center=(x, y), r=size, fill=shape_color, 
                                      stroke="#000000", stroke_width=size*0.08))
                else:
                    # Circle with knocked-out center and colored/black border
                    hole_size = size * 0.6
                    path_data = f"M {x+size} {y} " \
                              f"A {size} {size} 0 1 1 {x-size} {y} " \
                              f"A {size} {size} 0 1 1 {x+size} {y} Z " \
                              f"M {x+hole_size} {y} " \
                              f"A {hole_size} {hole_size} 0 1 1 {x-hole_size} {y} " \
                              f"A {hole_size} {hole_size} 0 1 1 {x+hole_size} {y} Z"
                    dwg.add(dwg.path(d=path_data, fill="#ffffff", fill_rule="evenodd", 
                                    stroke=shape_color, stroke_width=size*0.12))
                
            else:
                # Triangle
                size_base = ring_thickness * 0.24
                size_var = 0.6 * (shape_seed / 255)
                size = size_base * (0.4 + size_var)
                flip = 1 if (shape_seed % 2 == 0) else -1
                
                if is_solid:
                    # Solid colored triangle with black border
                    points = [
                        (x, y - flip * size/2), 
                        (x + size/2, y + flip * size/2), 
                        (x - size/2, y + flip * size/2)
                    ]
                    dwg.add(dwg.polygon(points=points, fill=shape_color, 
                                       stroke="#000000", stroke_width=size*0.08,
                                       transform=f"rotate({rotation_angle},{x},{y})"))
                else:
                    # Triangle with knocked-out center and colored/black border
                    hole_size = size * 0.5
                    outer_points = [
                        (x, y - flip * size/2), 
                        (x + size/2, y + flip * size/2), 
                        (x - size/2, y + flip * size/2)
                    ]
                    inner_points = [
                        (x, y - flip * hole_size/2), 
                        (x + hole_size/2, y + flip * hole_size/2), 
                        (x - hole_size/2, y + flip * hole_size/2)
                    ]
                    path_data = f"M {outer_points[0][0]} {outer_points[0][1]} " \
                              f"L {outer_points[1][0]} {outer_points[1][1]} " \
                              f"L {outer_points[2][0]} {outer_points[2][1]} Z " \
                              f"M {inner_points[0][0]} {inner_points[0][1]} " \
                              f"L {inner_points[1][0]} {inner_points[1][1]} " \
                              f"L {inner_points[2][0]} {inner_points[2][1]} Z"
                    dwg.add(dwg.path(d=path_data, fill="#ffffff", fill_rule="evenodd", 
                                    stroke=shape_color, stroke_width=size*0.12,
                                    transform=f"rotate({rotation_angle},{x},{y})"))
            
            # Add black spoke from inner radius to glyph element
            spoke_seed = seed_values[(i + 29) % len(seed_values)]
            if spoke_seed % 5 == 0:
                inner_x = cx + inner_radius * math.cos(angle)
                inner_y = cy + inner_radius * math.sin(angle)
                spoke_width = ring_thickness * 0.018  # Slightly thinner
                dwg.add(dwg.line(start=(inner_x, inner_y), end=(x, y), 
                                stroke="#000000", stroke_width=spoke_width, opacity=0.8))

    # Add solid black inner and outer ring borders with adjusted thickness
    # Thinner inner border, thicker outer border
    
    







def add_chinese_microprint(dwg: svgwrite.Drawing, cx:int, cy:int, radius:int, text="壹佰 卢纳币",
                           repetitions=1, font_family="FengGuangMingRui", font_size=8):
    """Add Chinese microprint around a small circle as a security feature."""
    import math
    n = repetitions
    for i in range(n):
        angle = 2*math.pi*i/n
        x = cx + radius*math.cos(angle)
        y = cy + radius*math.sin(angle)
        rotation = math.degrees(angle) + 90
        dwg.add(dwg.text(text,
                         insert=(x,y),
                         font_size=font_size,
                         font_family=font_family,
                         fill="#000",
                         opacity=1,
                         text_anchor="middle",
                         alignment_baseline="middle",
                         transform=f"rotate({rotation},{x},{y})"))
import hashlib
import json
import base64
import zlib
from datetime import datetime
import os


def read_prompt_file(filepath: str, default: str = "") -> str:
    """
    Read a prompt file and return its contents as a single string.
    If the file doesn't exist, return the provided default string.
    """
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read().strip()
    else:
        return default.strip()

def generate_kawaii_mural_from_background(denomination, filename="background_prompt.txt"):
    """
    Generate a kawaii East Asian mural/scenery prompt based on a base background prompt,
    and append a color palette derived from the denomination.
    """
    # Read base prompt from file
    base_prompt = read_prompt_file(filename)
    
    # Generate denomination-based color palette
    palette = denomination_to_color(denomination)  # e.g., "pastel pinks and blues"
    
    # Combine into final prompt
    prompt = (
        f"{base_prompt}, kawaii hand-drawn oekaki style, playful animals and dolls, "
        f"Studio Ghibli-inspired, whimsical, painterly, soft textures, "
        f"use a palette dominated by {palette} in the style of Chinese DMT Studio Ghibli"
    )
    
    return prompt



def number_to_chinese(num: int) -> str:
    numerals = {
        0:"零", 1:"壹", 2:"贰", 3:"叁", 4:"肆",
        5:"伍", 6:"陆", 7:"柒", 8:"捌", 9:"玖"
    }
    units = ["", "拾", "佰", "仟", "万", "拾万", "佰万", "仟万", "亿"]
    s = str(num)
    result = ""
    for i, digit in enumerate(s[::-1]):
        n = int(digit)
        if n != 0:
            result = numerals[n] + units[i] + result
        elif not result.startswith("零"):
            result = "零" + result
    return result.rstrip("零")
from datetime import datetime
import random
import hashlib
import secrets
def cm_to_px(cm, dpi=300.0):
    """
    Convert centimeters to pixels.
    
    Parameters:
        cm: float - measurement in centimeters
        dpi: float - dots per inch (default: 300 DPI)
    
    Returns:
        float - measurement in pixels
    """
    return cm * dpi / 2.54
def add_subtle_frame_and_microgrid(dwg, W: int, H: int, border_info: dict, denomination: int, timestamp_ms: int, seed_hash: bytes):
    """Proxy to widgets implementation."""
    return _widget_add_subtle_frame_and_microgrid(
        dwg,
        W,
        H,
        border_info,
        denomination,
        timestamp_ms,
        seed_hash,
    )
# --- Dynamic data generation ---
def generate_timestamp():
    """Return current date-time as YYYYMMDD-HHMM string"""
    return datetime.now().strftime("%Y%m%d-%H%M")

import hashlib
import secrets
from datetime import datetime
import base64

# Alternative version with checksum for validation
def generate_serial_id_with_checksum():
    """
    Generate serial ID with built-in checksum for validation
    """
    ts = int(datetime.now().timestamp() * 1000000)
    salt = secrets.token_bytes(3)
    raw = f"{ts}-".encode() + salt
    h = hashlib.sha3_256(raw).digest()
    
    # Take first 10 bytes for serial
    serial_bytes = h[:10]
    serial_b64 = base64.urlsafe_b64encode(serial_bytes).decode('ascii').replace('=', '')[:14]
    
    # Add checksum (last 2 bytes of hash)
    checksum_bytes = h[-2:]
    checksum_b64 = base64.urlsafe_b64encode(checksum_bytes).decode('ascii').replace('=', '')[:3]
    
    return f"SN-{serial_b64}-{checksum_b64}"

from PIL import Image, ImageDraw, ImageFont







# -----------------------------
# Add security background
# -----------------------------
import math, hashlib, colorsys
from datetime import datetime
import svgwrite


def add_center_text(
    dwg,
    W: int,
    H: int,
    title: str,
    phrase: str,
    denom_color: str,
    title_font: str = "FengGuangMingRui",
    phrase_font: str = "FengGuangMingRui",
):
    # Define padding in pixels
    TOP_PADDING = int(0.5 * 30 * 4)      # ~0.5 cm
    BOTTOM_PADDING = int(0.5 * 30 * 4)   # ~0.5 cm

    # Stroke thickness in pixels (0.05 cm at 300 DPI)
    STROKE_WIDTH = 0.05 * 300 / 2.54

    # Helper to add text with outline
    def add_text_with_outline(x, y, text, font_size, fill_color, stroke_color, baseline, font_family):
        # Stroke first
        dwg.add(dwg.text(
            text,
            insert=(x, y),
            font_size=font_size,
            font_family=font_family,
            fill=fill_color,
            stroke="white",
            stroke_width=STROKE_WIDTH,
            text_anchor="middle",
            alignment_baseline=baseline,
            opacity=0.5
        ))
        # Fill on top
        dwg.add(dwg.text(
            text,
            insert=(x, y),
            font_size=font_size,
            font_family=font_family,
            fill=fill_color,
            stroke=stroke_color,
            text_anchor="middle",
            alignment_baseline=baseline,
            opacity=1
        ))

    # Title near the top
    add_text_with_outline(x=(W/2), y=TOP_PADDING, text=title, font_size=int(H*0.12), fill_color="black", stroke_color=denom_color, baseline="hanging", font_family=title_font)

    # Phrase near the bottom
    add_text_with_outline(x=(W/2), y=(H - BOTTOM_PADDING), text=phrase, font_size=int(H*0.08), fill_color="black", stroke_color=denom_color, baseline="baseline", font_family=phrase_font)



def generate_timestamp_ms():
    """
    Generate current timestamp in milliseconds with microsecond precision.
    Returns integer representing milliseconds since epoch.
    """
    return int(time.time() * 1000)

# Alternative version that includes microseconds for even more precision:
def generate_timestamp_ms_precise():
    """
    Generate timestamp with microsecond precision.
    Returns integer representing milliseconds.microseconds.
    """
    now = datetime.now()
    return int(now.timestamp() * 1000) + now.microsecond // 1000
import colorsys

def hsl_to_rgb_string(h, s, l):
    """Convert HSL (0–360, 0–100, 0–100) to rgb(r,g,b) CSS string."""
    h = h / 360.0
    s = s / 100.0
    l = l / 100.0
    r, g, b = colorsys.hls_to_rgb(h, l, s)
    return f"rgb({int(r*255)}, {int(g*255)}, {int(b*255)})"

def denomination_color(denom: int) -> str:
    """
    Returns a light ROYGBIV hex color based on the denomination.
    Maps 1 → Red, 100,000,000 → Violet on a log scale.
    """
    # Clamp between 1 and 100,000,000
    denom = max(1, min(100_000_000, denom))

    # Normalize exponent (log10 scale)
    exp = math.log10(denom) / math.log10(100_000_000)  # 0.0 → 1.0

    # ROYGBIV palette
    roygbiv = [
        (255, 0, 0),       # Red
        (255, 165, 0),     # Orange
        (255, 255, 0),     # Yellow
        (0, 128, 0),       # Green
        (0, 0, 255),       # Blue
        (75, 0, 130),      # Indigo
        (143, 0, 255)      # Violet
    ]

    # Find segment in ROYGBIV
    idx = int(exp * (len(roygbiv) - 1))
    frac = exp * (len(roygbiv) - 1) - idx

    # Interpolate between two colors
    c1 = roygbiv[idx]
    c2 = roygbiv[min(idx + 1, len(roygbiv) - 1)]
    r = int(c1[0] + (c2[0] - c1[0]) * frac)
    g = int(c1[1] + (c2[1] - c1[1]) * frac)
    b = int(c1[2] + (c2[2] - c1[2]) * frac)

    # Light tint: blend 70% white + 30% color
    r = int(0.7 * 255 + 0.3 * r)
    g = int(0.7 * 255 + 0.3 * g)
    b = int(0.7 * 255 + 0.3 * b)

    return f"#{r:02X}{g:02X}{b:02X}"

def get_random_background(bg_dir="./backgrounds"):
    files = [
        os.path.join(bg_dir, f)
        for f in os.listdir(bg_dir)
        if os.path.isfile(os.path.join(bg_dir, f)) and f.lower().endswith((".png", ".jpg", ".jpeg"))
    ]
    if not files:
        raise FileNotFoundError(f"No background images found in {bg_dir}")
    return random.choice(files)


import qrcode
from PIL import Image, ImageDraw
import math
try:
    import qrcode
    QR_AVAILABLE = True
except ImportError:
    QR_AVAILABLE = False
    print("QR code generation not available. Install qrcode[pil] package.")



def generate_fantasy_banknote(seed_text: str, input_image_path: str, outfile_svg: str,
                               width_mm: float = 160.0, height_mm: float = 60.0,
                               title: str = "灵国国库", subtitle: str = "天圆地方", serial_id: str = "SERIALID", timestamp:str = "TIMESTAMP",
                               denomination: str = "100 卢纳币", specimen: bool = True,
                               fonts = {}, bg_dir: str = "./backgrounds", background_prompt: str = "",
                               progress_callback=None,
                               border_inset_mm: float = 0.5,
                               border_thickness_mm: float = 3.0,
                               enable_qr_border: bool = True,
                               enable_background: bool = True,
                               background_filter: str = "vectorize",
                               background_margin: int = 60,
                               background_segments: int = 1024,
                               mosaic_font: str = "Daemon Full Working",
                               mosaic_font_dir: str = "./fonts",
                               mosaic_font_size_mm: float = 1.1,
                               mosaic_charset: str = "LUNAMINT",
                               mosaic_invert: bool = False,
                               mosaic_snap_grid_px: float = 16.0,
                               mosaic_opacity: float = 1.0,
                               glyph_font: str = "Daemon Full Working",
                               glyph_font_dir: str = "./fonts",
                               glyph_font_size_mm: float = 1.2,
                               glyph_charset: str = "LUNAMINT",
                               glyph_invert: bool = False,
                               glyph_snap_grid_px: float = 16.0,
                               glyph_opacity: float = 0.9,
                               glyph_fill_dark: str = "#111111",
                               glyph_fill_light: str = "#f7f2eb",
                               glyph_stroke_dark: str = "#0b0b0b",
                               glyph_stroke_light: str = "#999999",
                               glyph_stroke_width_mm: float = 0.12,
                               glyph_inset_scale: float = 0.8,
                               glyph_outset_scale: float = 1.1,
                               glyph_threshold: int = 140,
                               glyph_colorize: bool = False,
                               glyph_cell_padding_mm: float = 0.0,
                               enable_microgrid: bool = True,
                               enable_decorative_border: bool = True,
                               enable_center_seal: bool = True,
                               enable_center_text: bool = True,
                               enable_corner_decorations: bool = True,
                               enable_corner_denoms: bool = True,
                               enable_microprint: bool = True,
                               microprint_repetitions: int = 16,
                               microprint_text: str | None = None,
                               center_radius_scale: float = 0.32,
                               small_radius_scale: float = 0.25,
                               text_seal_scale: float = 0.65,
                               secondary_ring_scale: float = 0.88,
                               center_seal_scale: float = 1.2,
                               title_font: str = "FengGuangMingRui",
                               subtitle_font: str = "FengGuangMingRui",
                               corner_font: str = "Daemon Full Working",
                               seal_chinese_font: str = "FengGuangMingRui",
                               seal_english_font: str = "Daemon Full Working",
                               showcase_widgets: bool = False,
                               ascii_stamp_prompt: str | None = None,
                               showcase_labels: bool = False,
                               label_font: str = "Daemon Full Working",
                               label_size_mm: float = 2.6,
                               qr_url: str | None = None,
                               require_signed_qr: bool = False,
                               sm2_private_key: str | None = None,
                               sm2_public_key: str | None = None,
                               verify_base_url: str | None = None,
                               issuer_id: str | None = None,
                               validity_days: int | None = None,
                               pow_difficulty: int | None = None,
                               sm4_key: str | None = None,
                               sm4_enable: bool | None = None,
                               qr_stamp_width: int = 60,
                               qr_stamp_height: int = 60,
                               qr_rows: int = 6,
                               qr_side: str = "both",
                               qr_stamp: bool = True,
                               aztec: bool = True,
                               aztec_scale: float = 3.0,
                               aztec_border: float = 12.0,
                               aztec_rotation_base: float = 0.0,
                               aztec_offset_x: float = 360.0,
                               aztec_offset_y: float = 0.0,
                               aztec_border_opacity: float = 0.5):
    timestamp_ms = timestamp or generate_timestamp_ms_precise()
    serial_id = serial_id or generate_serial_id_with_checksum()
    W = mm_to_px(width_mm)
    H = mm_to_px(height_mm)
    dwg = svgwrite.Drawing(outfile_svg, size=(W,H), viewBox=f"0 0 {W} {H}")
    
    denom_value = denom_to_int(denomination)
    denom_exponent = int(round(math.log10(denom_value))) if denom_value > 0 else 0
    seed_text=seed_text
    seed_hash = sha3_512_salted(seed_text, serial_id)
    dwg.add(dwg.rect(insert=(0,0), size=(W,H), fill=denomination_color(denom=denom_value)))

    if progress_callback:
        progress_callback("Adding QR border")
    
    if enable_qr_border:
        border_info = add_qr_like_border(
            dwg,
            seed_text,
            W,
            H,
            serial_id,
            timestamp_ms,
            inset_mm=border_inset_mm,
            border_thickness_mm=border_thickness_mm,
        )
    else:
        border_info = {
            "diamond_start_x": 0.0,
            "diamond_start_y": 0.0,
            "diamond_width": float(W),
            "diamond_height": float(H),
            "image_start_x": 0.0,
            "image_start_y": 0.0,
            "image_width": float(W),
            "image_height": float(H),
        }
    
    if progress_callback:
        progress_callback("Rendering background")
    if enable_background:
        filter_name = (background_filter or "vectorize").strip().lower()
        if filter_name in {"letter_mosaic", "letter-mosaic", "mosaic", "letters"}:
            add_letter_mosaic_background(
                dwg=dwg,
                W=W,
                H=H,
                seed_text=seed_text,
                bg_dir=bg_dir,
                margin=background_margin,
                background_prompt=background_prompt,
                denomination=denomination,
                config=LetterMosaicConfig(
                    font_name=mosaic_font,
                    font_dir=mosaic_font_dir,
                    font_size_mm=mosaic_font_size_mm,
                    charset=mosaic_charset,
                    invert=mosaic_invert,
                    snap_grid_px=mosaic_snap_grid_px,
                    opacity=mosaic_opacity,
                ),
            )
        elif filter_name in {"glyph_grid", "glyph-grid", "glyphs", "grid"}:
            add_glyph_grid_background(
                dwg=dwg,
                W=W,
                H=H,
                seed_text=seed_text,
                bg_dir=bg_dir,
                margin=background_margin,
                background_prompt=background_prompt,
                denomination=denomination,
                config=GlyphGridConfig(
                    options=GlyphGridOptions(
                        font_name=glyph_font,
                        font_dir=glyph_font_dir,
                        font_size_mm=glyph_font_size_mm,
                        charset=glyph_charset,
                        invert=glyph_invert,
                        snap_grid_px=glyph_snap_grid_px,
                        opacity=glyph_opacity,
                        fill_dark=glyph_fill_dark,
                        fill_light=glyph_fill_light,
                        stroke_dark=glyph_stroke_dark,
                        stroke_light=glyph_stroke_light,
                        stroke_width_mm=glyph_stroke_width_mm,
                        inset_scale=glyph_inset_scale,
                        outset_scale=glyph_outset_scale,
                        threshold=glyph_threshold,
                        colorize=glyph_colorize,
                        cell_padding_mm=glyph_cell_padding_mm,
                    )
                ),
            )
        elif filter_name in {"triangle_mosaic", "triangle-mosaic", "triangles"}:
            add_triangle_mosaic_background(
                dwg=dwg,
                W=W,
                H=H,
                seed_text=seed_text,
                bg_dir=bg_dir,
                margin=background_margin,
                background_prompt=background_prompt,
                denomination=denomination,
                config=TriangleMosaicConfig(),
            )
        else:
            add_vectorized_background(
                dwg=dwg,
                W=W,
                H=H,
                seed_text=seed_text,
                bg_dir=bg_dir,
                margin=background_margin,
                n_segments=background_segments,
                background_prompt=background_prompt,
                denomination=denomination,
            )
    
    if progress_callback:
        progress_callback("Adding microgrid and border")
    if enable_microgrid:
        add_subtle_frame_and_microgrid(dwg, W, H, border_info, denom_value, timestamp_ms, to_bytes(seed_hash))
    if enable_decorative_border:
        add_decorative_border(dwg, W, H, border_info, denom_value, timestamp_ms)

    if showcase_widgets:
        label_size_px = mm_to_px(label_size_mm)
        def _label(text: str, x_mm: float, y_mm: float) -> None:
            dwg.add(dwg.text(
                text,
                insert=(mm_to_px(x_mm), mm_to_px(y_mm)),
                font_size=label_size_px,
                font_family=label_font,
                fill="#222",
                opacity=0.85,
            ))

        add_barcode_border_mm(
            dwg,
            x_mm=2,
            y_mm=2,
            width_mm=width_mm - 4,
            height_mm=height_mm - 4,
            border_thickness_mm=2.2,
            module_mm=0.6,
            data=f"{seed_text}-{serial_id}",
            opacity=0.6,
        )
        if showcase_labels:
            _label("Barcode Border", 6, 6)
        add_tile_border_mm(
            dwg,
            x_mm=4,
            y_mm=4,
            width_mm=width_mm - 8,
            height_mm=height_mm - 8,
            border_thickness_mm=1.6,
            tile_mm=1.4,
            data=f"{serial_id}-{denom_value}",
            opacity=0.45,
        )
        if showcase_labels:
            _label("Tile Border", width_mm - 36, 6)
        add_security_thread_mm(
            dwg,
            x_mm=12,
            y_mm=6,
            height_mm=height_mm - 12,
            width_mm=1.4,
            microtext="LUNAMINT",
            microtext_spacing_mm=3.2,
            opacity=0.28,
        )
        if showcase_labels:
            _label("Security Thread", 14, 14)
        add_guilloche_band_mm(
            dwg,
            x_mm=18,
            y_mm=height_mm * 0.2,
            width_mm=width_mm - 36,
            height_mm=4.5,
            amplitude_mm=0.6,
            wavelength_mm=5.2,
            stroke_width_mm=0.08,
            opacity=0.55,
            layers=5,
        )
        if showcase_labels:
            _label("Guilloche Band", 22, height_mm * 0.2 - 2)
        add_rosette_mm(
            dwg,
            cx_mm=width_mm * 0.22,
            cy_mm=height_mm * 0.52,
            radius_mm=10,
            petals=14,
            opacity=0.6,
        )
        if showcase_labels:
            _label("Rosette", width_mm * 0.16, height_mm * 0.38)
        add_godseye_mm(
            dwg,
            cx_mm=width_mm * 0.78,
            cy_mm=height_mm * 0.52,
            radius_mm=9,
            rings=7,
            rotation_deg=18,
            opacity=0.6,
        )
        if showcase_labels:
            _label("Godseye", width_mm * 0.72, height_mm * 0.38)
        add_watermark_medallion_mm(
            dwg,
            cx_mm=width_mm * 0.5,
            cy_mm=height_mm * 0.52,
            radius_mm=14,
            text="LUNAMINT",
            opacity=0.16,
        )
        if showcase_labels:
            _label("Watermark", width_mm * 0.46, height_mm * 0.32)
        add_iris_lines_mm(
            dwg,
            cx_mm=width_mm * 0.5,
            cy_mm=height_mm * 0.52,
            radius_mm=14,
            lines=120,
            opacity=0.2,
        )
        if showcase_labels:
            _label("Iris Lines", width_mm * 0.47, height_mm * 0.72)
        add_fractal_stamp_mm(
            dwg,
            x_mm=width_mm - 26,
            y_mm=height_mm - 18,
            size_mm=12,
            iterations=3,
            angle_deg=60,
            opacity=0.45,
        )
        if showcase_labels:
            _label("Fractal Stamp", width_mm - 42, height_mm - 6)
        add_serial_panel_mm(
            dwg,
            x_mm=width_mm * 0.58,
            y_mm=height_mm - 12,
            width_mm=38,
            height_mm=8,
            serial_text=str(serial_id),
        )
        if showcase_labels:
            _label("Serial Panel", width_mm * 0.58, height_mm - 14)
        add_microtext_line_mm(
            dwg,
            text="LUNAMINT • SECURITY • STARFORGE",
            x_mm=8,
            y_mm=height_mm - 4,
            width_mm=width_mm - 16,
            font_size_mm=0.6,
            opacity=0.4,
        )
        if showcase_labels:
            _label("Microtext Line", width_mm * 0.35, height_mm - 6)
        if ascii_stamp_prompt:
            try:
                opts = AsciiStampOptions(font_name=seal_english_font)
                add_ascii_stamp_from_prompt_mm(
                    dwg,
                    prompt=ascii_stamp_prompt,
                    x_mm=width_mm * 0.36,
                    y_mm=height_mm * 0.22,
                    width_mm=30,
                    height_mm=22,
                    options=opts,
                )
                if showcase_labels:
                    _label("ASCII Stamp", width_mm * 0.36, height_mm * 0.2)
            except Exception:
                pass
    im = None
    if input_image_path and os.path.exists(input_image_path):
        im = Image.open(input_image_path).convert("RGB")
    else:
        im = Image.new("RGB", (512, 512), color=(235, 235, 235))
    
    center_px_radius = int(min(W, H) * center_radius_scale)
    cx, cy = W//2, H//2
    cy = H//2
    d_color = denomination_to_color(denom_exponent)
    small_radius = min(W, H) * small_radius_scale
    text_left = f"{str(seed_text)}"
    text_right= f"{str(serial_id)}"
    if progress_callback:
        progress_callback("Placing center seal and text")
    if enable_center_seal:
        add_text_seal(
            dwg,
            cy=cy,
            radius=small_radius * text_seal_scale,
            text_left=text_left,
            text_right=text_right,
            denom_color=d_color,
            inner_text="日",
            include_datetime=True,
            seed_text=seed_text,
            serial_id=serial_id,
            canvas_width=W,
            chinese_font=seal_chinese_font,
            english_font=seal_english_font,
        )
        add_secondary_ring(dwg, cx, cy, radius=center_px_radius * secondary_ring_scale, seed=to_bytes(seed_hash), segments=360, d_color=d_color)
        add_center_seal(dwg, im, cx, cy, center_px_radius * center_seal_scale)
    if enable_center_text:
        add_center_text(
            dwg,
            W,
            H,
            title,
            subtitle,
            denom_color=denomination_to_color(denom_exponent),
            title_font=title_font,
            phrase_font=subtitle_font,
        )
    if enable_corner_decorations:
        add_functional_corner_decorations(dwg, W, H, denomination, timestamp_ms, serial_id)
    if enable_corner_denoms:
        add_corner_denoms(dwg, W, H, str(denom_value), font_family=corner_font)
    chinese_value = number_to_chinese(denom_value)
    if enable_microprint:
        if progress_callback:
            progress_callback("Adding microprint")
        microprint_value = microprint_text or f"{chinese_value} 卢纳币"
        add_chinese_microprint(
            dwg, cx, cy, radius=int(center_px_radius * 0.7),
            text=microprint_value,
            repetitions=microprint_repetitions,
        )
    if not qr_url:
        cfg = load_crypto_config()
        if sm2_private_key:
            cfg.sm2_private_key = sm2_private_key
        if sm2_public_key:
            cfg.sm2_public_key = sm2_public_key
        if verify_base_url:
            cfg.verify_base_url = verify_base_url
        if issuer_id:
            cfg.issuer_id = issuer_id
        if validity_days is not None:
            cfg.validity_days = validity_days
        if pow_difficulty is not None:
            cfg.pow_difficulty = pow_difficulty
        if sm4_key:
            cfg.sm4_key = sm4_key
        if sm4_enable is not None:
            cfg.encrypt_payload = sm4_enable
        try:
            qr_url = build_qr_url(serial_id, denom_value, int(timestamp_ms), config=cfg)
        except RuntimeError:
            if require_signed_qr:
                raise
            qr_url = f"https://bank.lunamint.local/verify/{serial_id}"
    
    if progress_callback:
        progress_callback("Adding QR and Aztec elements")
    if qr_stamp:
        add_roygbiv_qr_style(
            dwg,
            W=W,
            H=H,
            url=qr_url,
            stamp_width=qr_stamp_width,
            stamp_height=qr_stamp_height,
            rows=qr_rows,
            side=qr_side,
        )

    if aztec:
        matrix = safe_make_matrix(qr_url)
        if matrix is not None:
            add_colored_aztec_to_canvas(
                dwg,
                cx=cx - aztec_offset_x,
                cy=cy - aztec_offset_y,
                matrix=matrix,
                scale=aztec_scale,
                border=aztec_border,
                denom_exponent=denom_exponent,
                rotation=aztec_rotation_base,
                border_opacity=aztec_border_opacity,
            )
            add_colored_aztec_to_canvas(
                dwg,
                cx=cx + aztec_offset_x,
                cy=cy - aztec_offset_y,
                matrix=matrix,
                scale=aztec_scale,
                border=aztec_border,
                denom_exponent=denom_exponent,
                rotation=aztec_rotation_base + 180,
                border_opacity=aztec_border_opacity,
            )
    # Add specimen text if needed
    if specimen:
        dwg.add(dwg.text("SPECIMEN", insert=(W*0.5,H*0.92),
                         font_size=int(H*0.08), fill="#333", font_family="monospace", 
                         text_anchor="middle", opacity=0.75))
    

    if progress_callback:
        progress_callback("Saving vector output")
    dwg.save()
    print(f"[+] Saved: {outfile_svg}")
from PIL import ImageStat

def to_bytes(data, encoding='utf-8'):
    """
    Convert different types of data to bytes.

    Parameters:
        data: str, int, float, or bytes
        encoding: str, encoding to use if data is a string

    Returns:
        bytes representation of the input
    """
    if isinstance(data, bytes):
        return data
    elif isinstance(data, str):
        return data.encode(encoding)
    elif isinstance(data, int):
        # Convert int to bytes (big-endian, minimum number of bytes)
        length = (data.bit_length() + 7) // 8 or 1
        return data.to_bytes(length, byteorder='big', signed=True)
    elif isinstance(data, float):
        import struct
        return struct.pack('>d', data)  # 8-byte double, big-endian
    else:
        raise TypeError(f"Cannot convert type {type(data)} to bytes")
def denom_to_int(denom_str: str) -> int:
    """
    Convert a denomination string like "100 yuan" to an integer 100.
    Ignores non-digit characters.
    """
    import re
    match = re.search(r'\d+', denom_str)
    if match:
        return int(match.group())
    raise ValueError(f"No numeric part found in denomination '{denom_str}'")
def add_corner_denoms(dwg, W: int, H: int, denom_str: str, font_family: str = "Daemon Full Working"):
    """
    Draws denomination numbers in all four corners with white outline 0.05cm behind
    fill and fill opacity 0.9. Bottom ones remain aligned as before.
    """

    # Format denomination with commas
    try:
        denom_formatted = f"{int(denom_str):,}"
    except ValueError:
        denom_formatted = denom_str

    first_digit = denom_formatted[0]
    rest_digits = denom_formatted[1:]

    # Sizes
    BIG_FONT = 128
    SMALL_FONT = 72

    # Padding
    PADDING = int(0.5 * 30 * 3.78)

    # Stroke thickness in pixels (0.05 cm at 300 DPI)
    STROKE_WIDTH = 0.05 * 300 / 2.54

    # Colors for corners
    COLORS = ["red", "green", "blue", "black"]

    # Helper to add text with stroke behind
    def add_text_with_outline(x, y, text, font_size, color, anchor, baseline):
        # Stroke first
        dwg.add(dwg.text(
            text,
            insert=(x, y),
            font_size=font_size,
            font_family=font_family,
            fill="none",
            stroke="#FFF",
            stroke_width=STROKE_WIDTH,
            text_anchor=anchor,
            alignment_baseline=baseline,
            opacity=0.9
        ))
        # Fill on top
        dwg.add(dwg.text(
            text,
            insert=(x, y),
            font_size=font_size,
            font_family=font_family,
            fill=color,
            stroke="none",
            text_anchor=anchor,
            alignment_baseline=baseline,
            opacity=0.9
        ))

    # --- Top-left ---
    add_text_with_outline(PADDING, PADDING, first_digit, BIG_FONT, COLORS[0], "start", "hanging")
    offset_x = PADDING + BIG_FONT * 0.6
    add_text_with_outline(offset_x, PADDING, rest_digits, SMALL_FONT, COLORS[0], "start", "hanging")

    # --- Top-right ---
    add_text_with_outline(W - PADDING, PADDING, rest_digits, SMALL_FONT, COLORS[1], "end", "hanging")
    offset_x = W - PADDING - SMALL_FONT * len(rest_digits) * 0.55
    add_text_with_outline(offset_x, PADDING, first_digit, BIG_FONT, COLORS[1], "end", "hanging")

    # --- Bottom-left ---
    add_text_with_outline(PADDING, H - PADDING, first_digit, BIG_FONT, COLORS[2], "start", "baseline")
    offset_x = PADDING + BIG_FONT * 0.6
    add_text_with_outline(offset_x, H - PADDING, rest_digits, SMALL_FONT, COLORS[2], "start", "baseline")

    # --- Bottom-right ---
    add_text_with_outline(W - PADDING, H - PADDING, rest_digits, SMALL_FONT, COLORS[3], "end", "baseline")
    offset_x = W - PADDING - SMALL_FONT * len(rest_digits) * 0.55
    add_text_with_outline(offset_x, H - PADDING, first_digit, BIG_FONT, COLORS[3], "end", "baseline")





import svgwrite
import math

def tesselated_triangles(dwg, x, y, size, rows=8, cols=8, stroke_color="#000000"):
    """Draw a tessellation of equilateral triangles starting from (x,y)."""
    tri_h = (math.sqrt(3) / 2) * size  # height of an equilateral triangle

    for row in range(rows):
        for col in range(cols):
            # Alternate upright vs inverted triangles
            if (row + col) % 2 == 0:
                points = [
                    (x + col*size/2, y + row*tri_h),
                    (x + col*size/2 + size/2, y + row*tri_h + tri_h),
                    (x + col*size/2 - size/2, y + row*tri_h + tri_h),
                ]
            else:
                points = [
                    (x + col*size/2, y + row*tri_h + tri_h),
                    (x + col*size/2 + size/2, y + row*tri_h),
                    (x + col*size/2 - size/2, y + row*tri_h),
                ]
            dwg.add(dwg.polygon(points=points,
                                fill="none",
                                stroke=stroke_color,
                                stroke_width=1))


def add_functional_corner_decorations(dwg, W, H, denom, timestamp, serial_id,
                                      size=100, padding=75, stroke_width=1):
    # Main + highlight colors per corner
    COLORS = [
        ("#D80027", "#FF5555", "#FF69B4"),  # top-left (red + pink)
        ("#009E60", "#55FFAA", "#FFD700"),  # top-right (green + yellow)
        ("#0052B4", "#55AAFF", "#FF69B4"),  # bottom-left (blue + pink)
        ("#222222", "#AAAAAA", "#FFD700"),  # bottom-right (black/gray + yellow)
    ]

    def micro_text_pattern(x, y, text, rows=12, cols=12, spacing=10,
                           c_main="#000", c_highlight="#FF69B4"):
        """Repeating microtext grid with alternating highlight color."""
        for row in range(rows):
            for col in range(cols):
                color = c_main if (row+col) % 3 else c_highlight
                dwg.add(dwg.text(text,
                                 insert=(x + col*spacing, y + row*spacing),
                                 font_size=6, font_family="Daemon Full Working",
                                 fill=color, opacity=0.25))

    def tesselated_triangles(dwg, x, y, s, rows=8, cols=8,
                             c_main="#000", c_highlight="#FFD700"):
        """Draw tessellated upright + inverted triangles with mixed colors."""
        h = s * (3 ** 0.5) / 2
        for row in range(rows):
            for col in range(cols):
                x0 = x + col * s
                y0 = y + row * h
                if (row + col) % 2 == 0:
                    pts = [(x0, y0 + h), (x0 + s/2, y0), (x0 + s, y0 + h)]
                else:
                    pts = [(x0, y0), (x0 + s, y0), (x0 + s/2, y0 + h)]
                stroke_color = c_main if (row+col) % 4 else c_highlight
                dwg.add(dwg.polygon(points=pts, fill="none",
                                    stroke=stroke_color,
                                    stroke_width=0.6, opacity=0.7))

    def top_left(x, y, denom):
        main, secondary, highlight = COLORS[0]
        for i in range(3):
            offset = i*size*0.18
            stroke_c = main if i % 2 == 0 else highlight
            dwg.add(dwg.rect(insert=(x+offset, y+offset),
                             size=(size-2*offset, size-2*offset),
                             rx=8, ry=8, fill="none",
                             stroke=stroke_c, stroke_width=stroke_width))
        dwg.add(dwg.text(denom, insert=(x+size/2, y+size/2),
                         font_size=22, text_anchor="middle",
                         alignment_baseline="middle",
                         font_family="Daemon Full Working", fill=secondary))
        micro_text_pattern(x+12, y+12, denom, c_main=secondary, c_highlight=highlight)

    def top_right(x, y, denom):
        main, secondary, highlight = COLORS[1]
        tesselated_triangles(dwg, x - size, y, size/6, rows=12, cols=12,
                             c_main=main, c_highlight=highlight)
        dwg.add(dwg.text(denom, insert=(x - size/2, y + size/2),
                         font_size=20, text_anchor="middle",
                         alignment_baseline="middle",
                         font_family="Daemon Full Working", fill=random.choice([secondary, highlight])))

    def bottom_left(x, y, denom):
        main, secondary, highlight = COLORS[2]
        tesselated_triangles(dwg, x, y - size, size/6, rows=12, cols=12,
                             c_main=main, c_highlight=highlight)
        dwg.add(dwg.text(denom, insert=(x + size/2, y - size/2),
                         font_size=20, text_anchor="middle",
                         alignment_baseline="middle",
                         font_family="Daemon Full Working", fill=random.choice([secondary, highlight])))

    def bottom_right(x, y, denom, timestamp):
        main, secondary, highlight = COLORS[3]
        for i in range(4):
            offset = i*size*0.18
            stroke_c = main if i % 2 else highlight
            dwg.add(dwg.rect(insert=(x - size + offset, y - size + offset),
                             size=(size - 2*offset, size - 2*offset),
                             rx=10, ry=10, fill="none",
                             stroke=stroke_c, stroke_width=stroke_width))
        dwg.add(dwg.text(denom, insert=(x - size/2, y - size/2),
                         font_size=22, text_anchor="middle",
                         alignment_baseline="middle",
                         font_family="Daemon Full Working", fill=random.choice([secondary, highlight])))
        micro_text_pattern(x - size + 5, y - size + 5, f"{denom} {timestamp}",
                           c_main=secondary, c_highlight=highlight)

    # Apply all four corners
    top_left(padding, padding, denom)
    top_right(W - padding, padding, denom)
    bottom_left(padding, H - padding, denom)
    bottom_right(W - padding, H - padding, denom, timestamp)

# Add border
# ----------------------
import math
def add_decorative_border(dwg, W:int, H:int, border_info:dict, denom_value: int, timestamp_ms:int):
    """
    Adds multi-band border around diamond area.
    Each band encodes parts of the timestamp (year, month, etc.)
    and the pattern is influenced by denom_value.
    
    Shapes used:
        0 → filled diamond
        1 → empty diamond
        2 → filled square
        3 → empty square
        4 → X / stitch
    """

    import datetime
    if isinstance(timestamp_ms, dict):
        timestamp_ms = timestamp_ms.get("timestamp_ms", 0)

    # Convert timestamp_ms to datetime
    ts = datetime.datetime.fromtimestamp(float(timestamp_ms) / 1000.0)
    bands = [
        ("year", ts.year % 100, 0.25 + 0.025),           # ¼ cm (largest)
        ("month", ts.month, 0.1875 + 0.025),             # 3/16 cm
        ("day", ts.day, 0.125 + 0.025),                  # ⅛ cm
        ("hour", ts.hour, 0.1875 + 0.025),               # 3/16 cm (repeats at hour level)
        ("minute", ts.minute, 0.09375 + 0.025),          # 3/32 cm (half of hour)
        ("second", ts.second, 0.046875 + 0.025),         # 3/64 cm (half of minute)
        ("microsecond", ts.microsecond // 1000, 0.0234375 + 0.025)  # 3/128 cm (half of second)
    ]

    # Get diamond area from border_info
    start_x = float(border_info.get("diamond_start_x", 0))
    start_y = float(border_info.get("diamond_start_y", 0))
    width   = float(border_info.get("diamond_width", W))
    height  = float(border_info.get("diamond_height", H))

    # Convert cm to pixels (assuming 96 dpi)
    cm_to_px = lambda cm: float(cm * 96.0 / 2.54)

    pad_base = cm_to_px(0.25)  # ¼ cm padding
    inset = -0.75
    denom_value = denom_value or 0  # default if None
    # Add opacity to both fill and stroke
    fill_opacity = 1
    stroke_opacity = 1
    # --- shape drawing helpers
    def draw_shape(g, x, y, size, kind, band_index):
        half = size / 2.0
    
        # Alternate by band - even bands: dark fill/light stroke, odd bands: light fill/dark stroke
        fill_black = band_index % 2 == 0
        
        if fill_black:
            fill_color = "#000"  # Dark gray
            stroke_color = "#FFFFFF"  # Light gray
            stroke_opacity = 1/(band_index+0.01)
            fill_opacity = 1
        else:
            fill_color = "#FFF"  # Light gray
            stroke_color = "#000000"  # Dark gray
            fill_opacity = band_index/1
            stroke_opacity = 1
        
        # 50% transparency
        stroke_width = max(0.5, size * 0.025)
        
        if kind == 0:  # filled diamond
            pts = [(x+half, y), (x+size, y+half), (x+half, y+size), (x, y+half)]
            g.add(dwg.polygon(points=pts, fill=fill_color, fill_opacity=fill_opacity, 
                            stroke=stroke_color, stroke_opacity=stroke_opacity, stroke_width=stroke_width))
        elif kind == 1:  # empty diamond
            pts = [(x+half, y), (x+size, y+half), (x+half, y+size), (x, y+half)]
            g.add(dwg.polygon(points=pts, fill="none", 
                            stroke=stroke_color, stroke_opacity=stroke_opacity, stroke_width=stroke_width))
        elif kind == 2:  # filled square
            g.add(dwg.rect(insert=(x, y), size=(size, size), 
                        fill=fill_color, fill_opacity=fill_opacity,
                        stroke=stroke_color, stroke_opacity=stroke_opacity, stroke_width=stroke_width))
        elif kind == 3:  # empty square
            g.add(dwg.rect(insert=(x, y), size=(size, size), fill="none",
                        stroke=stroke_color, stroke_opacity=stroke_opacity, stroke_width=stroke_width))
        elif kind == 4:  # X / stitch
            g.add(dwg.line(start=(x, y), end=(x+size, y+size), 
                        stroke=stroke_color, stroke_opacity=stroke_opacity, stroke_width=stroke_width))
            g.add(dwg.line(start=(x+size, y), end=(x, y+size), 
                        stroke=stroke_color, stroke_opacity=stroke_opacity, stroke_width=stroke_width))

    for band_index, (band_name, value, band_cm) in enumerate(bands):
        band_size = cm_to_px(band_cm)
        g = dwg.g()

        # number of tiles along edges
        num_cols = int((width - 2*pad_base - 2*inset) // band_size)
        num_rows = int((height - 2*pad_base - 2*inset) // band_size)

        offset = value + (denom_value % 97)

        # --- top border
        y = start_y + pad_base + inset
        for c in range(num_cols):
            x = start_x + pad_base + inset + c * band_size
            kind = (c + offset) % 5
            draw_shape(g, x, y, band_size, kind, band_index)  # Added band_index

        # --- bottom border
        y = start_y + height - pad_base - inset - band_size
        for c in range(num_cols):
            x = start_x + pad_base + inset + c * band_size
            kind = (c + offset + 1) % 5
            draw_shape(g, x, y, band_size, kind, band_index)  # Added band_index

        # --- left border
        x = start_x + pad_base + inset
        for r in range(num_rows):
            y = start_y + pad_base + inset + r * band_size
            kind = (r + offset + 2) % 5
            draw_shape(g, x, y, band_size, kind, band_index)  # Added band_index

        # --- right border
        x = start_x + width - pad_base - inset - band_size
        for r in range(num_rows):
            y = start_y + pad_base + inset + r * band_size
            kind = (r + offset + 3) % 5
            draw_shape(g, x, y, band_size, kind, band_index)  # Added band_index

        dwg.add(g)
        inset += band_size


def generate_single_banknote(
    seed_text,
    input_image_path,
    single_denom,
    outfile=None,
    specimen=False,
    serial_id=None,
    timestamp=None,
    width_mm=160.0,
    height_mm=60.0,
    title="灵国国库",
    subtitle="天圆地方",
    font_dir="./fonts",
    bg_dir="./backgrounds",
    dpi=300.0,
    background_prompt="",
    progress_callback=None
):
    if progress_callback:
        progress_callback("start:front")
    print(f"[DEBUG] Starting front SVG generation: {outfile}")
       
    # Update global DPI
    global MM_TO_PX
    MM_TO_PX = dpi / 25.4

    # Set default outfile if not provided
    if outfile is None:
        timestamp_str = timestamp or datetime.now().strftime("%Y%m%d-%H%M%S")
        outfile = f"./images/{seed_text}/{single_denom}/{seed_text}_-_{single_denom}_-_{timestamp_str}_FRONT.svg"

    # Create output directory
    outfile_dir = os.path.dirname(outfile)
    os.makedirs(outfile_dir, exist_ok=True)

    # Load fonts
    fonts_obj = load_fonts(font_dir)

    # Generate the single banknote
    denomination_str = f"{single_denom} 卢纳币"

    generate_fantasy_banknote(
        seed_text=seed_text,
        input_image_path=input_image_path,
        outfile_svg=outfile,
        width_mm=width_mm,
        height_mm=height_mm,
        title=title,
        subtitle=subtitle,
        specimen=specimen,
        denomination=denomination_str,
        fonts=fonts_obj,
        serial_id=serial_id,
        timestamp=timestamp,
        bg_dir=bg_dir,
        background_prompt=background_prompt,
        progress_callback=progress_callback
    )
    if progress_callback:
        progress_callback("completed:front")
    print(f"[DEBUG] Front SVG saved: {outfile}")

    print(f"[+] Single bill generated: {outfile}")
    return outfile

    def generate_multiple_banknotes(seed_text, input_image_path, copies=1, yen_model=False, 
                                specimen=False, serial_id=None, timestamp=None,
                                width_mm=160.0, height_mm=60.0, title="灵国国库", subtitle="天圆地方",
                                font_dir="./fonts", bg_dir="./backgrounds", dpi=300.0, background_prompt=""):
        """
        Generate multiple banknotes with different denominations.
        
        Args:
            seed_text: Seed text or name for the note
            input_image_path: Input image path
            copies: Number of distinct notes to generate
            yen_model: Use 1-100,000,000 denominations
            specimen: Add SPECIMEN overlay
            serial_id: Serial ID
            timestamp: Timestamp String
            width_mm: Width in mm
            height_mm: Height in mm
            title: Title text
            subtitle: Subtitle text
            font_dir: Directory containing font files
            bg_dir: Directory containing background images
            dpi: Resolution in DPI
        
        Returns:
            List of paths to generated SVG files
        """
        # Update global DPI
        global MM_TO_PX
        MM_TO_PX = dpi / 25.4
        
        # Generate denominations
        if yen_model:
            base_denoms = [1, 10, 100, 1000, 10000, 100000, 1000000, 10000000, 100000000]
            denominations = base_denoms[:9]  # top 9 denominations
        else:
            denominations = [100 * (i + 1) for i in range(9)]  # default 9 denominations

        fonts_obj = load_fonts(font_dir)
        generated_files = []

        for i in tqdm(range(copies), desc="Generating banknotes"):
            new_seed = seed_text  # no _i prefix in filenames

            for denom in denominations:
                timestamp_str = timestamp or datetime.now().strftime("%Y%m%d%H%M%S")
                # Filename format: seed_denomination_datetime.svg
                outfile_svg = f"./images/{new_seed}/{denom}/{new_seed}_-_{denom}_-_{timestamp_str}_FRONT.svg"
                outfile_dir = os.path.dirname(outfile_svg)
                os.makedirs(outfile_dir, exist_ok=True)

                denomination_str = f"{denom} 卢纳币"

                generate_fantasy_banknote(
                    seed_text=f"{new_seed}_{i}",  # keep unique seed for generation
                    input_image_path=input_image_path,
                    outfile_svg=outfile_svg,
                    width_mm=width_mm,
                    height_mm=height_mm,
                    title=title,
                    subtitle=subtitle,
                    specimen=specimen,
                    denomination=denomination_str,
                    fonts=fonts_obj,
                    serial_id=serial_id,
                    timestamp=timestamp_str,
                    bg_dir=bg_dir,
                    background_prompt=background_prompt
                )
                
                generated_files.append(outfile_svg)

        return generated_files

    def single_bill_run():
        """
        Command-line wrapper function for single bill generation.
        """
        parser = argparse.ArgumentParser(description="Generate a single fantasy banknote with specific denomination")
        parser.add_argument("seed_text", type=str, help="Seed text or name for the note")
        parser.add_argument("input_image", type=str, help="Input image path")
        parser.add_argument("--single_denom", type=int, required=True, help="Specific denomination to generate (e.g., 100)")
        parser.add_argument("--outfile", type=str, default=None, help="Output SVG file (default: auto-generated)")
        parser.add_argument("--specimen", action="store_true", help="Add SPECIMEN overlay")
        parser.add_argument("--serial_id", type=str, help="Serial ID")
        parser.add_argument("--timestamp", type=str, help="Timestamp String")
        parser.add_argument("--width-mm", type=float, default=160.0, help="Width in mm (default: 160.0)")
        parser.add_argument("--height-mm", type=float, default=60.0, help="Height in mm (default: 60.0)")
        parser.add_argument("--title", type=str, default="灵国国库", help="Title text (default: 灵国国库)")
        parser.add_argument("--subtitle", type=str, default="天圆地方", help="Subtitle text (default: 天圆地方)")
        parser.add_argument("--font-dir", type=str, default="./fonts", help="Directory containing font files (default: ./fonts)")
        parser.add_argument("--bg-dir", type=str, default="./backgrounds", help="Directory containing background images (default: ./backgrounds)")
        parser.add_argument("--dpi", type=float, default=300.0, help="Resolution in DPI (default: 300.0)")
        parser.add_argument("--background-prompt", type=str, help="Background generation prompt")
        
        args = parser.parse_args()
        
        generate_single_banknote(
            seed_text=args.seed_text,
            input_image_path=args.input_image,
            single_denom=args.single_denom,
            outfile=args.outfile,
            specimen=args.specimen,
            serial_id=args.serial_id,
            timestamp=args.timestamp,
            width_mm=args.width_mm,
            height_mm=args.height_mm,
            title=args.title,
            subtitle=args.subtitle,
            font_dir=args.font_dir,
            bg_dir=args.bg_dir,
            dpi=args.dpi,
            background_prompt=args.background_prompt
        )

    def multi_bill_run():
        """
        Command-line wrapper function for multiple bill generation.
        """
        parser = argparse.ArgumentParser(description="Fantasy banknote generator")
        parser.add_argument("seed_text", type=str, help="Seed text or name for the note")
        parser.add_argument("input_image", type=str, help="Input image path")
        parser.add_argument("--outfile", type=str, default="banknote.svg", help="Base output SVG file")
        parser.add_argument("--specimen", action="store_true", help="Add SPECIMEN overlay")
        parser.add_argument("--copies", type=int, default=1, help="Number of distinct notes to generate")
        parser.add_argument("--yen_model", action="store_true", help="Use 1-100,000,000 denominations")
        parser.add_argument("--serial_id", type=str, help="Serial ID")
        parser.add_argument("--timestamp", type=str, help="Timestamp String")
        parser.add_argument("--width-mm", type=float, default=160.0, help="Width in mm (default: 160.0)")
        parser.add_argument("--height-mm", type=float, default=60.0, help="Height in mm (default: 60.0)")
        parser.add_argument("--title", type=str, default="灵国国库", help="Title text (default: 灵国国库)")
        parser.add_argument("--subtitle", type=str, default="天圆地方", help="Subtitle text (default: 天圆地方)")
        parser.add_argument("--font-dir", type=str, default="./fonts", help="Directory containing font files (default: ./fonts)")
        parser.add_argument("--bg-dir", type=str, default="./backgrounds", help="Directory containing background images (default: ./backgrounds)")
        parser.add_argument("--dpi", type=float, default=300.0, help="Resolution in DPI (default: 300.0)")
        parser.add_argument("--background-prompt", type=str, help="Background generation prompt")
        
        args = parser.parse_args()

        generate_multiple_banknotes(
            seed_text=args.seed_text,
            input_image_path=args.input_image,
            copies=args.copies,
            yen_model=args.yen_model,
            specimen=args.specimen,
            serial_id=args.serial_id,
            timestamp=args.timestamp,
            width_mm=args.width_mm,
            height_mm=args.height_mm,
            title=args.title,
            subtitle=args.subtitle,
            font_dir=args.font_dir,
            bg_dir=args.bg_dir,
            dpi=args.dpi,
            background_prompt=args.background_prompt
        )

    # Main execution
    if __name__ == "__main__":
        import sys
        
        # Check if --single_denom flag is present to use the single bill mode
        if "--single_denom" in sys.argv:
            single_bill_run()
        else:
            multi_bill_run()
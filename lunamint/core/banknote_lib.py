"""
banknote_lib.py - Standalone banknote SVG/PNG generation helpers.

This module intentionally avoids Flask/DB dependencies and can be used as a
lightweight library for generating banknote assets.
"""
from __future__ import annotations

import os
import subprocess
import datetime
import secrets
import hashlib
from pathlib import Path
from io import BytesIO
from typing import Optional, Dict

import cairosvg
from PIL import Image

# Try to import generator functions directly (faster); fallback to subprocess.
try:
    from ..graphics.generate_banknote_front import (
        generate_single_banknote as _generate_front,
    )
except Exception:
    _generate_front = None

try:
    from ..graphics.generate_banknote_back import (
        run_single_denomination as _generate_back,
    )
except Exception:
    _generate_back = None

BASE_DIR = Path(__file__).resolve().parent
FRONT_SCRIPT = str((BASE_DIR / ".." / "graphics" / "generate_banknote_front.py").resolve())
BACK_SCRIPT = str((BASE_DIR / ".." / "graphics" / "generate_banknote_back.py").resolve())


def generate_timestamp_ms_precise() -> int:
    """Generate timestamp with microsecond precision (ms)."""
    now = datetime.datetime.now()
    return int(now.timestamp() * 1000) + now.microsecond // 1000


def generate_serial_id_with_checksum(timestamp_ms: Optional[int] = None) -> str:
    """Generate serial ID with checksum (front)."""
    ts = timestamp_ms or generate_timestamp_ms_precise()
    salt = secrets.token_bytes(3)
    raw = f"{ts}-".encode() + salt
    h = hashlib.sha3_256(raw).digest()

    serial_bytes = h[:10]
    serial_b64 = (
        __import__("base64").urlsafe_b64encode(serial_bytes)
        .decode("ascii")
        .replace("=", "")[:14]
    )

    checksum_bytes = h[-2:]
    checksum_b64 = (
        __import__("base64").urlsafe_b64encode(checksum_bytes)
        .decode("ascii")
        .replace("=", "")[:3]
    )

    return f"SN-{serial_b64}-{checksum_b64}"


def generate_serial_id_combined(timestamp_ms: Optional[int] = None) -> str:
    """Generate compact serial ID (back)."""
    ts = timestamp_ms or generate_timestamp_ms_precise()
    salt = secrets.token_bytes(4)
    raw = f"{ts}-".encode() + salt
    h = hashlib.sha3_256(raw).digest()

    serial_b64 = __import__("base64").urlsafe_b64encode(h[:12]).decode("ascii")
    serial_clean = serial_b64.replace("=", "")[:12]
    return f"SN-{serial_clean[:4]}-{serial_clean[4:8]}-{serial_clean[8:12]}"


def create_proper_filename(name: str, denom: str, timestamp_ms: int, side: str) -> str:
    """Create filename: {name}_-_{denom}_-_{timestamp}_{side}.svg"""
    return f"{name}_-_{denom}_-_{timestamp_ms}_{side}.svg"


def create_basename(name: str, denom: str, timestamp_ms: int, side: str) -> str:
    """Create basename: {name}_-_{denom}_-_{timestamp}_{side}"""
    return f"{name}_-_{denom}_-_{timestamp_ms}_{side}"


def generate_png_from_svg(svg_path: str, png_path: str, size=(1600, 600)) -> bool:
    """Generate PNG from SVG file using cairosvg (with simple cache)."""
    if os.path.exists(png_path) and os.path.exists(svg_path):
        if os.path.getmtime(png_path) >= os.path.getmtime(svg_path):
            return True

    png_bytes = cairosvg.svg2png(
        url=svg_path,
        output_width=size[0],
        output_height=size[1],
    )
    img = Image.open(BytesIO(png_bytes))
    img.save(png_path, format="PNG", optimize=False, compress_level=1)
    return True


def generate_banknote_pair_svgs_pngs(
    name: str,
    denom: int,
    portrait_path: str,
    output_dir: str,
    timestamp_ms: Optional[int] = None,
    front_serial: Optional[str] = None,
    back_serial: Optional[str] = None,
    width_mm: float = 160.0,
    height_mm: float = 60.0,
    title: str = "灵国国库",
    subtitle: str = "天圆地方",
    font_dir: str = "./fonts",
    bg_dir: str = "./backgrounds",
    dpi: float = 300.0,
    bg_image: Optional[str] = None,
    background_prompt: Optional[str] = None,
    use_parallel: bool = True,
    multi_gpu_enabled: Optional[bool] = None,
) -> Dict[str, str]:
    """Generate front+back SVG and PNG files for a denomination.

    Returns a dict with paths and serials. Does not touch DB/Flask.
    """
    if portrait_path and not os.path.exists(portrait_path):
        raise FileNotFoundError("portrait_path must exist when provided")

    os.makedirs(output_dir, exist_ok=True)
    ts = timestamp_ms or generate_timestamp_ms_precise()
    front_serial = front_serial or generate_serial_id_with_checksum(ts)
    back_serial = back_serial or generate_serial_id_combined(ts)

    denom_str = str(int(denom))
    front_filename = create_proper_filename(name, denom_str, ts, "FRONT")
    back_basename = create_basename(name, denom_str, ts, "BACK")

    front_svg_path = os.path.join(output_dir, front_filename)
    back_svg_path = os.path.join(output_dir, f"{back_basename}.svg")

    if multi_gpu_enabled is None:
        multi_gpu_enabled = os.getenv("MULTI_GPU_ENABLED", "false").lower() == "true"

    def _run_front():
        if os.path.exists(front_svg_path) and os.path.getsize(front_svg_path) > 0:
            return True
        gpu_env = os.environ.copy()
        if multi_gpu_enabled:
            gpu_env["CUDA_VISIBLE_DEVICES"] = "0"
        if not _generate_front:
            raise RuntimeError("Front generator is unavailable; please install required dependencies.")
        _generate_front(
            seed_text=name,
            input_image_path=portrait_path,
            single_denom=denom_str,
            outfile=front_svg_path,
            serial_id=front_serial,
            timestamp=int(ts),
            background_prompt=background_prompt,
        )
        return True

    def _run_back():
        if os.path.exists(back_svg_path) and os.path.getsize(back_svg_path) > 0:
            return True
        gpu_env = os.environ.copy()
        if multi_gpu_enabled:
            gpu_env["CUDA_VISIBLE_DEVICES"] = "1"
        if not _generate_back:
            raise RuntimeError("Back generator is unavailable; please install required dependencies.")
        _generate_back(
            outdir=output_dir,
            base_name=back_basename,
            denomination=denom_str,
            seed_text=name,
            serial_id=back_serial,
            timestamp=int(ts),
        )
        return True

    if use_parallel:
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            front_future = executor.submit(_run_front)
            back_future = executor.submit(_run_back)
            if not (front_future.result() and back_future.result()):
                raise RuntimeError("Failed to generate front/back SVG")
    else:
        if not _run_front():
            raise RuntimeError("Failed to generate front SVG")
        if not _run_back():
            raise RuntimeError("Failed to generate back SVG")

    front_png_path = front_svg_path.replace(".svg", ".png")
    back_png_path = back_svg_path.replace(".svg", ".png")
    generate_png_from_svg(front_svg_path, front_png_path)
    generate_png_from_svg(back_svg_path, back_png_path)

    return {
        "front_svg": front_svg_path,
        "front_png": front_png_path,
        "back_svg": back_svg_path,
        "back_png": back_png_path,
        "front_serial": front_serial,
        "back_serial": back_serial,
        "timestamp_ms": ts,
    }

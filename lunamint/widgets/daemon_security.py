"""Daemon security letter pattern widget."""
from __future__ import annotations

import hashlib
import colorsys
from pathlib import Path
from typing import Iterable, Optional

import svgwrite

from .measure import mm_to_px


def _find_font_path(font_name: str, font_dir: str) -> str:
    if font_name and Path(font_name).is_file():
        return font_name
    for ext in (".ttf", ".otf"):
        candidate = Path(font_dir) / f"{font_name}{ext}"
        if candidate.exists():
            return str(candidate)
    for file in Path(font_dir).glob("*.ttf"):
        if font_name.lower().replace(" ", "") in file.stem.lower().replace(" ", ""):
            return str(file)
    for file in Path(font_dir).glob("*.otf"):
        if font_name.lower().replace(" ", "") in file.stem.lower().replace(" ", ""):
            return str(file)
    raise FileNotFoundError(f"Font '{font_name}' not found in {font_dir}")


def _resolve_glyph_name(cmap: dict[int, str], glyph_set, ch: str) -> Optional[str]:
    glyph_name = cmap.get(ord(ch))
    if not glyph_name or glyph_name in {".notdef", "NULL"}:
        if ch.islower():
            glyph_name = cmap.get(ord(ch.upper()))
        elif ch.isupper():
            glyph_name = cmap.get(ord(ch.lower()))
    if not glyph_name or glyph_name in {".notdef", "NULL"}:
        return None
    if glyph_name not in glyph_set:
        return None
    return glyph_name


def _iter_chars(text: str) -> Iterable[str]:
    cleaned = "".join(ch for ch in text if not ch.isspace())
    if not cleaned:
        cleaned = "LUNAMINT"
    while True:
        for ch in cleaned:
            yield ch


_CRYPTO_SEED_CACHE: dict[tuple[str, str, str | None, str | None, str | None], bytes] = {}


def _normalize_crypto_bytes(result: object) -> bytes:
    if isinstance(result, bytes):
        return result
    if isinstance(result, str):
        try:
            return bytes.fromhex(result)
        except ValueError:
            return result.encode("utf-8")
    if isinstance(result, list):
        return bytes(result)
    raise TypeError("Unsupported crypto return type")


def _seed_digest(
    seed: str,
    algo: str,
    sm2_private_key: str | None,
    sm2_public_key: str | None,
    sm4_key: str | None,
) -> bytes:
    name = (algo or "sha256").lower()
    cache_key = (name, seed, sm2_private_key, sm2_public_key, sm4_key)
    cached = _CRYPTO_SEED_CACHE.get(cache_key)
    if cached is not None:
        return cached

    payload = seed.encode("utf-8")

    if name == "sha3_256":
        digest = hashlib.sha3_256(payload).digest()
    elif name == "sha256":
        digest = hashlib.sha256(payload).digest()
    elif name == "sm3":
        try:
            from lunalib.core import sm3  # type: ignore

            if hasattr(sm3, "hash"):
                digest = _normalize_crypto_bytes(sm3.hash(payload))
            elif hasattr(sm3, "sm3_hash"):
                digest = _normalize_crypto_bytes(sm3.sm3_hash(payload))
            elif hasattr(sm3, "hash_bytes"):
                digest = _normalize_crypto_bytes(sm3.hash_bytes(payload))
            else:
                digest = hashlib.sha256(payload).digest()
        except Exception:
            digest = hashlib.sha256(payload).digest()
    elif name == "sm2":
        if not sm2_private_key:
            digest = hashlib.sha256(payload).digest()
        else:
            try:
                from .crypto import sm2_sign_bytes

                digest = sm2_sign_bytes(payload, sm2_private_key, sm2_public_key)
            except Exception:
                try:
                    from lunalib.core import sm2  # type: ignore

                    if hasattr(sm2, "sign"):
                        digest = _normalize_crypto_bytes(sm2.sign(payload, sm2_private_key))
                    elif hasattr(sm2, "sm2_sign"):
                        digest = _normalize_crypto_bytes(sm2.sm2_sign(payload, sm2_private_key))
                    else:
                        digest = hashlib.sha256(payload).digest()
                except Exception:
                    digest = hashlib.sha256(payload).digest()
    elif name == "sm4":
        if not sm4_key:
            digest = hashlib.sha256(payload).digest()
        else:
            try:
                from lunalib.core import sm4  # type: ignore

                if hasattr(sm4, "encrypt"):
                    digest = _normalize_crypto_bytes(sm4.encrypt(payload, sm4_key))
                elif hasattr(sm4, "sm4_encrypt"):
                    digest = _normalize_crypto_bytes(sm4.sm4_encrypt(payload, sm4_key))
                else:
                    digest = hashlib.sha256(payload).digest()
            except Exception:
                digest = hashlib.sha256(payload).digest()
    else:
        digest = hashlib.sha256(payload).digest()

    _CRYPTO_SEED_CACHE[cache_key] = digest
    return digest


def _color_for_char(
    ch: str,
    idx: int,
    seed: str,
    hash_algo: str,
    sm2_private_key: str | None,
    sm2_public_key: str | None,
    sm4_key: str | None,
) -> str:
    algo = (hash_algo or "sha256").lower()
    if algo in {"sm2", "sm3", "sm4"}:
        base = _seed_digest(seed, algo, sm2_private_key, sm2_public_key, sm4_key)
        payload = f"{ch}|{idx}".encode("utf-8")
        digest = hashlib.sha256(base + payload).digest()
    else:
        payload = f"{seed}|{ch}|{idx}".encode("utf-8")
        if algo == "sha3_256":
            digest = hashlib.sha3_256(payload).digest()
        else:
            digest = hashlib.sha256(payload).digest()
    hue = digest[0] / 255.0
    sat = 0.65 + (digest[1] / 255.0) * 0.3
    val = 0.75 + (digest[2] / 255.0) * 0.25
    r, g, b = colorsys.hsv_to_rgb(hue, sat, val)
    return f"#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}"


def add_daemon_security_pattern_px(
    dwg: svgwrite.Drawing,
    x_px: float,
    y_px: float,
    width_px: float,
    height_px: float,
    text: str = "LUNAMINT",
    font_name: str = "Daemon Full Working",
    font_dir: str = "./fonts",
    font_size_px: float = 12.0,
    spacing_px: float = 6.0,
    row_spacing_px: float | None = None,
    angle_deg: float = 0.0,
    opacity: float = 0.35,
    color_seed: str = "",
    stagger: bool = True,
    density: float = 1.0,
    letter_scale: float = 1.0,
    hash_algo: str = "sha256",
    sm2_private_key: str | None = None,
    sm2_public_key: str | None = None,
    sm4_key: str | None = None,
    render_as_shapes: bool = False,
) -> svgwrite.container.Group:
    width_px = max(1.0, width_px)
    height_px = max(1.0, height_px)
    letter_scale = max(0.1, letter_scale)
    font_size_px = max(1.0, font_size_px * letter_scale)
    spacing_px = max(0.0, spacing_px)
    row_spacing_px = max(0.0, row_spacing_px) if row_spacing_px is not None else spacing_px
    density = max(0.1, density)

    step_x = max(1.0, (font_size_px + spacing_px) / density)
    step_y = max(1.0, (font_size_px + row_spacing_px) / density)

    cols = max(1, int(width_px / step_x) + 2)
    rows = max(1, int(height_px / step_y) + 2)

    group = dwg.g(opacity=opacity)
    center_x = x_px + width_px * 0.5
    center_y = y_px + height_px * 0.5
    if angle_deg:
        group.rotate(angle_deg, center=(center_x, center_y))

    char_iter = _iter_chars(text)
    idx = 0

    glyph_cache: dict[str, tuple[str, float, float]] = {}
    if render_as_shapes:
        try:
            from fontTools.pens.boundsPen import BoundsPen
            from fontTools.pens.svgPathPen import SVGPathPen
            from fontTools.ttLib import TTFont
        except Exception as exc:
            raise RuntimeError("fontTools is required for render_as_shapes in daemon_security.") from exc

        font_path = _find_font_path(font_name, font_dir)
        font = TTFont(font_path)
        glyph_set = font.getGlyphSet()
        cmap = font.getBestCmap()
        units_per_em = font["head"].unitsPerEm
        base_scale = font_size_px / units_per_em
        glyph_hash = hashlib.md5(font_path.encode("utf-8")).hexdigest()[:8]

        def _get_glyph(ch: str) -> Optional[tuple[str, float, float]]:
            cached = glyph_cache.get(ch)
            if cached is not None:
                return cached
            glyph_name = _resolve_glyph_name(cmap, glyph_set, ch)
            if not glyph_name:
                return None
            glyph = glyph_set[glyph_name]
            pen = SVGPathPen(glyph_set)
            glyph.draw(pen)
            path = pen.getCommands()
            if not path:
                return None
            bounds_pen = BoundsPen(glyph_set)
            glyph.draw(bounds_pen)
            bounds = bounds_pen.bounds
            if not bounds:
                return None
            min_x, min_y, max_x, max_y = bounds
            glyph_cx = (min_x + max_x) / 2
            glyph_cy = (min_y + max_y) / 2
            glyph_id = f"daemon_glyph_{glyph_hash}_{ord(ch)}"
            dwg.defs.add(dwg.path(id=glyph_id, d=path))
            cached = (glyph_id, glyph_cx, glyph_cy)
            glyph_cache[ch] = cached
            return cached
    for row in range(rows):
        offset_x = step_x * 0.5 if (stagger and row % 2 == 1) else 0.0
        y = y_px + row * step_y + font_size_px * 0.5
        if y > y_px + height_px + step_y:
            break
        for col in range(cols):
            x = x_px + col * step_x + offset_x + font_size_px * 0.5
            if x > x_px + width_px + step_x:
                break
            ch = next(char_iter)
            fill = _color_for_char(
                ch,
                idx,
                color_seed or text,
                hash_algo,
                sm2_private_key,
                sm2_public_key,
                sm4_key,
            )
            idx += 1
            if render_as_shapes:
                glyph_info = _get_glyph(ch)
                if glyph_info is None:
                    continue
                glyph_id, glyph_cx, glyph_cy = glyph_info
                transform = (
                    f"translate({x:.2f},{y:.2f}) "
                    f"scale({base_scale:.4f},{-base_scale:.4f}) "
                    f"translate({-glyph_cx:.2f},{-glyph_cy:.2f})"
                )
                group.add(
                    dwg.use(
                        href=f"#{glyph_id}",
                        fill=fill,
                        transform=transform,
                    )
                )
            else:
                group.add(
                    dwg.text(
                        ch,
                        insert=(x, y),
                        text_anchor="middle",
                        alignment_baseline="middle",
                        font_size=font_size_px,
                        font_family=font_name,
                        fill=fill,
                    )
                )

    dwg.add(group)
    return group


def add_daemon_security_pattern_mm(
    dwg: svgwrite.Drawing,
    x_mm: float,
    y_mm: float,
    width_mm: float,
    height_mm: float,
    text: str = "LUNAMINT",
    font_name: str = "Daemon Full Working",
    font_dir: str = "./fonts",
    font_size_mm: float = 1.2,
    spacing_mm: float = 0.6,
    row_spacing_mm: float | None = None,
    angle_deg: float = 0.0,
    opacity: float = 0.35,
    color_seed: str = "",
    stagger: bool = True,
    density: float = 1.0,
    letter_scale: float = 1.0,
    hash_algo: str = "sha256",
    sm2_private_key: str | None = None,
    sm2_public_key: str | None = None,
    sm4_key: str | None = None,
    render_as_shapes: bool = False,
    dpi: float = 300.0,
) -> svgwrite.container.Group:
    x_px = mm_to_px(x_mm, dpi)
    y_px = mm_to_px(y_mm, dpi)
    width_px = mm_to_px(width_mm, dpi)
    height_px = mm_to_px(height_mm, dpi)
    font_size_px = mm_to_px(font_size_mm, dpi)
    spacing_px = mm_to_px(spacing_mm, dpi)
    row_spacing_px = mm_to_px(row_spacing_mm, dpi) if row_spacing_mm is not None else spacing_px

    return add_daemon_security_pattern_px(
        dwg,
        x_px=x_px,
        y_px=y_px,
        width_px=width_px,
        height_px=height_px,
        text=text,
        font_name=font_name,
        font_dir=font_dir,
        font_size_px=font_size_px,
        spacing_px=spacing_px,
        row_spacing_px=row_spacing_px,
        angle_deg=angle_deg,
        opacity=opacity,
        color_seed=color_seed,
        stagger=stagger,
        density=density,
        letter_scale=letter_scale,
        hash_algo=hash_algo,
        sm2_private_key=sm2_private_key,
        sm2_public_key=sm2_public_key,
        sm4_key=sm4_key,
        render_as_shapes=render_as_shapes,
    )

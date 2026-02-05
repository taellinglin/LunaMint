"""Vectorization filters for SDAPI-generated backgrounds."""
from __future__ import annotations

import base64
import hashlib
import os
import random
import time
import colorsys
from io import BytesIO
from typing import Optional

import numpy as np
import svgwrite
from PIL import Image
from skimage import color, segmentation, measure

from ..widgets.config import SDAPIConfig, sdapi_txt2img
from ..widgets.crypto import load_crypto_config, sm2_sign_bytes


def _tint_channel(value: int, factor: float) -> int:
    return int(max(0, min(255, round(value * factor))))


def _tint_color(color: tuple[int, int, int], factor: float) -> tuple[int, int, int]:
    return (
        _tint_channel(color[0], factor),
        _tint_channel(color[1], factor),
        _tint_channel(color[2], factor),
    )


def _signature_tinted_color(
    base_color: tuple[int, int, int],
    signature: bytes,
    offset: int,
    min_factor: float = 0.65,
    max_factor: float = 1.35,
) -> tuple[int, int, int]:
    if not signature:
        return _tint_color(base_color, 1.0)
    span = max(0.01, max_factor - min_factor)
    factors = []
    for channel in range(3):
        b = signature[(offset + channel) % len(signature)]
        factors.append(min_factor + (b / 255.0) * span)
    return (
        _tint_channel(base_color[0], factors[0]),
        _tint_channel(base_color[1], factors[1]),
        _tint_channel(base_color[2], factors[2]),
    )


def _hslv_to_rgb(h: float, s: float, l: float, v: float) -> tuple[int, int, int]:
    h = h % 1.0
    s = max(0.0, min(1.0, s))
    l = max(0.0, min(1.0, l))
    v = max(0.0, min(1.0, v))
    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    l_shift = (l - 0.5) * 2.0
    if l_shift >= 0:
        r = r + (1.0 - r) * l_shift
        g = g + (1.0 - g) * l_shift
        b = b + (1.0 - b) * l_shift
    else:
        factor = 1.0 + l_shift
        r *= factor
        g *= factor
        b *= factor
    return (
        _tint_channel(int(round(r * 255)), 1.0),
        _tint_channel(int(round(g * 255)), 1.0),
        _tint_channel(int(round(b * 255)), 1.0),
    )


def _signature_hslv_color(
    signature: bytes,
    offset: int,
    hue: Optional[float],
    saturation: float,
    lightness: float,
    value: float,
    hue_range: float,
) -> tuple[int, int, int]:
    if signature:
        base = signature[offset % len(signature)] / 255.0
    else:
        base = 0.0
    if hue is None:
        h = base
    else:
        h = hue
    if signature:
        wobble = (signature[(offset + 1) % len(signature)] / 255.0 - 0.5) * hue_range
        h = (h + wobble) % 1.0
    return _hslv_to_rgb(h, saturation, lightness, value)


def _expand_bytes(seed: bytes, needed: int) -> bytes:
    if len(seed) >= needed:
        return seed[:needed]
    buf = bytearray(seed)
    counter = 0
    while len(buf) < needed:
        counter_bytes = counter.to_bytes(4, "big")
        buf.extend(hashlib.sha3_256(seed + counter_bytes).digest())
        counter += 1
    return bytes(buf[:needed])


def _sm2_signature_bytes(
    seed_text: str,
    background_prompt: str,
    denomination: Optional[object],
    sm2_private_key: Optional[str],
    sm2_public_key: Optional[str],
) -> bytes:
    payload = f"{seed_text}|{background_prompt}|{denomination}".encode("utf-8")
    config = load_crypto_config()
    private_key = sm2_private_key or config.sm2_private_key
    public_key = sm2_public_key or config.sm2_public_key
    if private_key:
        try:
            return sm2_sign_bytes(payload, private_key, public_key)
        except Exception as exc:
            print(f"[!] SM2 signing failed, falling back to hash: {exc}")
    return hashlib.sha3_256(payload).digest()


def add_vectorized_background(
    dwg,
    W,
    H,
    seed_text: str = "",
    bg_dir: str = "./backgrounds",
    margin: int = 60,
    n_segments: int = 1024,
    background_prompt: str = "",
    denomination=None,
    prompt_file: str = "./background_prompt.txt",
    negative_prompt_file: str = "negative_prompt.txt",
    sdapi_config: Optional[SDAPIConfig] = None,
):
    """
    Generate a background via SDAPI and vectorize it into SVG paths.
    """
    background_path = None

    if not background_prompt:
        if os.path.exists(prompt_file):
            with open(prompt_file, "r", encoding="utf-8") as f:
                background_prompt = f.read().strip()
            print(f"[+] Using prompt from file: {background_prompt}")
        else:
            background_prompt = "kawaii oekaki Chinese DMT Studio Ghibli style banknote background"
            print(f"[!] Prompt file not found, using default: {background_prompt}")

    background_path = generate_sd_background(
        prompt=background_prompt,
        width=W - 2 * margin,
        height=H - 2 * margin,
        save_path=bg_dir,
        seed_text=seed_text,
        denomination=denomination,
        negative_prompt_file=negative_prompt_file,
        sdapi_config=sdapi_config,
    )

    if not background_path or not os.path.exists(background_path):
        files = [f for f in os.listdir(bg_dir) if f.lower().endswith((".png", ".jpg", ".jpeg"))]
        if files:
            background_path = os.path.join(bg_dir, random.choice(files))
            print(f"[+] Using random background: {background_path}")
        else:
            print("[!] No background files found.")
            return None

    max_retries = 10
    retry_delay = 0.5
    img = None
    for attempt in range(max_retries):
        try:
            print(f"[+] Attempt {attempt + 1}/{max_retries} to load background: {background_path}")
            with Image.open(background_path) as test_img:
                test_img.verify()
            img = Image.open(background_path).convert("RGB")
            break
        except Exception as exc:
            if attempt == max_retries - 1:
                print(f"[!] Failed to load background after {max_retries} attempts: {exc}")
                dwg.add(dwg.rect(insert=(0, 0), size=(W, H), fill="none"))
                return None
            print(f"[!] Background not ready (attempt {attempt + 1}), waiting {retry_delay}s...")
            time.sleep(retry_delay)

    if img is None:
        print("[!] Could not load background image, using fallback")
        dwg.add(dwg.rect(insert=(0, 0), size=(W, H), fill="none"))
        return None

    img = img.resize((W - 2 * margin, H - 2 * margin), Image.LANCZOS)
    arr = np.array(img)
    arr_lab = color.rgb2lab(arr)
    segments = segmentation.slic(arr_lab, n_segments=n_segments, compactness=20, start_label=1)

    group = dwg.g(opacity=0.7)
    for seg_val in np.unique(segments):
        mask = (segments == seg_val).astype(float)
        contours = measure.find_contours(mask, 0.5)

        for contour in contours:
            contour = contour[:, ::-1]
            contour[:, 0] += margin
            contour[:, 1] += margin

            path_data = "M " + " L ".join(f"{x:.2f},{y:.2f}" for x, y in contour) + " Z"
            avg_col = np.mean(arr[segments == seg_val], axis=0).astype(int)
            fill = svgwrite.rgb(int(avg_col[0]), int(avg_col[1]), int(avg_col[2]))
            group.add(dwg.path(d=path_data, fill=fill, stroke="none"))

    dwg.add(group)
    print(f"[+] Vectorized background with {len(np.unique(segments))} segments")
    return group


def add_vectorized_background_sm2_crosshatch(
    dwg,
    W,
    H,
    seed_text: str = "",
    bg_dir: str = "./backgrounds",
    margin: int = 60,
    n_segments: int = 1024,
    background_prompt: str = "",
    denomination=None,
    prompt_file: str = "./background_prompt.txt",
    negative_prompt_file: str = "negative_prompt.txt",
    sdapi_config: Optional[SDAPIConfig] = None,
    crosshatch_spacing: float = 6.0,
    crosshatch_stroke_width: float = 0.5,
    crosshatch_opacity: float = 0.45,
    crosshatch_alpha: Optional[float] = None,
    crosshatch_h: Optional[float] = None,
    crosshatch_s: float = 0.9,
    crosshatch_l: float = 0.65,
    crosshatch_v: float = 1.0,
    crosshatch_hue_range: float = 0.28,
    transparent_threshold: Optional[int] = 248,
    sm2_private_key: Optional[str] = None,
    sm2_public_key: Optional[str] = None,
    outline_stroke: Optional[str] = None,
    outline_stroke_width: float = 0.8,
    outline_stroke_opacity: float = 1.0,
    outline_stroke_linecap: str = "round",
    outline_stroke_linejoin: str = "round",
    crosshatch_use_mask: bool = False,
    crosshatch_flatten: bool = True,
    merge_similar_colors: bool = False,
    merge_color_bin: int = 16,
    crosshatch_on_merged: bool = True,
    vectorize_mode: str = "slic",
    color_quantize_colors: Optional[int] = None,
    color_quantize_bin: int = 16,
    color_quantize_dither: bool = False,
    anime_mode: bool = False,
):
    """
    Vectorize an SD background and overlay SM2-encoded crosshatching on each segment.
    """
    background_path = None

    if not background_prompt:
        if os.path.exists(prompt_file):
            with open(prompt_file, "r", encoding="utf-8") as f:
                background_prompt = f.read().strip()
            print(f"[+] Using prompt from file: {background_prompt}")
        else:
            background_prompt = "kawaii oekaki Chinese DMT Studio Ghibli style banknote background"
            print(f"[!] Prompt file not found, using default: {background_prompt}")

    background_path = generate_sd_background(
        prompt=background_prompt,
        width=W - 2 * margin,
        height=H - 2 * margin,
        save_path=bg_dir,
        seed_text=seed_text,
        denomination=denomination,
        negative_prompt_file=negative_prompt_file,
        sdapi_config=sdapi_config,
    )

    if not background_path or not os.path.exists(background_path):
        files = [f for f in os.listdir(bg_dir) if f.lower().endswith((".png", ".jpg", ".jpeg"))]
        if files:
            background_path = os.path.join(bg_dir, random.choice(files))
            print(f"[+] Using random background: {background_path}")
        else:
            print("[!] No background files found.")
            return None

    max_retries = 10
    retry_delay = 0.5
    img = None
    for attempt in range(max_retries):
        try:
            print(f"[+] Attempt {attempt + 1}/{max_retries} to load background: {background_path}")
            with Image.open(background_path) as test_img:
                test_img.verify()
            img = Image.open(background_path).convert("RGB")
            break
        except Exception as exc:
            if attempt == max_retries - 1:
                print(f"[!] Failed to load background after {max_retries} attempts: {exc}")
                dwg.add(dwg.rect(insert=(0, 0), size=(W, H), fill="none"))
                return None
            print(f"[!] Background not ready (attempt {attempt + 1}), waiting {retry_delay}s...")
            time.sleep(retry_delay)

    if img is None:
        print("[!] Could not load background image, using fallback")
        dwg.add(dwg.rect(insert=(0, 0), size=(W, H), fill="none"))
        return None

    img = img.resize((W - 2 * margin, H - 2 * margin), Image.LANCZOS)
    vectorize_mode = (vectorize_mode or "slic").strip().lower()
    if anime_mode:
        if vectorize_mode == "slic":
            vectorize_mode = "color"
        if color_quantize_colors is None:
            color_quantize_colors = 12
        if outline_stroke is None:
            outline_stroke = "#111111"
        outline_stroke_width = max(outline_stroke_width, 1.2)
        merge_similar_colors = True

    if color_quantize_colors is not None:
        colors = max(2, int(color_quantize_colors))
        dither_mode = Image.FLOYDSTEINBERG if color_quantize_dither else Image.NONE
        img = img.convert("P", palette=Image.ADAPTIVE, colors=colors, dither=dither_mode).convert("RGB")

    arr = np.array(img)
    if vectorize_mode == "color":
        bin_size = max(1, int(color_quantize_bin))
        if color_quantize_colors is None and bin_size > 1:
            arr = (np.round(arr / bin_size) * bin_size).clip(0, 255).astype(np.uint8)
        flat = arr.reshape(-1, 3)
        _, inverse = np.unique(flat, axis=0, return_inverse=True)
        segments = inverse.reshape(arr.shape[0], arr.shape[1]) + 1
        segment_ids = np.unique(segments)
    else:
        arr_lab = color.rgb2lab(arr)
        segments = segmentation.slic(arr_lab, n_segments=n_segments, compactness=20, start_label=1)
        segment_ids = np.unique(segments)

    signature = _sm2_signature_bytes(
        seed_text=seed_text,
        background_prompt=background_prompt,
        denomination=denomination,
        sm2_private_key=sm2_private_key,
        sm2_public_key=sm2_public_key,
    )
    signature = _expand_bytes(signature, max(2, len(segment_ids) * 2))

    hatch_alpha = crosshatch_opacity if crosshatch_alpha is None else crosshatch_alpha
    fill_group = dwg.g(opacity=0.7)
    hatch_group = dwg.g(opacity=hatch_alpha)
    outline_group = dwg.g()
    clip_prefix = hashlib.md5(signature).hexdigest()[:8]

    if crosshatch_flatten:
        try:
            from shapely.affinity import rotate as _rotate_geom
            from shapely.geometry import LineString, Polygon
        except Exception as exc:
            raise RuntimeError(
                "crosshatch_flatten requires shapely to clip hatch strokes. "
                "Install shapely or disable crosshatch_flatten."
            ) from exc

    merge_bins = max(1, int(merge_color_bin))
    merge_geoms: dict[tuple[int, int, int], list] = {}
    merge_order: list[tuple[int, int, int]] = []
    if merge_similar_colors:
        try:
            import shapely.ops as _shape_ops
            from shapely.geometry import Polygon as _MergePolygon
            from shapely.geometry import MultiPolygon as _MergeMultiPolygon
            from shapely.geometry import GeometryCollection as _MergeGeometryCollection
        except Exception as exc:
            raise RuntimeError(
                "merge_similar_colors requires shapely to union segments. "
                "Install shapely or disable merge_similar_colors."
            ) from exc

        def _quantize_color(rgb_vals: tuple[int, int, int]) -> tuple[int, int, int]:
            return tuple(
                max(0, min(255, int(round(v / merge_bins) * merge_bins))) for v in rgb_vals
            )

        def _geom_to_paths(geom) -> list[str]:
            if geom is None or geom.is_empty:
                return []
            polygons = []
            if isinstance(geom, _MergePolygon):
                polygons = [geom]
            elif isinstance(geom, _MergeMultiPolygon):
                polygons = list(geom.geoms)
            elif isinstance(geom, _MergeGeometryCollection):
                polygons = [g for g in geom.geoms if isinstance(g, _MergePolygon)]
            paths: list[str] = []
            for poly in polygons:
                parts: list[str] = []
                exterior = list(poly.exterior.coords)
                if exterior:
                    parts.append("M " + " L ".join(f"{x:.2f},{y:.2f}" for x, y in exterior) + " Z")
                for interior in poly.interiors:
                    coords = list(interior.coords)
                    if coords:
                        parts.append("M " + " L ".join(f"{x:.2f},{y:.2f}" for x, y in coords) + " Z")
                if parts:
                    paths.append(" ".join(parts))
            return paths

        def _geom_polygons(geom) -> list:
            if geom is None or geom.is_empty:
                return []
            if isinstance(geom, _MergePolygon):
                return [geom]
            if isinstance(geom, _MergeMultiPolygon):
                return list(geom.geoms)
            if isinstance(geom, _MergeGeometryCollection):
                return [g for g in geom.geoms if isinstance(g, _MergePolygon)]
            return []

    for idx, seg_val in enumerate(segment_ids):
        mask = (segments == seg_val).astype(float)
        contours = measure.find_contours(mask, 0.5)

        avg_col = np.mean(arr[segments == seg_val], axis=0).astype(int)
        if transparent_threshold is not None:
            if all(channel >= transparent_threshold for channel in avg_col.tolist()):
                continue
        fill = svgwrite.rgb(int(avg_col[0]), int(avg_col[1]), int(avg_col[2]))
        hatch_color_a = svgwrite.rgb(
            *_signature_hslv_color(
                signature,
                idx * 5,
                crosshatch_h,
                crosshatch_s,
                crosshatch_l,
                crosshatch_v,
                crosshatch_hue_range,
            )
        )
        hatch_color_b = svgwrite.rgb(
            *_signature_hslv_color(
                signature,
                idx * 5 + 2,
                None if crosshatch_h is None else (crosshatch_h + 0.5),
                crosshatch_s,
                crosshatch_l,
                crosshatch_v,
                crosshatch_hue_range,
            )
        )

        angle_base = (signature[(idx * 2) % len(signature)] / 255.0) * 160.0 - 80.0
        angle_offset = (signature[(idx * 2 + 1) % len(signature)] / 255.0) * 40.0 - 20.0
        angle_a = angle_base
        angle_b = angle_base + 90.0 + angle_offset

        for contour_idx, contour in enumerate(contours):
            contour = contour[:, ::-1]
            contour[:, 0] += margin
            contour[:, 1] += margin

            path_data = "M " + " L ".join(f"{x:.2f},{y:.2f}" for x, y in contour) + " Z"
            if merge_similar_colors:
                try:
                    merged_poly = _MergePolygon(contour).buffer(0)
                except Exception:
                    merged_poly = None
                if merged_poly is not None and not merged_poly.is_empty:
                    key = _quantize_color(tuple(avg_col.tolist()))
                    if key not in merge_geoms:
                        merge_order.append(key)
                    merge_geoms.setdefault(key, []).append(merged_poly)
            else:
                fill_group.add(dwg.path(d=path_data, fill=fill, stroke="none"))
            if outline_stroke and str(outline_stroke).lower() != "none":
                outline_group.add(
                    dwg.path(
                        d=path_data,
                        fill="none",
                        stroke=str(outline_stroke),
                        stroke_width=outline_stroke_width,
                        stroke_opacity=outline_stroke_opacity,
                        stroke_linecap=outline_stroke_linecap,
                        stroke_linejoin=outline_stroke_linejoin,
                    )
                )

            if not (merge_similar_colors and crosshatch_on_merged):
                min_x = float(np.min(contour[:, 0]))
                max_x = float(np.max(contour[:, 0]))
                min_y = float(np.min(contour[:, 1]))
                max_y = float(np.max(contour[:, 1]))
                width = max_x - min_x
                height = max_y - min_y
                if max(width, height) < crosshatch_spacing * 2:
                    continue

                region_group = dwg.g()
                polygon = None
                if crosshatch_flatten:
                    try:
                        polygon = Polygon(contour).buffer(0)
                    except Exception:
                        polygon = None
                if not crosshatch_flatten:
                    if crosshatch_use_mask:
                        mask_id = f"sm2mask_{clip_prefix}_{seg_val}_{contour_idx}"
                        mask = dwg.defs.add(
                            dwg.mask(id=mask_id, maskUnits="userSpaceOnUse", maskContentUnits="userSpaceOnUse")
                        )
                        mask.add(dwg.rect(insert=(0, 0), size=(W, H), fill="#000000"))
                        mask.add(dwg.path(d=path_data, fill="#ffffff"))
                        region_group.update({"mask": f"url(#{mask_id})"})
                    else:
                        clip_id = f"sm2hatch_{clip_prefix}_{seg_val}_{contour_idx}"
                        clip = dwg.defs.add(dwg.clipPath(id=clip_id, clipPathUnits="userSpaceOnUse"))
                        clip.add(dwg.path(d=path_data))
                        region_group.update({"clip-path": f"url(#{clip_id})"})

                cx = (min_x + max_x) / 2.0
                cy = (min_y + max_y) / 2.0
                pad = max(2.0, crosshatch_spacing * 0.75)
                line_start_x = min_x - pad
                line_end_x = max_x + pad

                def _emit_line_segments(geom, stroke_color: str) -> None:
                    if geom.is_empty:
                        return
                    if geom.geom_type == "LineString":
                        coords = list(geom.coords)
                        if len(coords) < 2:
                            return
                        for i in range(len(coords) - 1):
                            region_group.add(
                                dwg.line(
                                    start=coords[i],
                                    end=coords[i + 1],
                                    stroke=stroke_color,
                                    stroke_width=crosshatch_stroke_width,
                                    opacity=0.9,
                                )
                            )
                        return
                    if geom.geom_type in {"MultiLineString", "GeometryCollection"}:
                        for part in geom.geoms:
                            _emit_line_segments(part, stroke_color)

                def _add_hatch_lines(angle: float, stroke_color: str) -> None:
                    y = min_y - pad
                    while y <= max_y + pad:
                        if crosshatch_flatten and polygon is not None and not polygon.is_empty:
                            base_line = LineString([(line_start_x, y), (line_end_x, y)])
                            rotated = _rotate_geom(base_line, angle, origin=(cx, cy), use_radians=False)
                            clipped = rotated.intersection(polygon)
                            _emit_line_segments(clipped, stroke_color)
                        else:
                            angle_group = dwg.g()
                            angle_group.update({"transform": f"rotate({angle:.2f},{cx:.2f},{cy:.2f})"})
                            angle_group.add(
                                dwg.line(
                                    start=(line_start_x, y),
                                    end=(line_end_x, y),
                                    stroke=stroke_color,
                                    stroke_width=crosshatch_stroke_width,
                                    opacity=0.9,
                                )
                            )
                            region_group.add(angle_group)
                        y += crosshatch_spacing

                _add_hatch_lines(angle_a, hatch_color_a)
                _add_hatch_lines(angle_b, hatch_color_b)
                hatch_group.add(region_group)

    dwg.add(fill_group)
    if merge_similar_colors and merge_geoms:
        for merge_idx, key in enumerate(merge_order or list(merge_geoms.keys())):
            geoms = merge_geoms.get(key, [])
            if not geoms:
                continue
            merged = _shape_ops.unary_union(geoms)
            if merged is None or merged.is_empty:
                continue
            fill = svgwrite.rgb(key[0], key[1], key[2])
            for path_data in _geom_to_paths(merged):
                fill_group.add(dwg.path(d=path_data, fill=fill, stroke="none"))

            if not crosshatch_on_merged:
                continue
            hatch_color_a = svgwrite.rgb(
                *_signature_hslv_color(
                    signature,
                    merge_idx * 5,
                    crosshatch_h,
                    crosshatch_s,
                    crosshatch_l,
                    crosshatch_v,
                    crosshatch_hue_range,
                )
            )
            hatch_color_b = svgwrite.rgb(
                *_signature_hslv_color(
                    signature,
                    merge_idx * 5 + 2,
                    None if crosshatch_h is None else (crosshatch_h + 0.5),
                    crosshatch_s,
                    crosshatch_l,
                    crosshatch_v,
                    crosshatch_hue_range,
                )
            )
            angle_base = (signature[(merge_idx * 2) % len(signature)] / 255.0) * 160.0 - 80.0
            angle_offset = (signature[(merge_idx * 2 + 1) % len(signature)] / 255.0) * 40.0 - 20.0
            angle_a = angle_base
            angle_b = angle_base + 90.0 + angle_offset

            polygons = _geom_polygons(merged)
            for poly_idx, polygon in enumerate(polygons):
                min_x, min_y, max_x, max_y = polygon.bounds
                width = max_x - min_x
                height = max_y - min_y
                if max(width, height) < crosshatch_spacing * 2:
                    continue
                region_group = dwg.g()
                if not crosshatch_flatten:
                    clip_id = f"sm2hatch_merge_{clip_prefix}_{key[0]}_{key[1]}_{key[2]}_{poly_idx}"
                    clip = dwg.defs.add(dwg.clipPath(id=clip_id, clipPathUnits="userSpaceOnUse"))
                    for path_data in _geom_to_paths(polygon):
                        clip.add(dwg.path(d=path_data))
                    region_group.update({"clip-path": f"url(#{clip_id})"})

                cx = (min_x + max_x) / 2.0
                cy = (min_y + max_y) / 2.0
                pad = max(2.0, crosshatch_spacing * 0.75)
                line_start_x = min_x - pad
                line_end_x = max_x + pad

                def _emit_line_segments(geom, stroke_color: str) -> None:
                    if geom.is_empty:
                        return
                    if geom.geom_type == "LineString":
                        coords = list(geom.coords)
                        if len(coords) < 2:
                            return
                        for i in range(len(coords) - 1):
                            region_group.add(
                                dwg.line(
                                    start=coords[i],
                                    end=coords[i + 1],
                                    stroke=stroke_color,
                                    stroke_width=crosshatch_stroke_width,
                                    opacity=0.9,
                                )
                            )
                        return
                    if geom.geom_type in {"MultiLineString", "GeometryCollection"}:
                        for part in geom.geoms:
                            _emit_line_segments(part, stroke_color)

                def _add_hatch_lines(angle: float, stroke_color: str) -> None:
                    y = min_y - pad
                    while y <= max_y + pad:
                        if crosshatch_flatten:
                            base_line = LineString([(line_start_x, y), (line_end_x, y)])
                            rotated = _rotate_geom(base_line, angle, origin=(cx, cy), use_radians=False)
                            clipped = rotated.intersection(polygon)
                            _emit_line_segments(clipped, stroke_color)
                        else:
                            angle_group = dwg.g()
                            angle_group.update({"transform": f"rotate({angle:.2f},{cx:.2f},{cy:.2f})"})
                            angle_group.add(
                                dwg.line(
                                    start=(line_start_x, y),
                                    end=(line_end_x, y),
                                    stroke=stroke_color,
                                    stroke_width=crosshatch_stroke_width,
                                    opacity=0.9,
                                )
                            )
                            region_group.add(angle_group)
                        y += crosshatch_spacing

                _add_hatch_lines(angle_a, hatch_color_a)
                _add_hatch_lines(angle_b, hatch_color_b)
                hatch_group.add(region_group)
    dwg.add(hatch_group)
    if outline_stroke and str(outline_stroke).lower() != "none":
        dwg.add(outline_group)
    print(
        f"[+] Vectorized background with SM2 crosshatching for {len(segment_ids)} segments"
    )
    return hatch_group


def generate_sd_background(
    prompt: str,
    width: int = 1600,
    height: int = 600,
    save_path: str = "./backgrounds",
    seed_text: str = "",
    denomination=None,
    negative_prompt_file: str = "negative_prompt.txt",
    sdapi_config: Optional[SDAPIConfig] = None,
):
    os.makedirs(save_path, exist_ok=True)

    if os.path.exists(negative_prompt_file):
        with open(negative_prompt_file, "r", encoding="utf-8") as f:
            negative_prompt = f.read().strip()
    else:
        negative_prompt = "text, words, blurry, low quality, watermark, signature"

    print(f"[+] Generating background with prompt: {prompt}")
    print(f"[+] Negative prompt: {negative_prompt}")

    payload = {
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "width": width,
        "height": height,
        "seed": random.randint(0, 2**32 - 1),
        "steps": 20,
        "cfg_scale": 7.5,
        "sampler_name": "Euler a",
        "batch_size": 1,
        "n_iter": 1,
        "restore_faces": False,
        "tiling": True,
        "enable_hr": False,
    }

    try:
        result = sdapi_txt2img(payload, config=sdapi_config)
        images = result.get("images", [])
        if images:
            image_data = images[0]
            image = Image.open(BytesIO(base64.b64decode(image_data)))

            prompt_hash = hashlib.md5(prompt.encode()).hexdigest()[:6]
            denom_str = f"d{denomination}_" if denomination is not None else ""
            seed_str = f"_{hashlib.md5(seed_text.encode()).hexdigest()[:4]}" if seed_text else ""
            filename = f"bg_{denom_str}{prompt_hash}{seed_str}_{int(time.time())}.png"
            filepath = os.path.join(save_path, filename)
            image.save(filepath)
            print(f"[+] Generated background: {filepath}")
            return filepath
    except Exception as exc:
        print(f"[!] Error generating background: {exc}")
        return None

    return None

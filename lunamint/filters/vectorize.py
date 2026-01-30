"""Vectorization filters for SDAPI-generated backgrounds."""
from __future__ import annotations

import base64
import hashlib
import os
import random
import time
from io import BytesIO
from typing import Optional

import numpy as np
import svgwrite
from PIL import Image
from skimage import color, segmentation, measure

from ..widgets.config import SDAPIConfig, sdapi_txt2img


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
                dwg.add(dwg.rect(insert=(0, 0), size=(W, H), fill="#f0f0f0"))
                return None
            print(f"[!] Background not ready (attempt {attempt + 1}), waiting {retry_delay}s...")
            time.sleep(retry_delay)

    if img is None:
        print("[!] Could not load background image, using fallback")
        dwg.add(dwg.rect(insert=(0, 0), size=(W, H), fill="#f0f0f0"))
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

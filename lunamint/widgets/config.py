"""Configuration helpers for external services like SDAPI."""
from __future__ import annotations

from dataclasses import dataclass
import os
import threading
import time
from typing import Any, Callable, Dict, Optional

import requests

ProgressCallback = Callable[[str], None]


@dataclass
class SDAPIConfig:
    base_url: str = "http://127.0.0.1:7777"
    txt2img_path: str = "/sdapi/v1/txt2img"
    progress_path: str = "/sdapi/v1/progress"
    model: Optional[str] = None
    timeout: int = 120
    enable_progress: bool = True
    progress_interval: float = 1.0

    @property
    def txt2img_url(self) -> str:
        if self.base_url.endswith(self.txt2img_path):
            return self.base_url
        if "/sdapi/v1/txt2img" in self.base_url:
            return self.base_url
        return self.base_url.rstrip("/") + self.txt2img_path

    @property
    def progress_url(self) -> str:
        if self.base_url.endswith(self.txt2img_path):
            return self.base_url[: -len(self.txt2img_path)] + self.progress_path
        if "/sdapi/v1/txt2img" in self.base_url:
            return self.base_url.replace("/sdapi/v1/txt2img", self.progress_path)
        return self.base_url.rstrip("/") + self.progress_path


def load_sdapi_config() -> SDAPIConfig:
    base_url = os.getenv("SD_API_BASE_URL") or os.getenv("SD_API_URL") or "http://127.0.0.1:7777"
    model = os.getenv("SD_API_MODEL") or None
    timeout = int(os.getenv("SD_API_TIMEOUT", "120"))
    enable_progress = os.getenv("SD_API_PROGRESS", "true").lower() == "true"
    progress_interval = float(os.getenv("SD_API_PROGRESS_INTERVAL", "1.0"))

    return SDAPIConfig(
        base_url=base_url,
        model=model,
        timeout=timeout,
        enable_progress=enable_progress,
        progress_interval=progress_interval,
    )


def _poll_progress(config: SDAPIConfig, stop_event: threading.Event, progress_callback: ProgressCallback) -> None:
    while not stop_event.is_set():
        try:
            resp = requests.get(config.progress_url, timeout=min(5, config.timeout))
            resp.raise_for_status()
            payload = resp.json()
            progress = float(payload.get("progress", 0.0)) * 100.0
            progress_callback(f"SDAPI progress: {progress:.1f}%")
        except Exception:
            pass
        stop_event.wait(config.progress_interval)


def sdapi_txt2img(
    payload: Dict[str, Any],
    config: Optional[SDAPIConfig] = None,
    progress_callback: Optional[ProgressCallback] = None,
) -> Dict[str, Any]:
    cfg = config or load_sdapi_config()
    request_payload = dict(payload)

    if cfg.model:
        override = dict(request_payload.get("override_settings", {}))
        override["sd_model_checkpoint"] = cfg.model
        request_payload["override_settings"] = override
        request_payload.setdefault("override_settings_restore_afterwards", True)

    stop_event = threading.Event()
    progress_thread = None
    if progress_callback and cfg.enable_progress:
        progress_thread = threading.Thread(
            target=_poll_progress,
            args=(cfg, stop_event, progress_callback),
            daemon=True,
        )
        progress_thread.start()

    try:
        response = requests.post(cfg.txt2img_url, json=request_payload, timeout=cfg.timeout)
        response.raise_for_status()
        return response.json()
    finally:
        stop_event.set()
        if progress_thread:
            progress_thread.join(timeout=1.0)

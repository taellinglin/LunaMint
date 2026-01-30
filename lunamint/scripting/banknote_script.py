"""Banknote-only script runner built on top of the layout language."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from .runtime import compile_layout


@dataclass
class BanknoteScriptConfig:
    shared: Dict[str, Any]
    front: Dict[str, Any]
    back: Dict[str, Any]


def build_banknote_config(source: str) -> BanknoteScriptConfig:
    compiled = compile_layout(source)
    values = compiled.get("values", {})

    shared: Dict[str, Any] = {}
    front: Dict[str, Any] = {}
    back: Dict[str, Any] = {}

    for key, value in values.items():
        if key.startswith("front."):
            front[key[len("front."):]] = value
        elif key.startswith("back."):
            back[key[len("back."):]] = value
        else:
            shared[key] = value

    return BanknoteScriptConfig(shared=shared, front=front, back=back)


def select_param(config: BanknoteScriptConfig, key: str, fallback: Any = None) -> Any:
    if key in config.shared:
        return config.shared[key]
    return fallback

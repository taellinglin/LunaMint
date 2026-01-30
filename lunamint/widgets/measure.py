"""Shared measurement helpers."""
from __future__ import annotations


def mm_to_px(mm: float, dpi: float = 300.0) -> float:
    return mm * dpi / 25.4


def cm_to_px(cm: float, dpi: float = 300.0) -> float:
    return cm * dpi / 2.54


def pt_to_px(pt: float, dpi: float = 300.0) -> float:
    return pt * dpi / 72.0


def snap_px(value: float, grid: float = 16.0) -> float:
    if grid <= 0:
        return value
    return round(value / grid) * grid

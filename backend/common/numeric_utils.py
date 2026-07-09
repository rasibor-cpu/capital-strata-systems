from __future__ import annotations

import math
from typing import Any


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return default
    return numeric if math.isfinite(numeric) else default


def safe_int(value: Any, default: int = 0) -> int:
    try:
        # Cast via float to handle string representation of floats like "42.0"
        return int(float(value))
    except (TypeError, ValueError):
        return default


def safe_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    val_str = str(value).strip().lower()
    if val_str in {"true", "yes", "1", "on", "ok"}:
        return True
    if val_str in {"false", "no", "0", "off", "none", "null"}:
        return False
    return default


def clamp(value: Any, low: float, high: float, default: float | None = None) -> float:
    numeric = safe_float(value, low if default is None else default)
    return max(low, min(high, numeric))


def normalize_percentage(value: Any, default: float = 0.0) -> float:
    """Clamp a percentage value to [0.0, 100.0] range."""
    return clamp(value, 0.0, 100.0, default=default)

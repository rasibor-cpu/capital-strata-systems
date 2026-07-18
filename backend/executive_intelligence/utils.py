"""Helpers for Executive Intelligence Engine."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from backend.executive_intelligence.constants import FRESHNESS_ALIAS


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def as_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def normalize_freshness(raw: Any) -> str:
    text = str(raw or "UNAVAILABLE").strip().upper()
    return FRESHNESS_ALIAS.get(text, "UNAVAILABLE" if text not in {"FRESH", "AGING", "STALE", "UNAVAILABLE"} else text)


def worst_freshness(*labels: str) -> str:
    rank = {"FRESH": 0, "AGING": 1, "STALE": 2, "UNAVAILABLE": 3}
    worst = "FRESH"
    for label in labels:
        n = normalize_freshness(label)
        if rank.get(n, 3) > rank.get(worst, 0):
            worst = n
    return worst


def clamp01(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:  # NaN
        return None
    if number > 1.0 and number <= 100.0:
        number = number / 100.0
    if number < 0.0:
        return 0.0
    if number > 1.0:
        return 1.0
    return float(number)


def confidence_band(score: float | None) -> str:
    if score is None:
        return "UNAVAILABLE"
    pct = score * 100.0
    if pct >= 95:
        return "Exceptional"
    if pct >= 90:
        return "Very High"
    if pct >= 80:
        return "High"
    if pct >= 70:
        return "Moderate"
    if pct >= 60:
        return "Low"
    return "Very Low"


def posture_from_runtime(status: str) -> str:
    s = str(status or "").upper()
    if s in {"GREEN", "HEALTHY", "OK", "PASS"}:
        return "GREEN"
    if s in {"AMBER", "DEGRADED", "RECOVERING", "WARNING", "PARTIAL", "DEFENSIVE"}:
        return "AMBER"
    if s in {"RED", "FAILED", "FAIL", "STALE", "CRITICAL"}:
        return "RED"
    return "UNAVAILABLE"


def safe_str(value: Any, default: str = "UNAVAILABLE") -> str:
    if value is None or value == "":
        return default
    return str(value)

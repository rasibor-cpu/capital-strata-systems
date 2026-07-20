"""Phase 179 — EDI models and constants (no financial arithmetic)."""

from __future__ import annotations

from typing import Any

SCHEMA_VERSION = "css.executive_decision_intelligence.v1"

EXECUTIVE_STATES = (
    "STABLE",
    "ATTENTION",
    "STRESSED",
    "NOT_READY",
    "DEGRADED",
)

PRIORITY_LEVELS = ("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO")

DISCLAIMER = (
    "Executive Decision Intelligence is advisory decision-support only. "
    "It does not calculate financial statements, does not execute trades, "
    "and does not create live trading authority."
)


def empty_item(code: str, title: str, **extra: Any) -> dict[str, Any]:
    item = {
        "code": code,
        "title": title,
        "priority": "INFO",
        "rank": 0,
        "confidence": 0.0,
        "advisory_only": True,
        "trading_impact": False,
        "executable": False,
    }
    item.update(extra)
    return item

"""Phase 179 — confidence aggregation from upstream categorical signals (no P&L math)."""

from __future__ import annotations

from typing import Any


def _clip(value: float) -> float:
    return max(0.0, min(1.0, round(float(value), 4)))


def compute_decision_confidence(
    *,
    financial_summary: dict[str, Any] | None,
    brief_readiness: dict[str, Any] | None,
    operational: dict[str, Any] | None,
    input_errors: list[str] | None = None,
) -> dict[str, Any]:
    """
    Derive a confidence band from readiness / traffic / operational freshness.
    Does not use monetary amounts.
    """
    summary = financial_summary if isinstance(financial_summary, dict) else {}
    brief = brief_readiness if isinstance(brief_readiness, dict) else {}
    ops = operational if isinstance(operational, dict) else {}
    errors = list(input_errors or [])

    score = 0.75
    notes: list[str] = []

    ready = str(summary.get("reporting_readiness") or "NOT_READY").upper()
    light = str(summary.get("profitability_traffic_light") or "NOT_AVAILABLE").upper()
    brief_state = str(brief.get("overall_state") or brief.get("state") or "").upper()

    if ready == "GREEN":
        score += 0.1
    elif ready == "AMBER":
        score -= 0.05
        notes.append("financial_reporting_amber")
    elif ready == "RED":
        score -= 0.15
        notes.append("financial_reporting_red")
    elif ready == "NOT_READY":
        score -= 0.25
        notes.append("financial_reporting_not_ready")

    if light == "NOT_AVAILABLE":
        score -= 0.1
        notes.append("profitability_traffic_unavailable")
    elif light == "RED":
        score -= 0.05
        notes.append("profitability_traffic_red")

    if brief_state == "NOT_READY":
        score -= 0.1
        notes.append("brief_readiness_not_ready")
    elif brief_state == "RED":
        score -= 0.05
        notes.append("brief_readiness_red")

    if ops.get("runtime_offline"):
        score -= 0.2
        notes.append("runtime_offline")
    if ops.get("data_stale"):
        score -= 0.1
        notes.append("operational_data_stale")

    if errors:
        score -= min(0.3, 0.08 * len(errors))
        notes.append("upstream_provider_errors")

    overall = _clip(score)
    if overall >= 0.8:
        band = "HIGH"
    elif overall >= 0.55:
        band = "MEDIUM"
    elif overall >= 0.3:
        band = "LOW"
    else:
        band = "VERY_LOW"

    return {
        "overall_confidence": overall,
        "confidence_band": band,
        "notes": notes,
        "advisory_only": True,
        "trading_impact": False,
    }

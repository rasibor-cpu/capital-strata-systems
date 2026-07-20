"""Phase 179 — opportunity ranking from categorical upstream signals (no financial math)."""

from __future__ import annotations

from typing import Any

from backend.executive_decision_intelligence.decision_prioritizer import dedupe_by_code


def build_opportunity_priorities(
    *,
    financial_summary: dict[str, Any] | None,
    operational: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    summary = financial_summary if isinstance(financial_summary, dict) else {}
    ops = operational if isinstance(operational, dict) else {}

    light = str(summary.get("profitability_traffic_light") or "NOT_AVAILABLE").upper()
    ready = str(summary.get("reporting_readiness") or "").upper()

    if light == "GREEN" and ready == "GREEN":
        items.append(
            {
                "code": "reporting_stable_for_distribution",
                "title": "Financial reporting posture is stable for executive distribution.",
                "reason": "Phase 178 readiness GREEN and traffic light GREEN.",
                "priority": "MEDIUM",
                "source": "phase178_summary",
                "confidence": 0.85,
                "advisory_only": True,
                "trading_impact": False,
                "executable": False,
            }
        )

    if light == "GREEN" and ready in {"GREEN", "AMBER"}:
        items.append(
            {
                "code": "review_growth_and_efficiency",
                "title": "Review growth and operating-efficiency opportunities.",
                "reason": "Profitability traffic light is GREEN; focus shifts to opportunity review.",
                "priority": "LOW",
                "source": "phase178_traffic_light",
                "confidence": 0.7,
                "advisory_only": True,
                "trading_impact": False,
                "executable": False,
            }
        )

    if ops.get("alert_count") == 0 and not ops.get("runtime_offline"):
        items.append(
            {
                "code": "ops_quiet_window",
                "title": "Operational quiet window — advance non-urgent governance work.",
                "reason": "No active alerts and runtime evidence available.",
                "priority": "INFO",
                "source": "mission_control",
                "confidence": 0.65,
                "advisory_only": True,
                "trading_impact": False,
                "executable": False,
            }
        )

    if summary.get("balance_sheet_balanced") is True and summary.get("cash_flow_reconciled") is True:
        items.append(
            {
                "code": "statement_integrity_ok",
                "title": "Statement integrity flags are clear — prioritize forward planning.",
                "reason": "Balance sheet balanced and cash flow reconciled per Phase 178.",
                "priority": "LOW",
                "source": "phase178_summary",
                "confidence": 0.8,
                "advisory_only": True,
                "trading_impact": False,
                "executable": False,
            }
        )

    if not items:
        items.append(
            {
                "code": "insufficient_opportunity_signals",
                "title": "Insufficient opportunity signals from available upstream inputs.",
                "reason": "Stabilize reporting/readiness before opportunity ranking expands.",
                "priority": "INFO",
                "source": "edi",
                "confidence": 0.4,
                "advisory_only": True,
                "trading_impact": False,
                "executable": False,
            }
        )

    return dedupe_by_code(items)

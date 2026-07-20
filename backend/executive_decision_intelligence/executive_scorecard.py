"""Phase 179 — executive scorecard from categorical upstream states (no P&L math)."""

from __future__ import annotations

from typing import Any


def _state_score(token: str) -> str:
    t = (token or "").upper()
    if t in {"GREEN", "HEALTHY", "OK", "NORMAL", "STABLE"}:
        return "GOOD"
    if t in {"AMBER", "WARN", "WARNING", "ELEVATED"}:
        return "WATCH"
    if t in {"RED", "BAD", "CRITICAL", "DOWN", "OFFLINE", "NOT_READY"}:
        return "BAD"
    if t in {"NOT_AVAILABLE", "UNKNOWN", ""}:
        return "NEUTRAL"
    return "NEUTRAL"


def build_executive_scorecard(
    *,
    financial_summary: dict[str, Any] | None,
    operational: dict[str, Any] | None,
    brief_readiness: dict[str, Any] | None,
    confidence: dict[str, Any] | None,
) -> dict[str, Any]:
    summary = financial_summary if isinstance(financial_summary, dict) else {}
    ops = operational if isinstance(operational, dict) else {}
    brief = brief_readiness if isinstance(brief_readiness, dict) else {}
    conf = confidence if isinstance(confidence, dict) else {}

    rows = [
        {
            "dimension": "Financial Reporting Readiness",
            "state": str(summary.get("reporting_readiness") or "NOT_READY"),
            "band": _state_score(str(summary.get("reporting_readiness") or "NOT_READY")),
            "source": "phase178",
        },
        {
            "dimension": "Profitability Traffic Light",
            "state": str(summary.get("profitability_traffic_light") or "NOT_AVAILABLE"),
            "band": _state_score(str(summary.get("profitability_traffic_light") or "NOT_AVAILABLE")),
            "source": "phase178",
        },
        {
            "dimension": "Balance Sheet Integrity",
            "state": (
                "BALANCED"
                if summary.get("balance_sheet_balanced") is True
                else ("UNBALANCED" if summary.get("balance_sheet_balanced") is False else "UNKNOWN")
            ),
            "band": (
                "GOOD"
                if summary.get("balance_sheet_balanced") is True
                else ("BAD" if summary.get("balance_sheet_balanced") is False else "NEUTRAL")
            ),
            "source": "phase178",
        },
        {
            "dimension": "Cash Flow Reconciliation",
            "state": (
                "RECONCILED"
                if summary.get("cash_flow_reconciled") is True
                else ("UNRECONCILED" if summary.get("cash_flow_reconciled") is False else "UNKNOWN")
            ),
            "band": (
                "GOOD"
                if summary.get("cash_flow_reconciled") is True
                else ("BAD" if summary.get("cash_flow_reconciled") is False else "NEUTRAL")
            ),
            "source": "phase178",
        },
        {
            "dimension": "Executive Brief Readiness",
            "state": str(brief.get("overall_state") or brief.get("state") or "UNKNOWN"),
            "band": _state_score(str(brief.get("overall_state") or brief.get("state") or "")),
            "source": "phase176j",
        },
        {
            "dimension": "Runtime / Platform",
            "state": "OFFLINE" if ops.get("runtime_offline") else str(ops.get("runtime_health") or "UNKNOWN"),
            "band": "BAD" if ops.get("runtime_offline") else _state_score(str(ops.get("runtime_health") or "")),
            "source": "mission_control",
        },
        {
            "dimension": "Risk Posture",
            "state": str(ops.get("risk_state") or "UNKNOWN"),
            "band": _state_score(str(ops.get("risk_state") or "")),
            "source": "mission_control",
        },
        {
            "dimension": "Decision Confidence",
            "state": str(conf.get("confidence_band") or "VERY_LOW"),
            "band": (
                "GOOD"
                if conf.get("confidence_band") == "HIGH"
                else ("WATCH" if conf.get("confidence_band") == "MEDIUM" else "BAD")
            ),
            "source": "edi",
        },
    ]

    return {
        "rows": rows,
        "advisory_only": True,
        "trading_impact": False,
    }

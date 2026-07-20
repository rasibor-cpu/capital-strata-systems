"""Phase 179 — risk ranking from categorical upstream signals (no financial math)."""

from __future__ import annotations

from typing import Any

from backend.executive_decision_intelligence.decision_prioritizer import dedupe_by_code


def build_risk_priorities(
    *,
    financial_summary: dict[str, Any] | None,
    operational: dict[str, Any] | None,
    brief_readiness: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    summary = financial_summary if isinstance(financial_summary, dict) else {}
    ops = operational if isinstance(operational, dict) else {}
    brief = brief_readiness if isinstance(brief_readiness, dict) else {}

    light = str(summary.get("profitability_traffic_light") or "NOT_AVAILABLE").upper()
    if light == "RED":
        items.append(
            {
                "code": "profitability_run_rate_red",
                "title": "Profitability run-rate is RED.",
                "reason": "Phase 178 traffic light indicates stressed required run-rate conditions.",
                "priority": "CRITICAL",
                "source": "phase178_traffic_light",
                "confidence": 0.9,
                "advisory_only": True,
                "trading_impact": False,
                "executable": False,
            }
        )
    elif light == "AMBER":
        items.append(
            {
                "code": "profitability_run_rate_amber",
                "title": "Profitability run-rate is AMBER.",
                "reason": "Target progress remains at risk per Phase 178 traffic light.",
                "priority": "HIGH",
                "source": "phase178_traffic_light",
                "confidence": 0.85,
                "advisory_only": True,
                "trading_impact": False,
                "executable": False,
            }
        )

    if summary.get("balance_sheet_balanced") is False:
        items.append(
            {
                "code": "unbalanced_balance_sheet",
                "title": "Balance sheet equation does not balance.",
                "reason": "Phase 178 summary flag balance_sheet_balanced=false.",
                "priority": "HIGH",
                "source": "phase178_summary",
                "confidence": 0.9,
                "advisory_only": True,
                "trading_impact": False,
                "executable": False,
            }
        )

    if summary.get("cash_flow_reconciled") is False:
        items.append(
            {
                "code": "cash_flow_unreconciled",
                "title": "Cash-flow reconciliation variance present.",
                "reason": "Phase 178 summary flag cash_flow_reconciled=false.",
                "priority": "HIGH",
                "source": "phase178_summary",
                "confidence": 0.9,
                "advisory_only": True,
                "trading_impact": False,
                "executable": False,
            }
        )

    risk_state = str(ops.get("risk_state") or "").upper()
    if risk_state in {"RED", "CRITICAL", "HIGH", "ELEVATED"}:
        items.append(
            {
                "code": "portfolio_risk_elevated",
                "title": "Portfolio / risk posture elevated.",
                "reason": f"Mission Control risk state={risk_state}.",
                "priority": "CRITICAL" if risk_state in {"RED", "CRITICAL"} else "HIGH",
                "source": "mission_control_risk",
                "confidence": 0.8,
                "advisory_only": True,
                "trading_impact": False,
                "executable": False,
            }
        )

    brief_state = str(brief.get("overall_state") or brief.get("state") or "").upper()
    if brief_state in {"RED", "NOT_READY"}:
        items.append(
            {
                "code": "executive_brief_not_ready",
                "title": "Executive brief readiness is blocked or red.",
                "reason": f"Phase 176J overall_state={brief_state}.",
                "priority": "HIGH",
                "source": "phase176j",
                "confidence": 0.85,
                "advisory_only": True,
                "trading_impact": False,
                "executable": False,
            }
        )

    if ops.get("broker_health") in {"RED", "BAD", "DOWN", "OFFLINE"}:
        items.append(
            {
                "code": "broker_health_degraded",
                "title": "Broker health signal is degraded.",
                "reason": "Mission Control platform broker_health is not healthy.",
                "priority": "HIGH",
                "source": "mission_control_platform",
                "confidence": 0.75,
                "advisory_only": True,
                "trading_impact": False,
                "executable": False,
            }
        )

    if not items:
        items.append(
            {
                "code": "no_material_risks_flagged",
                "title": "No material risk flags from available upstream signals.",
                "reason": "Categorical risk inputs did not raise escalations.",
                "priority": "INFO",
                "source": "edi",
                "confidence": 0.5,
                "advisory_only": True,
                "trading_impact": False,
                "executable": False,
            }
        )

    return dedupe_by_code(items)

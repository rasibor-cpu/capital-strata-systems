"""Phase 179 — executive priority extraction from Phase 178 management actions + ops signals."""

from __future__ import annotations

from typing import Any

from backend.executive_decision_intelligence.decision_prioritizer import (
    dedupe_by_code,
    map_action_priority,
)


def build_executive_priorities(
    *,
    management_actions: list[dict[str, Any]] | None,
    operational: dict[str, Any] | None,
    financial_summary: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """
    Convert advisory management actions and operational flags into executive priorities.
    Does not invent financial arithmetic — only categorical/state signals.
    """
    items: list[dict[str, Any]] = []
    summary = financial_summary if isinstance(financial_summary, dict) else {}
    ops = operational if isinstance(operational, dict) else {}

    for action in management_actions or []:
        if not isinstance(action, dict):
            continue
        code = str(action.get("code") or "").strip()
        if not code:
            continue
        items.append(
            {
                "code": f"fin_action:{code}",
                "title": str(action.get("action") or code),
                "reason": str(action.get("reason") or ""),
                "priority": map_action_priority(action.get("priority")),
                "source": "phase178_management_actions",
                "confidence": 0.85,
                "advisory_only": True,
                "trading_impact": False,
                "executable": False,
            }
        )

    ready = str(summary.get("reporting_readiness") or "").upper()
    if ready == "NOT_READY":
        items.append(
            {
                "code": "reporting_not_ready",
                "title": "Restore financial reporting readiness before executive distribution.",
                "reason": "Phase 177/178 reporting readiness is NOT_READY.",
                "priority": "CRITICAL",
                "source": "phase178_summary",
                "confidence": 0.9,
                "advisory_only": True,
                "trading_impact": False,
                "executable": False,
            }
        )

    if ops.get("runtime_offline"):
        items.append(
            {
                "code": "runtime_offline",
                "title": "Restore runtime evidence for Mission Control decision support.",
                "reason": "Platform/runtime evidence is offline.",
                "priority": "CRITICAL",
                "source": "mission_control_platform",
                "confidence": 0.95,
                "advisory_only": True,
                "trading_impact": False,
                "executable": False,
            }
        )

    alert_count = ops.get("alert_count")
    try:
        if alert_count is not None and int(alert_count) > 0:
            items.append(
                {
                    "code": "active_alerts",
                    "title": "Review active operational alerts.",
                    "reason": f"Mission Control reports {int(alert_count)} active alert(s).",
                    "priority": "HIGH" if int(alert_count) >= 3 else "MEDIUM",
                    "source": "mission_control_alerts",
                    "confidence": 0.8,
                    "advisory_only": True,
                    "trading_impact": False,
                    "executable": False,
                }
            )
    except (TypeError, ValueError):
        pass

    return dedupe_by_code(items)

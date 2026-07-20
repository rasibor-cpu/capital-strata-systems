"""Phase 179 — resource priority suggestions (non-allocating; advisory labels only)."""

from __future__ import annotations

from typing import Any

from backend.executive_decision_intelligence.decision_prioritizer import dedupe_by_code


def build_resource_priorities(
    *,
    priorities: list[dict[str, Any]] | None,
    risks: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    """
    Map top risks/priorities to advisory resource focus areas.
    Does not allocate capital, change portfolios, or schedule jobs.
    """
    items: list[dict[str, Any]] = []
    focus_map = {
        "reporting_not_ready": ("data_engineering", "Restore financial reporting inputs"),
        "runtime_offline": ("platform_operations", "Restore runtime evidence pipeline"),
        "active_alerts": ("operations", "Triage active alerts"),
        "profitability_run_rate_red": ("finance_review", "Executive review of run-rate posture"),
        "profitability_run_rate_amber": ("finance_review", "Monitor run-rate vs target"),
        "unbalanced_balance_sheet": ("finance_controls", "Investigate statement integrity"),
        "cash_flow_unreconciled": ("finance_controls", "Validate cash reconciliation"),
        "portfolio_risk_elevated": ("risk_oversight", "Elevate risk oversight cadence"),
        "executive_brief_not_ready": ("executive_ops", "Unblock executive brief readiness"),
        "broker_health_degraded": ("connectivity", "Validate broker connectivity health"),
        "missing_financial_feeds": ("data_engineering", "Validate financial source feeds"),
        "stale_financial_data": ("data_engineering", "Refresh financial source freshness"),
        "incomplete_statement_coverage": ("finance_controls", "Complete statement coverage"),
    }

    seen_focus: set[str] = set()
    for entry in list(risks or []) + list(priorities or []):
        if not isinstance(entry, dict):
            continue
        raw = str(entry.get("code") or "")
        code = raw.split("fin_action:")[-1]
        if code not in focus_map:
            continue
        focus, title = focus_map[code]
        if focus in seen_focus:
            continue
        seen_focus.add(focus)
        items.append(
            {
                "code": f"resource:{focus}",
                "title": title,
                "focus_area": focus,
                "priority": entry.get("priority") or "MEDIUM",
                "reason": f"Derived from upstream signal {code}.",
                "source": "edi_resource_allocator",
                "confidence": entry.get("confidence", 0.7),
                "advisory_only": True,
                "trading_impact": False,
                "executable": False,
            }
        )

    if not items:
        items.append(
            {
                "code": "resource:maintain_watch",
                "title": "Maintain standard executive watch cadence.",
                "focus_area": "executive_ops",
                "priority": "INFO",
                "reason": "No elevated resource redirection signals.",
                "source": "edi_resource_allocator",
                "confidence": 0.5,
                "advisory_only": True,
                "trading_impact": False,
                "executable": False,
            }
        )

    return dedupe_by_code(items)

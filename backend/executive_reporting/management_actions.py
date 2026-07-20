"""Phase 178 — advisory management actions (deterministic, non-executing)."""

from __future__ import annotations

from typing import Any


def generate_management_actions(
    *,
    summary: dict[str, Any],
    phase177_package: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """
    Priority-ordered advisory actions from explicit conditions.
    Never trading instructions. Never auto-executed.
    """
    _ = phase177_package
    actions: list[dict[str, Any]] = []
    light = str(summary.get("profitability_traffic_light") or "NOT_AVAILABLE")
    target = summary.get("target_profit")
    blockers = [str(b) for b in (summary.get("financial_blockers") or [])]
    warnings = [str(w) for w in (summary.get("financial_warnings") or [])]
    balanced = summary.get("balance_sheet_balanced")
    reconciled = summary.get("cash_flow_reconciled")
    cash_change = summary.get("net_change_in_cash")
    readiness = str(summary.get("reporting_readiness") or "NOT_READY")

    def add(priority: int, code: str, action: str, reason: str) -> None:
        actions.append(
            {
                "priority": priority,
                "code": code,
                "action": action,
                "reason": reason,
                "advisory_only": True,
                "trading_impact": False,
                "executable": False,
            }
        )

    if target is None:
        add(
            10,
            "missing_target_profit",
            "Configure an approved profitability target.",
            "Target profit is missing; run-rate and target progress cannot be evaluated.",
        )

    if light == "RED":
        add(
            20,
            "run_rate_stressed",
            "Review revenue strategy, direct costs, and operating expenses.",
            "Required daily run rate materially exceeds recent actual performance (RED).",
        )
    elif light == "AMBER":
        add(
            30,
            "run_rate_at_risk",
            "Monitor daily profit pace against the required run rate and review controllable costs.",
            "Target not yet achieved; required run rate remains within a recoverable band (AMBER).",
        )

    try:
        from decimal import Decimal

        if cash_change is not None and Decimal(str(cash_change)) < 0:
            add(
                40,
                "negative_cash_trend",
                "Review operating cash outflows and funding requirements.",
                f"Net change in cash is negative ({cash_change}).",
            )
    except Exception:
        pass

    if balanced is False:
        add(
            15,
            "unbalanced_balance_sheet",
            "Investigate missing or inconsistent asset, liability, or equity inputs.",
            "Balance sheet accounting equation does not balance.",
        )

    if reconciled is False:
        add(
            16,
            "cash_flow_unreconciled",
            "Validate opening cash, period cash movements, and reported closing cash.",
            "Cash-flow reconciliation variance is present.",
        )

    missing_feeds = any(
        "unavailable" in b.lower() or "missing" in b.lower() or "no financial" in b.lower()
        for b in blockers + warnings
    )
    if readiness == "NOT_READY" or missing_feeds:
        add(
            12,
            "missing_financial_feeds",
            "Connect or validate the relevant financial source system inputs.",
            "Financial reporting readiness is incomplete or blocked.",
        )

    # Stable priority sort then code for determinism
    actions.sort(key=lambda a: (int(a["priority"]), str(a["code"])))
    return actions

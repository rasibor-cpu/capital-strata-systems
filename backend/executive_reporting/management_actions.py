"""Phase 178 — advisory management actions (deterministic, non-executing)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _parse_freshness_age_seconds(
    freshness: Any,
    *,
    reference_time: Any = None,
) -> float | None:
    """Return age in seconds when freshness looks like an ISO timestamp; else None.

    Uses ``reference_time`` when provided (ISO string or datetime) so identical
    fixed inputs yield identical stale decisions. Falls back to UTC now only
    when no reference is available.
    """
    raw = freshness
    if raw is None:
        return None
    text = str(raw).strip()
    if not text or text.upper() in {"UNKNOWN", "UNAVAILABLE", "NONE"}:
        return None
    try:
        # Support trailing Z
        normalized = text.replace("Z", "+00:00")
        ts = datetime.fromisoformat(normalized)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)

        ref = datetime.now(timezone.utc)
        if reference_time is not None:
            if isinstance(reference_time, datetime):
                ref = reference_time
            else:
                ref_text = str(reference_time).strip().replace("Z", "+00:00")
                ref = datetime.fromisoformat(ref_text)
            if ref.tzinfo is None:
                ref = ref.replace(tzinfo=timezone.utc)
            ref = ref.astimezone(timezone.utc)

        return max(0.0, (ref - ts.astimezone(timezone.utc)).total_seconds())
    except Exception:
        return None


def generate_management_actions(
    *,
    summary: dict[str, Any],
    phase177_package: dict[str, Any] | None = None,
    stale_after_seconds: float = 86400.0,
) -> list[dict[str, Any]]:
    """
    Priority-ordered advisory actions from explicit conditions.
    Never trading instructions. Never auto-executed.
    Duplicate codes are suppressed (first occurrence wins; then priority sort).
    """
    pkg = phase177_package if isinstance(phase177_package, dict) else {}
    actions: list[dict[str, Any]] = []
    seen: set[str] = set()

    light = str(summary.get("profitability_traffic_light") or "NOT_AVAILABLE")
    target = summary.get("target_profit")
    blockers = [str(b) for b in (summary.get("financial_blockers") or [])]
    warnings = [str(w) for w in (summary.get("financial_warnings") or [])]
    balanced = summary.get("balance_sheet_balanced")
    reconciled = summary.get("cash_flow_reconciled")
    cash_change = summary.get("net_change_in_cash")
    readiness = str(summary.get("reporting_readiness") or "NOT_READY")

    def add(priority: int, code: str, action: str, reason: str) -> None:
        if code in seen:
            return
        seen.add(code)
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

    # Incomplete statement coverage (presentation-layer signal from Phase 177 outputs)
    income = pkg.get("income_statement") if isinstance(pkg.get("income_statement"), dict) else {}
    balance = pkg.get("balance_sheet") if isinstance(pkg.get("balance_sheet"), dict) else {}
    cash_flow = pkg.get("cash_flow_statement") if isinstance(pkg.get("cash_flow_statement"), dict) else {}
    incomplete = False
    if income and income.get("complete") is False:
        incomplete = True
    if balance and balance.get("complete") is False:
        incomplete = True
    if cash_flow and cash_flow.get("complete") is False:
        incomplete = True
    if summary.get("net_profit") is None and summary.get("total_assets") is None:
        incomplete = True
    if incomplete:
        add(
            18,
            "incomplete_statement_coverage",
            "Complete missing income-statement, balance-sheet, or cash-flow inputs before executive distribution.",
            "One or more financial statement sections are incomplete.",
        )

    # Stale financial data — age vs summary.generated_at when available (deterministic)
    freshness = summary.get("data_freshness")
    age = _parse_freshness_age_seconds(
        freshness,
        reference_time=summary.get("generated_at"),
    )
    stale_flag = any("stale" in w.lower() or "outdated" in w.lower() for w in warnings + blockers)
    if stale_flag or (age is not None and age > float(stale_after_seconds)):
        add(
            14,
            "stale_financial_data",
            "Refresh financial source feeds and regenerate the management report.",
            (
                f"Financial data freshness appears stale (age_seconds≈{int(age)})."
                if age is not None
                else "Financial warnings/blockers indicate stale or outdated data."
            ),
        )

    # Stable priority sort then code for determinism
    actions.sort(key=lambda a: (int(a["priority"]), str(a["code"])))
    return actions

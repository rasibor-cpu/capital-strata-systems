"""Phase 178 — deterministic executive narrative (facts only from Phase 177/178 summary)."""

from __future__ import annotations

from typing import Any


SCHEMA_VERSION = "css.executive_financial_narrative.v1"


def _money(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _pct(value: Any) -> str | None:
    if value is None:
        return None
    try:
        from decimal import Decimal

        # stored as ratio (e.g. 0.5000) — present as percent when |v| <= 2
        d = Decimal(str(value))
        if abs(d) <= 2:
            return f"{(d * 100).quantize(Decimal('0.01'))}%"
        return f"{d}%"
    except Exception:
        return str(value)


def _top_drivers(section: dict[str, Any] | None, *, limit: int = 3) -> list[tuple[str, str]]:
    if not isinstance(section, dict):
        return []
    scored: list[tuple[str, float, str]] = []
    for key, raw in section.items():
        if raw is None:
            continue
        try:
            from decimal import Decimal

            val = Decimal(str(raw))
            scored.append((key.replace("_", " "), float(abs(val)), format(val, "f")))
        except Exception:
            continue
    scored.sort(key=lambda t: (-t[1], t[0]))
    return [(name, amount) for name, _, amount in scored[:limit]]


def generate_executive_narrative(
    *,
    summary: dict[str, Any],
    phase177_package: dict[str, Any] | None = None,
    management_actions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Plain-language narrative. Every claim is grounded in provided summary/package data.
    Deterministic for identical inputs. No trading instructions or future promises.
    """
    pkg = phase177_package if isinstance(phase177_package, dict) else {}
    income = pkg.get("income_statement") if isinstance(pkg.get("income_statement"), dict) else {}
    revenue = income.get("revenue_and_gains") if isinstance(income.get("revenue_and_gains"), dict) else {}
    costs = income.get("trading_and_direct_costs") if isinstance(income.get("trading_and_direct_costs"), dict) else {}
    opex = income.get("operating_expenses") if isinstance(income.get("operating_expenses"), dict) else {}

    net = summary.get("net_profit")
    target = summary.get("target_profit")
    light = str(summary.get("profitability_traffic_light") or "NOT_AVAILABLE")
    readiness = str(summary.get("reporting_readiness") or "NOT_READY")
    cash_change = summary.get("net_change_in_cash")
    balanced = summary.get("balance_sheet_balanced")
    reconciled = summary.get("cash_flow_reconciled")
    period = summary.get("reporting_period") if isinstance(summary.get("reporting_period"), dict) else {}
    period_label = period.get("label") or "the reporting period"

    # --- Profitability ---
    if net is None:
        profitability = (
            f"Net profit for {period_label} is not available from current financial inputs."
        )
        profitable = None
    else:
        try:
            from decimal import Decimal

            n = Decimal(str(net))
            if n > 0:
                profitable = True
                profitability = f"The period is profitable, with net profit of {_money(net)}."
            elif n < 0:
                profitable = False
                profitability = f"The period shows a net loss of {_money(net)}."
            else:
                profitable = False
                profitability = f"Net profit for {period_label} is zero."
        except Exception:
            profitable = None
            profitability = f"Net profit is reported as {_money(net)}."

    # --- Target progress ---
    if target is None:
        target_progress = "No approved profitability target is configured for this period."
        ahead = None
    else:
        variance = summary.get("projected_target_variance")
        pct = _pct(summary.get("target_achieved_percentage"))
        req = summary.get("required_daily_run_rate")
        parts = [f"Target profit is {_money(target)}."]
        if pct:
            parts.append(f"Target achieved to date is {pct}.")
        if light == "GREEN":
            ahead = True
            parts.append("Performance is on track relative to the target (traffic light GREEN).")
        elif light == "AMBER":
            ahead = False
            parts.append("Performance is behind target but within a recoverable run-rate band (AMBER).")
        elif light == "RED":
            ahead = False
            parts.append("Required daily run rate materially exceeds recent actual pace (RED).")
        else:
            ahead = None
            parts.append("Target progress traffic light is NOT_AVAILABLE.")
        if req is not None:
            parts.append(f"Required daily run rate to reach target is {_money(req)}.")
        if variance is not None:
            parts.append(f"Projected period-end variance versus target is {_money(variance)}.")
        target_progress = " ".join(parts)

    # --- Revenue / cost drivers ---
    top_rev = _top_drivers(revenue)
    if top_rev:
        revenue_drivers = "Leading revenue and gain lines: " + "; ".join(
            f"{n} ({a})" for n, a in top_rev
        ) + "."
    else:
        revenue_drivers = "Revenue contributor detail is incomplete or unavailable."

    cost_pairs = _top_drivers(costs) + _top_drivers(opex)
    try:
        from decimal import Decimal

        cost_pairs = sorted(cost_pairs, key=lambda t: Decimal(str(t[1])), reverse=True)[:3]
    except Exception:
        cost_pairs = cost_pairs[:3]
    if cost_pairs:
        cost_drivers = "Leading cost and loss lines: " + "; ".join(
            f"{n} ({a})" for n, a in cost_pairs
        ) + "."
    else:
        cost_drivers = "Cost driver detail is incomplete or unavailable."

    # --- Cash ---
    if cash_change is None:
        cash_position = "Net change in cash is not available from the cash-flow statement."
    else:
        try:
            from decimal import Decimal

            c = Decimal(str(cash_change))
            if c > 0:
                cash_position = f"Cash increased over the period (net change {_money(cash_change)})."
            elif c < 0:
                cash_position = f"Cash decreased over the period (net change {_money(cash_change)})."
            else:
                cash_position = "Cash was unchanged over the period (net change 0)."
        except Exception:
            cash_position = f"Net change in cash is reported as {_money(cash_change)}."
    if summary.get("current_cash") is not None:
        cash_position += f" Reported closing / current cash is {_money(summary.get('current_cash'))}."

    # --- Balance sheet ---
    if balanced is True:
        balance_sheet_position = (
            f"Balance sheet totals: assets {_money(summary.get('total_assets'))}, "
            f"liabilities {_money(summary.get('total_liabilities'))}, "
            f"equity {_money(summary.get('total_equity'))}. The accounting equation balances."
        )
    elif balanced is False:
        balance_sheet_position = (
            "The balance sheet accounting equation does not balance. "
            "Asset, liability, or equity inputs require investigation."
        )
    else:
        balance_sheet_position = "Balance-sheet reconciliation status is unavailable (incomplete inputs)."

    if reconciled is True:
        balance_sheet_position += " Cash-flow statement reconciles to reported closing cash."
    elif reconciled is False:
        balance_sheet_position += " Cash-flow statement does not reconcile to reported closing cash."

    # --- Data quality ---
    blockers = list(summary.get("financial_blockers") or [])
    warnings = list(summary.get("financial_warnings") or [])
    dq_parts = [f"Financial reporting readiness is {readiness}."]
    if blockers:
        dq_parts.append("Blockers: " + "; ".join(str(b) for b in blockers[:6]) + ".")
    if warnings:
        dq_parts.append("Warnings: " + "; ".join(str(w) for w in warnings[:6]) + ".")
    if not blockers and not warnings:
        dq_parts.append("No explicit financial blockers or warnings were recorded.")
    data_quality = " ".join(dq_parts)

    # --- Actions ---
    actions = management_actions or []
    if actions:
        action_lines = [
            str(a.get("action") or a.get("title") or a)
            for a in actions[:8]
            if isinstance(a, dict) or True
        ]
        recommended = "Recommended management actions (advisory): " + "; ".join(
            str(x) for x in action_lines if x
        ) + "."
    else:
        recommended = "No prioritized management actions were generated from current conditions."

    # --- Conclusion ---
    if profitable is True and ahead is True:
        conclusion = (
            f"For {period_label}, results are profitable and on track versus the configured target."
        )
    elif profitable is True and ahead is False:
        conclusion = (
            f"For {period_label}, results are profitable but behind the configured profitability target."
        )
    elif profitable is False and net is not None:
        conclusion = f"For {period_label}, results show a loss or zero profit based on available inputs."
    elif net is None:
        conclusion = (
            f"Financial results for {period_label} cannot be concluded because net profit is unavailable."
        )
    else:
        conclusion = f"Financial results for {period_label} are summarized from available Phase 177 outputs."

    conclusion += (
        " This is an advisory management report, not an audited statutory financial statement."
    )

    sections = {
        "executive_conclusion": conclusion,
        "profitability": profitability,
        "target_progress": target_progress,
        "revenue_drivers": revenue_drivers,
        "cost_drivers": cost_drivers,
        "cash_position": cash_position,
        "balance_sheet_position": balance_sheet_position,
        "data_quality_issues": data_quality,
        "recommended_management_actions": recommended,
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "sections": sections,
        "plain_text": "\n\n".join(f"{k.replace('_', ' ').title()}\n{v}" for k, v in sections.items()),
        "advisory_only": True,
        "trading_impact": False,
        "facts_only": True,
    }

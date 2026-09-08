from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from math import isclose, isfinite
from typing import Any, Mapping, Sequence


_SOURCE = "QUESTRADE_ACTIVITIES"
_ACCOUNT_HISTORY = "ACCOUNT_HISTORY"

_NON_TRADE_CLASSES = {
    "DIVIDEND",
    "FEE",
    "TRANSFER",
    "INTEREST",
    "TAX",
    "OTHER",
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _upper(value: Any) -> str:
    return _text(value).upper()


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
        return number if isfinite(number) else None
    except (TypeError, ValueError, OverflowError):
        return None


def _calendar_date(value: Any) -> str | None:
    text = _text(value)
    if not text:
        return None

    # ISO dates produced by CSS/Questrade begin with YYYY-MM-DD.
    if len(text) >= 10:
        candidate = text[:10]
        try:
            datetime.strptime(candidate, "%Y-%m-%d")
            return candidate
        except ValueError:
            pass

    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.date().isoformat()


def _cash_flow_summary(
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, dict[str, float]]:
    totals: dict[str, dict[str, float]] = defaultdict(
        lambda: defaultdict(float)
    )

    for row in rows:
        currency = _upper(row.get("currency")) or "UNSPECIFIED"
        classification = _upper(row.get("classification")) or "OTHER"
        amount = _number(row.get("net_amount"))

        if amount is None:
            continue

        totals[currency][classification] += amount

    return {
        currency: {
            classification: round(amount, 8)
            for classification, amount in sorted(classes.items())
        }
        for currency, classes in sorted(totals.items())
    }


def _candidate_matches(
    activity: Mapping[str, Any],
    outcomes: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    symbol = _upper(activity.get("symbol"))
    activity_date = _calendar_date(
        activity.get("trade_date")
        or activity.get("transaction_date")
    )
    activity_quantity = _number(activity.get("quantity"))
    activity_price = _number(activity.get("price"))

    if (not symbol or activity_quantity in (None, 0)
            or activity_price is None or activity_price <= 0):
        return []

    matches: list[dict[str, Any]] = []

    for raw in outcomes:
        if not isinstance(raw, Mapping):
            continue

        if _upper(raw.get("broker")) != "QUESTRADE":
            continue

        if _upper(raw.get("symbol")) != symbol:
            continue

        if not _text(raw.get("trade_id")):
            continue
        currency = _upper(activity.get("currency"))
        outcome_currency = _upper(raw.get("currency"))
        action = _upper(activity.get("action"))
        close_action = _upper(raw.get("close_action"))
        if currency and outcome_currency and currency != outcome_currency:
            continue
        if action in {"BTO", "STO"}:
            continue
        if action and close_action and action != close_action:
            continue
        limitations = []
        if not currency or not outcome_currency:
            limitations.append("currency_unverified")
        if action not in {"BUY", "SELL", "BTC", "STC"} or not close_action:
            limitations.append("close_action_unverified")

        close_date = _calendar_date(raw.get("timestamp_close"))
        quantity = _number(raw.get("quantity"))
        exit_price = _number(raw.get("exit_price"))

        checks = {
            "symbol": True,
            "close_date": (
                activity_date is not None
                and close_date is not None
                and activity_date == close_date
            ),
            "quantity": (
                activity_quantity is not None
                and quantity is not None
                and isclose(
                    abs(activity_quantity),
                    abs(quantity),
                    rel_tol=1e-9,
                    abs_tol=1e-9,
                )
            ),
            "exit_price": (
                activity_price is not None
                and exit_price is not None
                and isclose(
                    activity_price,
                    exit_price,
                    rel_tol=1e-6,
                    abs_tol=1e-6,
                )
            ),
        }

        # QT-005 does not have a stable Questrade activity/fill identifier.
        # Corroboration therefore requires all available economic/date fields.
        if all(checks.values()):
            matches.append(
                {
                    "trade_id": _text(raw.get("trade_id")),
                    "symbol": symbol,
                    "timestamp_close": raw.get("timestamp_close"),
                    "quantity": quantity,
                    "exit_price": exit_price,
                    "limitations": limitations,
                    "broker": "QUESTRADE",
                    "match_basis": [
                        "symbol",
                        "close_date",
                        "quantity",
                        "exit_price",
                    ],
                }
            )

    return matches


def reconcile_questrade_activity_history(
    activity_presentation: Mapping[str, Any] | None,
    trade_outcomes: Sequence[Mapping[str, Any]] | None,
    *,
    outcome_source_available: bool = True,
) -> dict[str, Any]:
    """
    Read-only corroboration of Questrade ACCOUNT_HISTORY against CSS outcomes.

    This function:
    - does not call a broker;
    - does not create, modify, or close positions;
    - does not write TradeOutcomeRepository;
    - does not synthesize realized/session P&L;
    - does not represent a real-time fill feed;
    - does not grant execution authority.

    Because the current Questrade activity contract exposes no stable activity
    identifier, exact economic/date matches are labelled CORROBORATED rather
    than authoritative/reconciled fills.
    """

    presentation = (
        dict(activity_presentation)
        if isinstance(activity_presentation, Mapping)
        else {}
    )

    rows = presentation.get("rows")
    if not isinstance(rows, list):
        rows = []

    outcomes = [
        dict(item)
        for item in (trade_outcomes or [])
        if isinstance(item, Mapping)
    ]

    source_status = _upper(presentation.get("status"))
    if source_status != "AVAILABLE":
        rows = []
    result_rows: list[dict[str, Any]] = []

    counts = {
        "CORROBORATED": 0,
        "AMBIGUOUS": 0,
        "UNMATCHED": 0,
        "NOT_APPLICABLE": 0,
    }

    for raw in rows:
        if not isinstance(raw, Mapping):
            continue

        row = dict(raw)
        classification = _upper(row.get("classification")) or "OTHER"

        if classification != "TRADE":
            status = "NOT_APPLICABLE"
            candidates: list[dict[str, Any]] = []
            reason = (
                "non_trade_account_history"
                if classification in _NON_TRADE_CLASSES
                else "not_trade_activity"
            )
        else:
            candidates = _candidate_matches(row, outcomes) if outcome_source_available else []

            if len(candidates) == 1 and not candidates[0]["limitations"]:
                status = "CORROBORATED"
                reason = "single_exact_economic_date_candidate"
            elif candidates:
                status = "AMBIGUOUS"
                reason = ("multiple_exact_economic_date_candidates" if len(candidates) > 1
                          else "candidate_has_unverified_currency_or_close_action")
            else:
                status = "UNMATCHED"
                reason = "no_exact_economic_date_candidate"

        counts[status] += 1

        result_rows.append(
            {
                **row,
                "reconciliation_status": status,
                "reconciliation_reason": reason,
                "candidate_count": len(candidates),
                "matched_trade_id": (
                    candidates[0]["trade_id"]
                    if status == "CORROBORATED"
                    else None
                ),
                "candidates": candidates,
            }
        )

    # A single CSS outcome cannot independently corroborate several history rows.
    candidate_uses: dict[str, int] = defaultdict(int)
    for row in result_rows:
        for candidate in row["candidates"]:
            candidate_uses[candidate["trade_id"]] += 1
    for row in result_rows:
        if row["reconciliation_status"] == "CORROBORATED" and any(
            candidate_uses[c["trade_id"]] > 1 for c in row["candidates"]
        ):
            counts["CORROBORATED"] -= 1
            counts["AMBIGUOUS"] += 1
            row.update(reconciliation_status="AMBIGUOUS",
                       reconciliation_reason="outcome_shared_by_activity_rows",
                       matched_trade_id=None)

    trade_rows = sum(
        1
        for row in result_rows
        if _upper(row.get("classification")) == "TRADE"
    )

    status = (
        "AVAILABLE"
        if source_status == "AVAILABLE" and outcome_source_available
        else "UNAVAILABLE"
    )

    return {
        "status": status,
        "source": _SOURCE,
        "provenance": "QUESTRADE_ACTIVITIES|CSS_TRADE_OUTCOME_READ_ONLY",
        "telemetry_semantics": _ACCOUNT_HISTORY,
        "reconciliation_semantics": "CORROBORATION_ONLY",
        "stable_broker_activity_id_available": False,
        "outcome_source_status": "AVAILABLE" if outcome_source_available else "UNAVAILABLE",
        "cash_flow_semantics": {
            "TRADE": "TRADE_CONSIDERATION_NOT_REALIZED_PNL",
            "DIVIDEND": "INVESTMENT_INCOME", "INTEREST": "FINANCING_OR_INVESTMENT_CASH_FLOW",
            "FEE": "COST", "TAX": "TAX_CASH_FLOW_OR_COST",
            "TRANSFER": "CAPITAL_MOVEMENT", "OTHER": "UNCLASSIFIED_CASH_FLOW",
        },
        "activity_count": len(result_rows),
        "trade_activity_count": trade_rows,
        "classification_counts": {classification: sum(
            (_upper(row.get("classification")) or "OTHER") == classification
            for row in result_rows
        ) for classification in sorted({_upper(row.get("classification")) or "OTHER" for row in result_rows})},
        "reconciliation_counts": counts,
        "cash_flow_by_currency_and_classification": _cash_flow_summary(
            result_rows
        ),
        "rows": result_rows,
        "real_time_fill_feed": False,
        "portfolio_mutation_authority": False,
        "trade_outcome_write_authority": False,
        "pnl_promotion_authority": False,
        "execution_authority": False,
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "advisory_only": True,
        "reason": (
            None
            if status == "AVAILABLE"
            else "css_trade_outcomes_unavailable" if not outcome_source_available
            else presentation.get("reason")
            or "questrade_activity_history_unavailable"
        ),
    }

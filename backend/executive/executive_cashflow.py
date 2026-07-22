"""Canonical Executive Cash Flow Statement builder."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .executive_models import FinancialStatement, StatementLine


def build_cashflow_statement(
    snapshot: Mapping[str, Any] | None,
    *,
    period_start: str,
    period_end: str,
    currency: str = "CAD",
) -> FinancialStatement:
    source = dict(snapshot or {})
    operating = _number(source.get("operating_cash_flow"))
    investing = _number(source.get("investing_cash_flow"))
    financing = _number(source.get("financing_cash_flow"))
    opening_cash = _number(source.get("opening_cash"))
    net_change = operating + investing + financing
    closing_cash = _number(source.get("closing_cash", opening_cash + net_change))
    lines = (
        StatementLine("operating_cash_flow", "Operating Cash Flow", operating, "OPERATING", True),
        StatementLine("investing_cash_flow", "Investing Cash Flow", investing, "INVESTING", True),
        StatementLine("financing_cash_flow", "Financing Cash Flow", financing, "FINANCING", True),
        StatementLine("net_cash_change", "Net Change in Cash", net_change, "NET", True),
        StatementLine("opening_cash", "Opening Cash", opening_cash, "CASH"),
        StatementLine("closing_cash", "Closing Cash", closing_cash, "CASH", True),
    )
    return FinancialStatement(
        statement_type="CASH_FLOW_STATEMENT",
        currency=currency,
        period_start=period_start,
        period_end=period_end,
        lines=lines,
        balanced=abs((opening_cash + net_change) - closing_cash) <= 0.01,
    )


def _number(value: Any) -> float:
    try:
        return round(float(value if value not in (None, "") else 0.0), 2)
    except (TypeError, ValueError):
        return 0.0


__all__ = ["build_cashflow_statement"]

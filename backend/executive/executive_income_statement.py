"""Canonical Executive Income Statement builder."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .executive_models import FinancialStatement, StatementLine


def build_income_statement(
    snapshot: Mapping[str, Any] | None,
    *,
    period_start: str,
    period_end: str,
    currency: str = "CAD",
) -> FinancialStatement:
    source = dict(snapshot or {})
    revenue = _number(source.get("revenue"))
    cost = _number(source.get("cost_of_revenue", source.get("cost_of_goods_sold")))
    operating_expenses = _number(source.get("operating_expenses"))
    taxes = _number(source.get("taxes"))
    gross_profit = revenue - cost
    operating_profit = gross_profit - operating_expenses
    net_profit = _number(source.get("net_profit", operating_profit - taxes))
    lines = (
        StatementLine("revenue", "Revenue", revenue, "REVENUE"),
        StatementLine("cost_of_revenue", "Cost of Revenue", -cost, "COST"),
        StatementLine("gross_profit", "Gross Profit", gross_profit, "PROFIT", True),
        StatementLine("operating_expenses", "Operating Expenses", -operating_expenses, "EXPENSE"),
        StatementLine("operating_profit", "Operating Profit", operating_profit, "PROFIT", True),
        StatementLine("taxes", "Taxes", -taxes, "EXPENSE"),
        StatementLine("net_profit", "Net Profit", net_profit, "PROFIT", True),
    )
    return FinancialStatement(
        statement_type="INCOME_STATEMENT",
        currency=currency,
        period_start=period_start,
        period_end=period_end,
        lines=lines,
    )


def _number(value: Any) -> float:
    try:
        return round(float(value if value not in (None, "") else 0.0), 2)
    except (TypeError, ValueError):
        return 0.0


__all__ = ["build_income_statement"]

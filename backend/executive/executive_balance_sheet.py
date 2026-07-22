"""Canonical Executive Balance Sheet builder."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .executive_models import FinancialStatement, StatementLine


def build_balance_sheet(
    snapshot: Mapping[str, Any] | None,
    *,
    as_of: str,
    currency: str = "CAD",
) -> FinancialStatement:
    source = dict(snapshot or {})
    cash = _number(source.get("cash", source.get("available_cash")))
    investments = _number(source.get("investments", source.get("portfolio_equity")))
    receivables = _number(source.get("receivables"))
    other_assets = _number(source.get("other_assets"))
    liabilities = _number(source.get("liabilities"))
    total_assets = cash + investments + receivables + other_assets
    equity = _optional_number(source.get("shareholders_equity"))
    if equity is None:
        equity = total_assets - liabilities
    balanced = abs(total_assets - (liabilities + equity)) <= 0.01
    lines = (
        StatementLine("cash", "Cash and Cash Equivalents", cash, "ASSET"),
        StatementLine("investments", "Investments", investments, "ASSET"),
        StatementLine("receivables", "Receivables", receivables, "ASSET"),
        StatementLine("other_assets", "Other Assets", other_assets, "ASSET"),
        StatementLine("total_assets", "Total Assets", total_assets, "ASSET", True),
        StatementLine("liabilities", "Total Liabilities", liabilities, "LIABILITY", True),
        StatementLine("shareholders_equity", "Shareholders' Equity", equity, "EQUITY", True),
        StatementLine(
            "liabilities_and_equity",
            "Total Liabilities and Equity",
            liabilities + equity,
            "BALANCE",
            True,
        ),
    )
    return FinancialStatement(
        statement_type="BALANCE_SHEET",
        currency=currency,
        period_start=as_of,
        period_end=as_of,
        lines=lines,
        balanced=balanced,
    )


def _number(value: Any) -> float:
    try:
        return round(float(value if value not in (None, "") else 0.0), 2)
    except (TypeError, ValueError):
        return 0.0


def _optional_number(value: Any) -> float | None:
    return None if value in (None, "") else _number(value)


__all__ = ["build_balance_sheet"]

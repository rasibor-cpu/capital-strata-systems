"""Phase 177 — canonical income statement (Decimal, explicit signs)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from backend.financial_reporting.data_contracts import FinancialDataContract
from backend.financial_reporting.models import FinancialAmount, money, ratio, serialize_decimal


@dataclass(frozen=True)
class IncomeStatement:
    currency: str
    realized_gains: Decimal | None
    unrealized_gains: Decimal | None
    interest: Decimal | None
    dividends: Decimal | None
    options_premium: Decimal | None
    fx_income: Decimal | None
    treasury_income: Decimal | None
    other_income: Decimal | None
    realized_losses: Decimal | None
    unrealized_losses: Decimal | None
    commissions: Decimal | None
    exchange_fees: Decimal | None
    financing_costs: Decimal | None
    market_data_costs: Decimal | None
    technology: Decimal | None
    personnel: Decimal | None
    professional_fees: Decimal | None
    administrative: Decimal | None
    other_operating_expenses: Decimal | None
    tax: Decimal | None
    gross_trading_income: Decimal | None
    net_trading_income: Decimal | None
    total_revenue: Decimal | None
    total_direct_costs: Decimal | None
    gross_profit: Decimal | None
    total_operating_expenses: Decimal | None
    operating_profit: Decimal | None
    profit_before_tax: Decimal | None
    net_profit: Decimal | None
    profit_margin: Decimal | None
    complete: bool
    missing_fields: tuple[str, ...]
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        def s(v: Decimal | None) -> str | None:
            return serialize_decimal(v)

        return {
            "currency": self.currency,
            "revenue_and_gains": {
                "realized_gains": s(self.realized_gains),
                "unrealized_gains": s(self.unrealized_gains),
                "interest": s(self.interest),
                "dividends": s(self.dividends),
                "options_premium": s(self.options_premium),
                "fx_income": s(self.fx_income),
                "treasury_income": s(self.treasury_income),
                "other_income": s(self.other_income),
            },
            "trading_and_direct_costs": {
                "realized_losses": s(self.realized_losses),
                "unrealized_losses": s(self.unrealized_losses),
                "commissions": s(self.commissions),
                "exchange_fees": s(self.exchange_fees),
                "financing_costs": s(self.financing_costs),
                "market_data_costs": s(self.market_data_costs),
            },
            "operating_expenses": {
                "technology": s(self.technology),
                "personnel": s(self.personnel),
                "professional_fees": s(self.professional_fees),
                "administrative": s(self.administrative),
                "other_operating_expenses": s(self.other_operating_expenses),
            },
            "totals": {
                "gross_trading_income": s(self.gross_trading_income),
                "net_trading_income": s(self.net_trading_income),
                "total_revenue": s(self.total_revenue),
                "total_direct_costs": s(self.total_direct_costs),
                "gross_profit": s(self.gross_profit),
                "total_operating_expenses": s(self.total_operating_expenses),
                "operating_profit": s(self.operating_profit),
                "profit_before_tax": s(self.profit_before_tax),
                "tax": s(self.tax),
                "net_profit": s(self.net_profit),
                "profit_margin": s(self.profit_margin),
            },
            "complete": self.complete,
            "missing_fields": list(self.missing_fields),
            "warnings": list(self.warnings),
            "sign_convention": {
                "gains_and_income": "positive increases profit",
                "losses_and_costs": "positive magnitudes reduce profit (not double-counted as negative gains)",
                "tax": "positive tax reduces net profit",
            },
        }


def _v(amt: FinancialAmount) -> Decimal | None:
    return amt.for_total()


def generate_income_statement(contract: FinancialDataContract) -> IncomeStatement:
    warnings: list[str] = []
    missing: list[str] = []

    def take(name: str, amt: FinancialAmount) -> Decimal | None:
        val = _v(amt)
        if val is None:
            missing.append(name)
        return val

    realized_gains = take("realized_trading_gains", contract.realized_trading_gains)
    unrealized_gains = take("unrealized_gains", contract.unrealized_gains)
    interest = take("interest_income", contract.interest_income)
    dividends = take("dividend_income", contract.dividend_income)
    options_premium = take("option_premium_income", contract.option_premium_income)
    fx_income = take("fx_gains", contract.fx_gains)
    treasury_income = take("treasury_income", contract.treasury_income)
    other_income = take("other_operating_income", contract.other_operating_income)

    realized_losses = take("realized_trading_losses", contract.realized_trading_losses)
    unrealized_losses = take("unrealized_losses", contract.unrealized_losses)
    commissions = take("broker_commissions", contract.broker_commissions)
    exchange_fees = take("exchange_fees", contract.exchange_fees)
    financing_costs = take("financing_costs", contract.financing_costs)
    # borrowing_costs roll into financing for statement presentation when present
    borrowing = _v(contract.borrowing_costs)
    if borrowing is not None:
        financing_costs = money((financing_costs or Decimal("0")) + borrowing)
    elif not contract.borrowing_costs.present:
        missing.append("borrowing_costs")
    market_data_costs = take("market_data_costs", contract.market_data_costs)

    technology = take("technology_costs", contract.technology_costs)
    personnel = take("personnel_expenses", contract.personnel_expenses)
    professional_fees = take("professional_fees", contract.professional_fees)
    administrative = take("administrative_costs", contract.administrative_costs)
    other_opex = take("operating_expenses", contract.operating_expenses)
    other_expenses = _v(contract.other_expenses)
    if other_expenses is not None:
        other_opex = money((other_opex or Decimal("0")) + other_expenses)
    elif not contract.other_expenses.present:
        missing.append("other_expenses")
    tax = take("taxes", contract.taxes)

    # Guard: do not double-count negative gains as losses
    if realized_gains is not None and realized_gains < 0:
        warnings.append("realized_trading_gains is negative; treat as gain line only (losses use realized_trading_losses)")
    if unrealized_gains is not None and unrealized_gains < 0:
        warnings.append("unrealized_gains is negative; losses should use unrealized_losses")

    def add_optional(*vals: Decimal | None) -> Decimal | None:
        if all(v is None for v in vals):
            return None
        return money(sum((v or Decimal("0")) for v in vals))

    gross_trading_income = add_optional(realized_gains, unrealized_gains)
    total_revenue = add_optional(
        realized_gains,
        unrealized_gains,
        interest,
        dividends,
        options_premium,
        fx_income,
        treasury_income,
        other_income,
    )
    total_direct_costs = add_optional(
        realized_losses,
        unrealized_losses,
        commissions,
        exchange_fees,
        financing_costs,
        market_data_costs,
    )
    net_trading_income = None
    if gross_trading_income is not None or total_direct_costs is not None:
        net_trading_income = money(
            (gross_trading_income or Decimal("0")) - (total_direct_costs or Decimal("0"))
        )
    gross_profit = None
    if total_revenue is not None or total_direct_costs is not None:
        gross_profit = money((total_revenue or Decimal("0")) - (total_direct_costs or Decimal("0")))

    total_operating_expenses = add_optional(
        technology, personnel, professional_fees, administrative, other_opex
    )
    operating_profit = None
    if gross_profit is not None or total_operating_expenses is not None:
        operating_profit = money(
            (gross_profit or Decimal("0")) - (total_operating_expenses or Decimal("0"))
        )
    profit_before_tax = operating_profit
    net_profit = None
    if profit_before_tax is not None or tax is not None:
        net_profit = money((profit_before_tax or Decimal("0")) - (tax or Decimal("0")))

    profit_margin = None
    if net_profit is not None and total_revenue is not None and total_revenue != 0:
        profit_margin = ratio(net_profit / total_revenue)

    # Completeness: core P&L usable when net_profit computable from at least revenue or costs
    complete = net_profit is not None and not (
        total_revenue is None and total_direct_costs is None and total_operating_expenses is None
    )

    return IncomeStatement(
        currency=contract.currency,
        realized_gains=realized_gains,
        unrealized_gains=unrealized_gains,
        interest=interest,
        dividends=dividends,
        options_premium=options_premium,
        fx_income=fx_income,
        treasury_income=treasury_income,
        other_income=other_income,
        realized_losses=realized_losses,
        unrealized_losses=unrealized_losses,
        commissions=commissions,
        exchange_fees=exchange_fees,
        financing_costs=financing_costs,
        market_data_costs=market_data_costs,
        technology=technology,
        personnel=personnel,
        professional_fees=professional_fees,
        administrative=administrative,
        other_operating_expenses=other_opex,
        tax=tax,
        gross_trading_income=gross_trading_income,
        net_trading_income=net_trading_income,
        total_revenue=total_revenue,
        total_direct_costs=total_direct_costs,
        gross_profit=gross_profit,
        total_operating_expenses=total_operating_expenses,
        operating_profit=operating_profit,
        profit_before_tax=profit_before_tax,
        net_profit=net_profit,
        profit_margin=profit_margin,
        complete=complete,
        missing_fields=tuple(sorted(set(missing))),
        warnings=tuple(warnings),
    )

"""Phase 177 — canonical balance sheet (does not force-balance)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from backend.financial_reporting.data_contracts import FinancialDataContract
from backend.financial_reporting.models import FinancialAmount, money, serialize_decimal


@dataclass(frozen=True)
class BalanceSheet:
    currency: str
    cash_and_equivalents: Decimal | None
    broker_cash: Decimal | None
    receivables: Decimal | None
    investments: Decimal | None
    derivative_assets: Decimal | None
    other_assets: Decimal | None
    total_assets: Decimal | None
    payables: Decimal | None
    margin_liabilities: Decimal | None
    financing_liabilities: Decimal | None
    derivative_liabilities: Decimal | None
    tax_liabilities: Decimal | None
    other_liabilities: Decimal | None
    total_liabilities: Decimal | None
    contributed_capital: Decimal | None
    retained_earnings: Decimal | None
    current_period_earnings: Decimal | None
    aoci: Decimal | None
    total_equity: Decimal | None
    liabilities_plus_equity: Decimal | None
    accounting_equation_variance: Decimal | None
    balanced: bool | None
    complete: bool
    missing_fields: tuple[str, ...]
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        s = serialize_decimal
        return {
            "currency": self.currency,
            "assets": {
                "cash_and_equivalents": s(self.cash_and_equivalents),
                "broker_cash": s(self.broker_cash),
                "receivables": s(self.receivables),
                "investments": s(self.investments),
                "derivative_assets": s(self.derivative_assets),
                "other_assets": s(self.other_assets),
                "total_assets": s(self.total_assets),
            },
            "liabilities": {
                "payables": s(self.payables),
                "margin_liabilities": s(self.margin_liabilities),
                "financing_liabilities": s(self.financing_liabilities),
                "derivative_liabilities": s(self.derivative_liabilities),
                "tax_liabilities": s(self.tax_liabilities),
                "other_liabilities": s(self.other_liabilities),
                "total_liabilities": s(self.total_liabilities),
            },
            "equity": {
                "contributed_capital": s(self.contributed_capital),
                "retained_earnings": s(self.retained_earnings),
                "current_period_earnings": s(self.current_period_earnings),
                "aoci": s(self.aoci),
                "total_equity": s(self.total_equity),
            },
            "liabilities_plus_equity": s(self.liabilities_plus_equity),
            "accounting_equation_variance": s(self.accounting_equation_variance),
            "balanced": self.balanced,
            "complete": self.complete,
            "missing_fields": list(self.missing_fields),
            "warnings": list(self.warnings),
        }


def _v(amt: FinancialAmount) -> Decimal | None:
    return amt.for_total()


def generate_balance_sheet(contract: FinancialDataContract) -> BalanceSheet:
    missing: list[str] = []
    warnings: list[str] = []

    def take(name: str, amt: FinancialAmount) -> Decimal | None:
        val = _v(amt)
        if val is None and amt.reason.value != "not_applicable":
            missing.append(name)
        return val

    cash = take("cash", contract.cash)
    broker_cash = take("broker_cash", contract.broker_cash)
    receivables = take("receivables", contract.receivables)
    investments = take("investments_fair_value", contract.investments_fair_value)
    derivative_assets = take("derivative_assets", contract.derivative_assets)
    other_assets = take("other_assets", contract.other_assets)

    payables = take("payables", contract.payables)
    margin = take("margin_liabilities", contract.margin_liabilities)
    financing = take("financing_liabilities", contract.financing_liabilities)
    der_liab = take("derivative_liabilities", contract.derivative_liabilities)
    tax_liab = take("tax_liabilities", contract.tax_liabilities)
    other_liab = take("other_liabilities", contract.other_liabilities)

    contributed = take("contributed_capital", contract.contributed_capital)
    retained = take("retained_earnings", contract.retained_earnings)
    cpe = take("current_period_earnings", contract.current_period_earnings)
    aoci = _v(contract.aoci)

    def total(*vals: Decimal | None) -> Decimal | None:
        if all(v is None for v in vals):
            return None
        return money(sum((v or Decimal("0")) for v in vals))

    cash_and_eq = total(cash, broker_cash)
    total_assets = total(cash_and_eq, receivables, investments, derivative_assets, other_assets)
    total_liab = total(payables, margin, financing, der_liab, tax_liab, other_liab)
    total_equity = total(contributed, retained, cpe, aoci)

    l_plus_e = None
    if total_liab is not None or total_equity is not None:
        l_plus_e = money((total_liab or Decimal("0")) + (total_equity or Decimal("0")))

    variance = None
    balanced: bool | None = None
    if total_assets is not None and l_plus_e is not None:
        variance = money(total_assets - l_plus_e)
        balanced = variance == money(0)
        if not balanced:
            warnings.append(
                f"accounting equation does not balance; variance={format(variance, 'f')}"
            )

    complete = total_assets is not None and total_liab is not None and total_equity is not None

    return BalanceSheet(
        currency=contract.currency,
        cash_and_equivalents=cash_and_eq,
        broker_cash=broker_cash,
        receivables=receivables,
        investments=investments,
        derivative_assets=derivative_assets,
        other_assets=other_assets,
        total_assets=total_assets,
        payables=payables,
        margin_liabilities=margin,
        financing_liabilities=financing,
        derivative_liabilities=der_liab,
        tax_liabilities=tax_liab,
        other_liabilities=other_liab,
        total_liabilities=total_liab,
        contributed_capital=contributed,
        retained_earnings=retained,
        current_period_earnings=cpe,
        aoci=aoci,
        total_equity=total_equity,
        liabilities_plus_equity=l_plus_e,
        accounting_equation_variance=variance,
        balanced=balanced,
        complete=complete,
        missing_fields=tuple(sorted(set(missing))),
        warnings=tuple(warnings),
    )

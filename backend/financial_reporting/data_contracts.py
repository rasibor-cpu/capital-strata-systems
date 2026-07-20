"""Phase 177 — stable financial data contract (inputs only; read-only)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from backend.financial_reporting.models import FinancialAmount, MissingReason
from backend.financial_reporting.periods import ReportingPeriod


def _amt(value: Any) -> FinancialAmount:
    if isinstance(value, FinancialAmount):
        return value
    if value is None:
        return FinancialAmount.missing(MissingReason.MISSING)
    return FinancialAmount.of(value)


@dataclass
class FinancialDataContract:
    """Canonical input contract. Missing fields stay missing — never silent healthy zeros."""

    currency: str = "USD"
    reporting_period: ReportingPeriod | None = None
    as_of: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    source_system: str = "css.financial_reporting"
    data_freshness: str | None = None
    data_completeness: str | None = None
    evidence_references: list[str] = field(default_factory=list)
    advisory_only: bool = True

    # Revenue / gains
    realized_trading_gains: FinancialAmount = field(default_factory=lambda: FinancialAmount.missing())
    unrealized_gains: FinancialAmount = field(default_factory=lambda: FinancialAmount.missing())
    interest_income: FinancialAmount = field(default_factory=lambda: FinancialAmount.missing())
    dividend_income: FinancialAmount = field(default_factory=lambda: FinancialAmount.missing())
    option_premium_income: FinancialAmount = field(default_factory=lambda: FinancialAmount.missing())
    fx_gains: FinancialAmount = field(default_factory=lambda: FinancialAmount.missing())
    treasury_income: FinancialAmount = field(default_factory=lambda: FinancialAmount.missing())
    other_operating_income: FinancialAmount = field(default_factory=lambda: FinancialAmount.missing())

    # Costs / losses (positive magnitudes unless noted)
    realized_trading_losses: FinancialAmount = field(default_factory=lambda: FinancialAmount.missing())
    unrealized_losses: FinancialAmount = field(default_factory=lambda: FinancialAmount.missing())
    broker_commissions: FinancialAmount = field(default_factory=lambda: FinancialAmount.missing())
    exchange_fees: FinancialAmount = field(default_factory=lambda: FinancialAmount.missing())
    financing_costs: FinancialAmount = field(default_factory=lambda: FinancialAmount.missing())
    borrowing_costs: FinancialAmount = field(default_factory=lambda: FinancialAmount.missing())
    market_data_costs: FinancialAmount = field(default_factory=lambda: FinancialAmount.missing())
    technology_costs: FinancialAmount = field(default_factory=lambda: FinancialAmount.missing())
    operating_expenses: FinancialAmount = field(default_factory=lambda: FinancialAmount.missing())
    personnel_expenses: FinancialAmount = field(default_factory=lambda: FinancialAmount.missing())
    professional_fees: FinancialAmount = field(default_factory=lambda: FinancialAmount.missing())
    administrative_costs: FinancialAmount = field(default_factory=lambda: FinancialAmount.missing())
    taxes: FinancialAmount = field(default_factory=lambda: FinancialAmount.missing())
    other_expenses: FinancialAmount = field(default_factory=lambda: FinancialAmount.missing())

    # Balance sheet
    cash: FinancialAmount = field(default_factory=lambda: FinancialAmount.missing())
    broker_cash: FinancialAmount = field(default_factory=lambda: FinancialAmount.missing())
    receivables: FinancialAmount = field(default_factory=lambda: FinancialAmount.missing())
    investments_fair_value: FinancialAmount = field(default_factory=lambda: FinancialAmount.missing())
    derivative_assets: FinancialAmount = field(default_factory=lambda: FinancialAmount.missing())
    other_assets: FinancialAmount = field(default_factory=lambda: FinancialAmount.missing())
    payables: FinancialAmount = field(default_factory=lambda: FinancialAmount.missing())
    margin_liabilities: FinancialAmount = field(default_factory=lambda: FinancialAmount.missing())
    financing_liabilities: FinancialAmount = field(default_factory=lambda: FinancialAmount.missing())
    derivative_liabilities: FinancialAmount = field(default_factory=lambda: FinancialAmount.missing())
    tax_liabilities: FinancialAmount = field(default_factory=lambda: FinancialAmount.missing())
    other_liabilities: FinancialAmount = field(default_factory=lambda: FinancialAmount.missing())
    contributed_capital: FinancialAmount = field(default_factory=lambda: FinancialAmount.missing())
    retained_earnings: FinancialAmount = field(default_factory=lambda: FinancialAmount.missing())
    current_period_earnings: FinancialAmount = field(default_factory=lambda: FinancialAmount.missing())
    aoci: FinancialAmount = field(
        default_factory=lambda: FinancialAmount.missing(MissingReason.NOT_APPLICABLE)
    )

    # Cash flow
    operating_cash_inflows: FinancialAmount = field(default_factory=lambda: FinancialAmount.missing())
    operating_cash_outflows: FinancialAmount = field(default_factory=lambda: FinancialAmount.missing())
    investing_cash_inflows: FinancialAmount = field(default_factory=lambda: FinancialAmount.missing())
    investing_cash_outflows: FinancialAmount = field(default_factory=lambda: FinancialAmount.missing())
    financing_cash_inflows: FinancialAmount = field(default_factory=lambda: FinancialAmount.missing())
    financing_cash_outflows: FinancialAmount = field(default_factory=lambda: FinancialAmount.missing())
    opening_cash: FinancialAmount = field(default_factory=lambda: FinancialAmount.missing())
    closing_cash: FinancialAmount = field(default_factory=lambda: FinancialAmount.missing())

    # Profitability target
    target_profit: FinancialAmount = field(default_factory=lambda: FinancialAmount.missing())

    @staticmethod
    def from_mapping(data: dict[str, Any] | None) -> FinancialDataContract:
        """Build contract from a plain dict; unknown keys ignored."""
        raw = dict(data or {})
        period = raw.pop("reporting_period", None)
        kwargs: dict[str, Any] = {}
        if isinstance(period, ReportingPeriod):
            kwargs["reporting_period"] = period
        for key, value in raw.items():
            if key in FinancialDataContract.__dataclass_fields__:
                field_type = FinancialDataContract.__dataclass_fields__[key].type
                if "FinancialAmount" in str(field_type):
                    kwargs[key] = _amt(value)
                else:
                    kwargs[key] = value
        return FinancialDataContract(**kwargs)

    def amount_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "currency": self.currency,
            "source_system": self.source_system,
            "as_of": self.as_of.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
            "data_freshness": self.data_freshness,
            "data_completeness": self.data_completeness,
            "evidence_references": list(self.evidence_references),
            "advisory_only": self.advisory_only,
            "reporting_period": self.reporting_period.to_dict() if self.reporting_period else None,
        }
        for name, field_def in self.__dataclass_fields__.items():
            if "FinancialAmount" in str(field_def.type):
                out[name] = getattr(self, name).to_dict()
        return out

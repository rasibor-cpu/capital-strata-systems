from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Sequence, Tuple

from backend.commercialization.client_earnings_summary import (
    CommercialClientEarningsSummary,
)
from backend.commercialization.independent_trade_economics import (
    IndependentTradeEconomics,
)


class CustomerProfitabilityError(ValueError):
    """Base error for the combined customer profitability projection."""


@dataclass(frozen=True, slots=True)
class CustomerProfitabilitySummary:
    """Read-only account-period profitability view across separated economics.

    The model combines already-calculated CSS-attributable performance with
    independent/customer-controlled trade economics without merging their
    attribution, loss-recovery, or fee logic.

    It creates no economics and grants no invoicing, deduction, settlement,
    broker, ledger, tax, or money-movement authority.
    """

    account_reference: str
    period_start: str
    period_end: str
    currency: str

    css_realized_profit: Decimal
    css_recovered_loss: Decimal
    css_new_economic_gain: Decimal
    css_performance_fee: Decimal

    independent_realized_profit: Decimal
    independent_platform_charge: Decimal

    gross_customer_profit: Decimal
    total_css_charges: Decimal
    net_customer_profit_after_css_charges: Decimal

    independent_trade_count: int
    evidence_refs: Tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.account_reference or self.account_reference != self.account_reference.strip():
            raise ValueError("account_reference is required and must be canonical")
        if not self.period_start or not self.period_end or self.period_end <= self.period_start:
            raise ValueError("period boundaries must be canonical and increasing")
        if (
            not self.currency
            or self.currency != self.currency.strip()
            or self.currency != self.currency.upper()
        ):
            raise ValueError("currency must be canonical uppercase text")

        for name in (
            "css_realized_profit",
            "css_recovered_loss",
            "css_new_economic_gain",
            "css_performance_fee",
            "independent_realized_profit",
            "independent_platform_charge",
            "gross_customer_profit",
            "total_css_charges",
            "net_customer_profit_after_css_charges",
        ):
            value = getattr(self, name)
            if not isinstance(value, Decimal):
                raise TypeError(f"{name} must be Decimal")
            if not value.is_finite():
                raise ValueError(f"{name} must be finite")

        for name in (
            "css_recovered_loss",
            "css_new_economic_gain",
            "css_performance_fee",
            "independent_platform_charge",
            "total_css_charges",
        ):
            if getattr(self, name) < Decimal("0"):
                raise ValueError(f"{name} cannot be negative")

        if self.independent_trade_count < 0:
            raise ValueError("independent_trade_count cannot be negative")

        expected_gross = self.css_realized_profit + self.independent_realized_profit
        if self.gross_customer_profit != expected_gross:
            raise ValueError("gross_customer_profit must reconcile exactly")

        expected_charges = self.css_performance_fee + self.independent_platform_charge
        if self.total_css_charges != expected_charges:
            raise ValueError("total_css_charges must reconcile exactly")

        expected_net = self.gross_customer_profit - self.total_css_charges
        if self.net_customer_profit_after_css_charges != expected_net:
            raise ValueError("net customer profit must reconcile exactly")

        if not isinstance(self.evidence_refs, tuple) or not self.evidence_refs:
            raise ValueError("evidence_refs must be a non-empty immutable tuple")

    @property
    def money_movement_allowed(self) -> bool:
        return False

    @property
    def invoice_creation_allowed(self) -> bool:
        return False

    @property
    def client_funds_deduction_allowed(self) -> bool:
        return False

    @property
    def execution_authority(self) -> bool:
        return False

    def explain(self) -> dict[str, Any]:
        return {
            "css_attributable": {
                "realized_profit": str(self.css_realized_profit),
                "recovered_loss": str(self.css_recovered_loss),
                "new_economic_gain": str(self.css_new_economic_gain),
                "performance_fee": str(self.css_performance_fee),
            },
            "independent_customer_controlled": {
                "realized_profit": str(self.independent_realized_profit),
                "platform_charge": str(self.independent_platform_charge),
                "trade_count": self.independent_trade_count,
                "affects_css_hwm": False,
                "affects_css_loss_recovery": False,
            },
            "combined_customer_result": {
                "gross_profit": str(self.gross_customer_profit),
                "total_css_charges": str(self.total_css_charges),
                "net_profit_after_css_charges": str(
                    self.net_customer_profit_after_css_charges
                ),
                "currency": self.currency,
            },
        }


def build_customer_profitability_summary(
    css_summary: CommercialClientEarningsSummary,
    independent_economics: Sequence[IndependentTradeEconomics],
) -> CustomerProfitabilitySummary:
    """Compose one transparent customer-period view from separated ledgers.

    The initial implementation is deliberately same-currency only. Cross-
    currency independent activity must be normalized by a separately approved
    FX-evidence path before it can enter this projection.
    """

    if not isinstance(css_summary, CommercialClientEarningsSummary):
        raise TypeError("css_summary must be CommercialClientEarningsSummary")

    billing_currency = css_summary.billing_currency

    independent_profit = Decimal("0")
    independent_charge = Decimal("0")
    evidence = list(css_summary.evidence_refs)

    for record in independent_economics:
        if not isinstance(record, IndependentTradeEconomics):
            raise TypeError("independent_economics must contain IndependentTradeEconomics")
        if record.currency != billing_currency:
            raise CustomerProfitabilityError(
                "independent economics currency must match CSS billing currency"
            )
        independent_profit += record.realized_pnl
        independent_charge += record.platform_charge_amount
        evidence.extend(record.evidence_refs)

    if css_summary.performance_currency != css_summary.billing_currency:
        raise CustomerProfitabilityError(
            "combined profitability requires CSS realized profit normalized to billing currency"
        )

    css_fee = css_summary.selected_fee_amount or Decimal("0")
    css_realized = css_summary.realized_attributable_profit

    gross = css_realized + independent_profit
    charges = css_fee + independent_charge
    net = gross - charges

    return CustomerProfitabilitySummary(
        account_reference=css_summary.account_reference,
        period_start=css_summary.billing_period_start,
        period_end=css_summary.billing_period_end,
        currency=billing_currency,
        css_realized_profit=css_realized,
        css_recovered_loss=css_summary.recovered_loss,
        css_new_economic_gain=css_summary.new_economic_gain,
        css_performance_fee=css_fee,
        independent_realized_profit=independent_profit,
        independent_platform_charge=independent_charge,
        gross_customer_profit=gross,
        total_css_charges=charges,
        net_customer_profit_after_css_charges=net,
        independent_trade_count=len(independent_economics),
        evidence_refs=tuple(dict.fromkeys(evidence)),
    )

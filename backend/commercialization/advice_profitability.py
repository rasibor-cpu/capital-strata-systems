from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Tuple

from backend.commercialization.performance_accounting import (
    PerformanceAccountingTransition,
)
from backend.commercialization.performance_attribution import (
    AttributablePerformance,
)


class AdviceProfitabilityError(ValueError):
    """Base error for advice-level profitability attribution."""


@dataclass(frozen=True, slots=True)
class AdviceProfitability:
    """Read-only economics for one accepted CSS recommendation outcome.

    The record explains what the customer made or lost on the trade,
    how much of a gain merely recovered prior losses, what portion created
    fresh economic gain, the shadow CSS fee attributable to that fresh gain,
    and what the customer retained after that fee.

    It does not invoice, debit, settle, move funds, post a ledger entry, or
    grant broker/execution authority.
    """

    advice_id: str
    trade_id: str
    currency: str

    realized_pnl: Decimal
    recovered_loss: Decimal
    new_economic_gain: Decimal

    performance_fee_rate: Decimal
    css_shadow_fee: Decimal
    customer_retained_after_css_fee: Decimal

    evidence_refs: Tuple[str, ...]

    def __post_init__(self) -> None:
        for name in ("advice_id", "trade_id"):
            value = getattr(self, name)
            if not value or value != value.strip():
                raise ValueError(f"{name} is required and must be canonical")

        if (
            not self.currency
            or self.currency != self.currency.strip()
            or self.currency != self.currency.upper()
        ):
            raise ValueError("currency must be canonical uppercase text")

        for name in (
            "realized_pnl",
            "recovered_loss",
            "new_economic_gain",
            "performance_fee_rate",
            "css_shadow_fee",
            "customer_retained_after_css_fee",
        ):
            value = getattr(self, name)
            if not isinstance(value, Decimal):
                raise TypeError(f"{name} must be Decimal")
            if not value.is_finite():
                raise ValueError(f"{name} must be finite")

        if self.recovered_loss < Decimal("0"):
            raise ValueError("recovered_loss cannot be negative")
        if self.new_economic_gain < Decimal("0"):
            raise ValueError("new_economic_gain cannot be negative")
        if not Decimal("0") <= self.performance_fee_rate <= Decimal("1"):
            raise ValueError("performance_fee_rate must be between 0 and 1")
        if self.css_shadow_fee < Decimal("0"):
            raise ValueError("css_shadow_fee cannot be negative")

        expected_fee = self.new_economic_gain * self.performance_fee_rate
        if self.css_shadow_fee != expected_fee:
            raise ValueError("css_shadow_fee must equal new economic gain times fee rate")

        expected_retained = self.realized_pnl - self.css_shadow_fee
        if self.customer_retained_after_css_fee != expected_retained:
            raise ValueError(
                "customer_retained_after_css_fee must equal realized P&L less CSS fee"
            )

        if not isinstance(self.evidence_refs, tuple) or not self.evidence_refs:
            raise ValueError("evidence_refs must be a non-empty immutable tuple")

    @property
    def fee_applies(self) -> bool:
        return self.css_shadow_fee > Decimal("0")

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
            "advice_id": self.advice_id,
            "trade_id": self.trade_id,
            "customer_realized_pnl": str(self.realized_pnl),
            "loss_recovery_applied": str(self.recovered_loss),
            "fresh_economic_gain": str(self.new_economic_gain),
            "css_fee_rate": str(self.performance_fee_rate),
            "css_shadow_fee": str(self.css_shadow_fee),
            "customer_retained_after_css_fee": str(
                self.customer_retained_after_css_fee
            ),
            "currency": self.currency,
        }


def build_advice_profitability(
    performance: AttributablePerformance,
    transition: PerformanceAccountingTransition,
    *,
    performance_fee_rate: Decimal,
) -> AdviceProfitability:
    """Build advice-level economics from canonical attribution/accounting.

    Fee allocation is strictly to fresh economic gain. Losses and gains used
    only to recover a previous drawdown produce no CSS fee.
    """

    if not isinstance(performance, AttributablePerformance):
        raise TypeError("performance must be AttributablePerformance")
    if not isinstance(transition, PerformanceAccountingTransition):
        raise TypeError("transition must be PerformanceAccountingTransition")
    if performance.trade_id != transition.trade_id:
        raise AdviceProfitabilityError("trade_id mismatch")
    if performance.realized_pnl != transition.attributable_realized_pnl:
        raise AdviceProfitabilityError("realized P&L mismatch")
    if not isinstance(performance_fee_rate, Decimal):
        raise TypeError("performance_fee_rate must be Decimal")
    if not performance_fee_rate.is_finite():
        raise ValueError("performance_fee_rate must be finite")
    if not Decimal("0") <= performance_fee_rate <= Decimal("1"):
        raise ValueError("performance_fee_rate must be between 0 and 1")

    fee = transition.new_economic_gain * performance_fee_rate
    retained = performance.realized_pnl - fee
    evidence = tuple(
        dict.fromkeys(
            performance.provenance_evidence_refs
            + performance.economics_evidence_refs
        )
    )

    return AdviceProfitability(
        advice_id=performance.advice_id,
        trade_id=performance.trade_id,
        currency=performance.currency,
        realized_pnl=performance.realized_pnl,
        recovered_loss=transition.recovered_loss,
        new_economic_gain=transition.new_economic_gain,
        performance_fee_rate=performance_fee_rate,
        css_shadow_fee=fee,
        customer_retained_after_css_fee=retained,
        evidence_refs=evidence,
    )

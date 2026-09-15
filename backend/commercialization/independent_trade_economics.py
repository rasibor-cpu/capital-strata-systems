from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Tuple

from backend.commercialization.trade_provenance import (
    AttributionClass,
    TradeProvenance,
)


class IndependentTradeEconomicsError(ValueError):
    """Base error for independent/customer-directed economics."""


class IndependentTradeEconomicsIneligibleError(IndependentTradeEconomicsError):
    """Raised when a trade cannot enter the independent-use charging path."""


class IndependentTradeChargeBasis(str, Enum):
    """Canonical basis for non-performance CSS platform economics."""

    PLATFORM_USAGE = "PLATFORM_USAGE"


@dataclass(frozen=True, slots=True)
class IndependentTradeEconomics:
    """Immutable economics record for customer-directed or CSS-modified trades.

    This path is deliberately separate from CSS performance attribution,
    high-water marks, loss recovery, and performance compensation.

    The record is documentary/shadow-only. It authorizes no debit, invoice,
    receivable, settlement, tax posting, broker action, or money movement.
    """

    trade_id: str
    account_reference: str
    calculation_timestamp: str
    attribution_class: AttributionClass
    realized_pnl: Decimal
    currency: str
    platform_charge_rate: Decimal
    platform_charge_amount: Decimal
    charge_basis: IndependentTradeChargeBasis
    evidence_refs: Tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.trade_id or self.trade_id != self.trade_id.strip():
            raise ValueError("trade_id is required and must be canonical")
        if not self.account_reference or self.account_reference != self.account_reference.strip():
            raise ValueError("account_reference is required and must be canonical")
        if not self.calculation_timestamp or self.calculation_timestamp != self.calculation_timestamp.strip():
            raise ValueError("calculation_timestamp is required and must be canonical")
        if self.attribution_class not in {
            AttributionClass.CUSTOMER_DIRECTED,
            AttributionClass.CSS_MODIFIED,
        }:
            raise ValueError(
                "independent economics requires CUSTOMER_DIRECTED or CSS_MODIFIED provenance"
            )
        for name in (
            "realized_pnl",
            "platform_charge_rate",
            "platform_charge_amount",
        ):
            value = getattr(self, name)
            if not isinstance(value, Decimal):
                raise TypeError(f"{name} must be Decimal")
            if not value.is_finite():
                raise ValueError(f"{name} must be finite")
        if self.platform_charge_rate < Decimal("0") or self.platform_charge_rate > Decimal("1"):
            raise ValueError("platform_charge_rate must be between 0 and 1")
        if self.platform_charge_amount < Decimal("0"):
            raise ValueError("platform_charge_amount cannot be negative")
        if (
            not self.currency
            or self.currency != self.currency.strip()
            or self.currency != self.currency.upper()
        ):
            raise ValueError("currency must be canonical uppercase text")
        if self.charge_basis != IndependentTradeChargeBasis.PLATFORM_USAGE:
            raise ValueError("independent trade economics must use PLATFORM_USAGE basis")
        if not isinstance(self.evidence_refs, tuple) or not self.evidence_refs:
            raise ValueError("evidence_refs must be a non-empty immutable tuple")

    @property
    def css_performance_attributable(self) -> bool:
        return False

    @property
    def high_water_mark_affected(self) -> bool:
        return False

    @property
    def loss_recovery_affected(self) -> bool:
        return False

    @property
    def performance_fee_eligible(self) -> bool:
        return False

    @property
    def real_fee_collection_allowed(self) -> bool:
        return False

    @property
    def client_funds_deduction_allowed(self) -> bool:
        return False

    @property
    def money_movement_allowed(self) -> bool:
        return False

    @property
    def invoice_creation_allowed(self) -> bool:
        return False

    @property
    def execution_authority(self) -> bool:
        return False


def build_independent_trade_economics(
    provenance: TradeProvenance,
    *,
    account_reference: str,
    calculation_timestamp: str,
    realized_pnl: Decimal,
    currency: str,
    platform_charge_rate: Decimal,
    evidence_refs: Tuple[str, ...],
) -> IndependentTradeEconomics:
    """Build shadow platform economics for independent/customer-controlled trades.

    CSS-advised accepted trades are rejected because they belong exclusively
    to the performance-attribution/HWM path. External trades are rejected
    because CSS has no charging claim over activity outside CSS.
    """

    if not isinstance(provenance, TradeProvenance):
        raise TypeError("provenance must be TradeProvenance")

    if provenance.attribution_class == AttributionClass.CSS_ADVISED_ACCEPTED:
        raise IndependentTradeEconomicsIneligibleError(
            "CSS-attributable trades must use the performance-fee path"
        )
    if provenance.attribution_class == AttributionClass.EXTERNAL:
        raise IndependentTradeEconomicsIneligibleError(
            "external trades are excluded from CSS economics"
        )
    if provenance.attribution_class not in {
        AttributionClass.CUSTOMER_DIRECTED,
        AttributionClass.CSS_MODIFIED,
    }:
        raise IndependentTradeEconomicsIneligibleError(
            "trade is not eligible for independent platform economics"
        )

    if not isinstance(realized_pnl, Decimal) or not realized_pnl.is_finite():
        raise TypeError("realized_pnl must be a finite Decimal")
    if not isinstance(platform_charge_rate, Decimal) or not platform_charge_rate.is_finite():
        raise TypeError("platform_charge_rate must be a finite Decimal")
    if platform_charge_rate < Decimal("0") or platform_charge_rate > Decimal("1"):
        raise ValueError("platform_charge_rate must be between 0 and 1")

    # The independent-use charge is not a performance fee. It is calculated
    # from positive realized activity only; losses never create a charge.
    positive_realized = max(realized_pnl, Decimal("0"))
    amount = positive_realized * platform_charge_rate

    return IndependentTradeEconomics(
        trade_id=provenance.trade_id,
        account_reference=account_reference,
        calculation_timestamp=calculation_timestamp,
        attribution_class=provenance.attribution_class,
        realized_pnl=realized_pnl,
        currency=currency,
        platform_charge_rate=platform_charge_rate,
        platform_charge_amount=amount,
        charge_basis=IndependentTradeChargeBasis.PLATFORM_USAGE,
        evidence_refs=evidence_refs,
    )

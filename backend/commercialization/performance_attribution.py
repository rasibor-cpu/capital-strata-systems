from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Tuple

from backend.commercialization.trade_provenance import TradeProvenance


class PerformanceAttributionError(ValueError):
    """Base COM-002B attribution-contract error."""


class PerformanceAttributionIneligibleError(
    PerformanceAttributionError
):
    """Raised when a trade cannot enter the CSS performance book."""


@dataclass(frozen=True, slots=True)
class VerifiedTradeEconomics:
    """
    Verified realized economics for one trade.

    This object does not infer P&L from cash movement, calculate
    fees, move client funds, or grant execution authority.
    """

    trade_id: str
    realized_pnl: Decimal
    currency: str
    verification_timestamp: str
    evidence_refs: Tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.trade_id or self.trade_id != self.trade_id.strip():
            raise ValueError(
                "trade_id is required and must be canonical"
            )

        if not isinstance(self.realized_pnl, Decimal):
            raise TypeError("realized_pnl must be Decimal")

        if not self.realized_pnl.is_finite():
            raise ValueError("realized_pnl must be finite")

        if (
            not self.currency
            or self.currency != self.currency.strip()
            or self.currency != self.currency.upper()
        ):
            raise ValueError(
                "currency must be canonical uppercase text"
            )

        if not self.verification_timestamp:
            raise ValueError(
                "verification_timestamp is required"
            )

        if not self.evidence_refs:
            raise ValueError(
                "verified economics require evidence"
            )


@dataclass(frozen=True, slots=True)
class AttributablePerformance:
    """
    Immutable COM-002B attributable realized-performance record.

    Attribution does not establish fee entitlement, fee accrual,
    client-funds authority, or execution authority.
    """

    trade_id: str
    advice_id: str
    realized_pnl: Decimal
    currency: str
    verification_timestamp: str
    provenance_evidence_refs: Tuple[str, ...]
    economics_evidence_refs: Tuple[str, ...]

    @property
    def real_fee_collection_allowed(self) -> bool:
        return False

    @property
    def client_funds_deduction_allowed(self) -> bool:
        return False

    @property
    def execution_authority(self) -> bool:
        return False


def build_attributable_performance(
    provenance: TradeProvenance,
    economics: VerifiedTradeEconomics,
) -> AttributablePerformance:
    """
    Fail-closed COM-002B attribution gate.

    P&L sign never affects eligibility. Eligible losses and profits
    enter attribution symmetrically.
    """

    if provenance.trade_id != economics.trade_id:
        raise PerformanceAttributionIneligibleError(
            "trade_id mismatch between provenance and economics"
        )

    if not provenance.css_performance_attribution_eligible:
        raise PerformanceAttributionIneligibleError(
            "trade is not CSS performance-attribution eligible"
        )

    if not provenance.advice_id:
        raise PerformanceAttributionIneligibleError(
            "eligible CSS attribution requires advice_id"
        )

    return AttributablePerformance(
        trade_id=provenance.trade_id,
        advice_id=provenance.advice_id,
        realized_pnl=economics.realized_pnl,
        currency=economics.currency,
        verification_timestamp=economics.verification_timestamp,
        provenance_evidence_refs=provenance.evidence_refs,
        economics_evidence_refs=economics.evidence_refs,
    )

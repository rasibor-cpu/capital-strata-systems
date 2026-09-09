from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Tuple

from backend.commercialization.billing_profile import (
    _parse_canonical_utc_timestamp, _require_evidence_refs,
)
from backend.commercialization.performance_compensation import (
    PerformanceCompensationTerms, _require_canonical_id, _require_finite_decimal,
)
from backend.commercialization.performance_crystallization import (
    CrystallizationAssessment, CrystallizationStatus,
)
from backend.commercialization.platform_access_fee_terms import CommercialPlatformAccessFeeTerms
from backend.commercialization.fx_conversion import CommercialFxConversionEvidence, _require_iso_currency


class FinalFeeSelectionIneligibleError(ValueError):
    """The supplied contractual snapshots cannot support fee selection."""


class FinalFeeBasis(str, Enum):
    PLATFORM_ACCESS = "PLATFORM_ACCESS"
    PERFORMANCE_COMPENSATION = "PERFORMANCE_COMPENSATION"


@dataclass(frozen=True, slots=True)
class CommercialFinalFeeSelection:
    """COM-002W documentary maximum of two alternatives, never their sum.

    policy_id preserves the canonical crystallization period identity.
    This record authorizes no invoice, receivable, payment, tax or GL posting.
    """

    fee_selection_id: str
    access_terms_id: str
    terms_id: str
    policy_id: str
    billing_currency: str
    period_start: str
    period_end: str
    platform_access_fee_amount: Decimal
    performance_fee_source_currency: str
    performance_fee_source_amount: Decimal
    performance_fee_billing_currency_amount: Decimal
    selected_fee_amount: Decimal
    selected_fee_basis: FinalFeeBasis
    selected_at: str
    evidence_refs: Tuple[str, ...]
    fx_conversion_id: str | None = None

    def __post_init__(self) -> None:
        for name in ("fee_selection_id", "access_terms_id", "terms_id", "policy_id"):
            _require_canonical_id(name, getattr(self, name))
        _require_iso_currency("billing_currency", self.billing_currency)
        _require_iso_currency("performance_fee_source_currency", self.performance_fee_source_currency)
        if self.billing_currency != "USD":
            raise ValueError("billing_currency must be USD")
        start = _parse_canonical_utc_timestamp("period_start", self.period_start)
        end = _parse_canonical_utc_timestamp("period_end", self.period_end)
        _parse_canonical_utc_timestamp("selected_at", self.selected_at)
        if end <= start:
            raise ValueError("period_end must be after period_start")
        for name in ("platform_access_fee_amount", "performance_fee_source_amount",
                     "performance_fee_billing_currency_amount", "selected_fee_amount"):
            if _require_finite_decimal(name, getattr(self, name)) < 0:
                raise ValueError(f"{name} cannot be negative")
        if not isinstance(self.selected_fee_basis, FinalFeeBasis):
            raise TypeError("selected_fee_basis must be FinalFeeBasis")
        performance_wins = self.performance_fee_billing_currency_amount >= self.platform_access_fee_amount
        basis = FinalFeeBasis.PERFORMANCE_COMPENSATION if performance_wins else FinalFeeBasis.PLATFORM_ACCESS
        amount = max(self.platform_access_fee_amount, self.performance_fee_billing_currency_amount)
        if self.selected_fee_amount != amount or self.selected_fee_basis != basis:
            raise ValueError("selected fee must be the maximum candidate; performance wins ties")
        if self.performance_fee_source_currency == self.billing_currency:
            if self.fx_conversion_id is not None:
                raise ValueError("USD performance must bypass FX evidence")
            if self.performance_fee_source_amount != self.performance_fee_billing_currency_amount:
                raise ValueError("USD performance amount must be preserved exactly")
        else:
            _require_canonical_id("fx_conversion_id", self.fx_conversion_id)
        if not isinstance(self.evidence_refs, tuple):
            raise TypeError("evidence_refs must be an immutable tuple")
        _require_evidence_refs(self.evidence_refs)

    @property
    def money_movement_allowed(self) -> bool:
        return False

    @property
    def execution_authority(self) -> bool:
        return False


def build_final_fee_selection(
    access_terms: CommercialPlatformAccessFeeTerms,
    performance_terms: PerformanceCompensationTerms,
    performance: CrystallizationAssessment,
    *, fee_selection_id: str, period_start: str, period_end: str,
    selected_at: str, evidence_refs: Tuple[str, ...],
    fx_conversion: CommercialFxConversionEvidence | None = None,
) -> CommercialFinalFeeSelection:
    """Use an eligible upstream COM-002E assessment; do not recompute A-D.

    The caller supplies the contractual billing period and applicable terms.
    Period strings must match the upstream persistence keys exactly. Access
    terms must cover the entire [start, end) period; overlap alone is not
    enough. No calendar, rate freshness, or automatic terms selection policy
    is inferred. A USD candidate bypasses conversion evidence entirely.
    """
    for value, expected in ((access_terms, CommercialPlatformAccessFeeTerms),
                            (performance_terms, PerformanceCompensationTerms),
                            (performance, CrystallizationAssessment)):
        if not isinstance(value, expected):
            raise TypeError(f"expected {expected.__name__}")
    if not access_terms.accepted or not performance_terms.accepted:
        raise FinalFeeSelectionIneligibleError("both terms must be accepted")
    if performance.terms_id != performance_terms.terms_id:
        raise FinalFeeSelectionIneligibleError("performance terms_id mismatch")
    if performance.currency != performance_terms.currency:
        raise FinalFeeSelectionIneligibleError("performance terms currency mismatch")
    if performance.status != CrystallizationStatus.ELIGIBLE:
        raise FinalFeeSelectionIneligibleError("performance assessment must be ELIGIBLE")
    if (period_start, period_end) != (performance.period_start, performance.period_end):
        raise FinalFeeSelectionIneligibleError("period mismatch with performance assessment")
    start = _parse_canonical_utc_timestamp("period_start", period_start)
    end = _parse_canonical_utc_timestamp("period_end", period_end)
    if start < _parse_canonical_utc_timestamp("effective_from", access_terms.effective_from):
        raise FinalFeeSelectionIneligibleError("access terms do not cover period start")
    if access_terms.effective_to is not None and end > _parse_canonical_utc_timestamp(
        "effective_to", access_terms.effective_to,
    ):
        raise FinalFeeSelectionIneligibleError("access terms do not cover period end")
    source_amount = performance.crystallizable_amount
    if performance.currency == access_terms.billing_currency:
        if fx_conversion is not None:
            raise FinalFeeSelectionIneligibleError("USD performance must bypass FX evidence")
        normalized = source_amount
    else:
        if not isinstance(fx_conversion, CommercialFxConversionEvidence):
            raise FinalFeeSelectionIneligibleError("non-USD performance requires FX evidence")
        if fx_conversion.source_currency != performance.currency:
            raise FinalFeeSelectionIneligibleError("FX source currency mismatch")
        if fx_conversion.target_currency != access_terms.billing_currency:
            raise FinalFeeSelectionIneligibleError("FX target currency mismatch")
        if fx_conversion.source_amount != source_amount:
            raise FinalFeeSelectionIneligibleError("FX source amount mismatch")
        normalized = fx_conversion.converted_amount
    performance_wins = normalized >= access_terms.access_fee_amount
    return CommercialFinalFeeSelection(
        fee_selection_id=fee_selection_id, access_terms_id=access_terms.access_terms_id,
        terms_id=performance.terms_id, policy_id=performance.policy_id,
        billing_currency=access_terms.billing_currency,
        period_start=period_start, period_end=period_end,
        platform_access_fee_amount=access_terms.access_fee_amount,
        performance_fee_source_currency=performance.currency,
        performance_fee_source_amount=source_amount,
        performance_fee_billing_currency_amount=normalized,
        selected_fee_amount=max(access_terms.access_fee_amount, normalized),
        selected_fee_basis=(FinalFeeBasis.PERFORMANCE_COMPENSATION if performance_wins
                            else FinalFeeBasis.PLATFORM_ACCESS),
        selected_at=selected_at, evidence_refs=evidence_refs,
        fx_conversion_id=fx_conversion.fx_conversion_id if fx_conversion else None,
    )

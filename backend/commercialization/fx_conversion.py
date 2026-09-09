from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, localcontext, MAX_EMAX, MIN_EMIN, Inexact
from typing import Tuple

from backend.commercialization.billing_profile import (
    _parse_canonical_utc_timestamp, _require_evidence_refs,
)
from backend.commercialization.performance_compensation import (
    _require_canonical_id, _require_canonical_currency, _require_finite_decimal,
)


def _require_iso_currency(name: str, value: str) -> None:
    _require_canonical_currency(value)
    if len(value) != 3 or not value.isascii() or not value.isalpha():
        raise ValueError(f"{name} must be a three-letter uppercase currency code")


def _exact_product(amount: Decimal, rate: Decimal) -> Decimal:
    """Preserve all coefficient digits independently of caller precision."""
    with localcontext() as context:
        context.prec = len(amount.as_tuple().digits) + len(rate.as_tuple().digits)
        context.Emax = MAX_EMAX
        context.Emin = MIN_EMIN
        context.traps[Inexact] = True
        return amount * rate


@dataclass(frozen=True, slots=True)
class CommercialFxConversionEvidence:
    """COM-002V evidenced normalization into USD; no provider or settlement.

    Caller supplies the authoritative daily prevailing rate and its provenance.
    This record defines neither a provider nor a rate-age policy.
    """

    fx_conversion_id: str
    source_currency: str
    target_currency: str
    source_amount: Decimal
    converted_amount: Decimal
    fx_rate: Decimal
    rate_effective_at: str
    rate_source_reference: str
    evidence_refs: Tuple[str, ...]

    def __post_init__(self) -> None:
        _require_canonical_id("fx_conversion_id", self.fx_conversion_id)
        _require_canonical_id("rate_source_reference", self.rate_source_reference)
        _require_iso_currency("source_currency", self.source_currency)
        _require_iso_currency("target_currency", self.target_currency)
        if self.source_currency == self.target_currency:
            raise ValueError("same-currency conversion is not FX evidence")
        if self.target_currency != "USD":
            raise ValueError("target_currency must be USD")
        for name in ("source_amount", "converted_amount", "fx_rate"):
            if _require_finite_decimal(name, getattr(self, name)) < 0:
                raise ValueError(f"{name} cannot be negative")
        if self.fx_rate == 0:
            raise ValueError("fx_rate must be positive")
        if self.converted_amount != _exact_product(self.source_amount, self.fx_rate):
            raise ValueError("converted_amount must equal source_amount * fx_rate exactly")
        _parse_canonical_utc_timestamp("rate_effective_at", self.rate_effective_at)
        if not isinstance(self.evidence_refs, tuple):
            raise TypeError("evidence_refs must be an immutable tuple")
        _require_evidence_refs(self.evidence_refs)

    @property
    def money_movement_allowed(self) -> bool:
        return False

    @property
    def execution_authority(self) -> bool:
        return False


def build_fx_conversion_evidence(
    *, fx_conversion_id: str, source_currency: str, target_currency: str,
    source_amount: Decimal, fx_rate: Decimal, rate_effective_at: str,
    rate_source_reference: str, evidence_refs: Tuple[str, ...],
) -> CommercialFxConversionEvidence:
    _require_finite_decimal("source_amount", source_amount)
    _require_finite_decimal("fx_rate", fx_rate)
    return CommercialFxConversionEvidence(
        fx_conversion_id, source_currency, target_currency, source_amount,
        _exact_product(source_amount, fx_rate), fx_rate, rate_effective_at,
        rate_source_reference, evidence_refs,
    )

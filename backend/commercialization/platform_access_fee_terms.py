from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Optional, Tuple

from backend.commercialization.billing_profile import (
    _parse_canonical_utc_timestamp,
    _require_evidence_refs,
)
from backend.commercialization.performance_compensation import (
    _require_canonical_currency,
    _require_canonical_id,
    _require_finite_decimal,
)


class PlatformAccessBillingFrequency(str, Enum):
    """Contractual access billing cadence, independent of crystallization."""

    MONTHLY = "MONTHLY"


@dataclass(frozen=True, slots=True)
class CommercialPlatformAccessFeeTerms:
    """Immutable COM-002U contractual pricing, with caller-supplied amounts.

    USD is the initially supported billing currency. Zero is permitted,
    consistent with nonnegative performance compensation terms. Amounts
    are neither rounded nor normalized to currency minor units.

    Acceptance records contractual state only; it grants no legal execution
    or collection authority. New pricing requires a new access_terms_id and
    effectivity record; historical terms must not be overwritten. There is
    no automatic review, replacement, repricing, or fee calculation here.
    """

    access_terms_id: str
    billing_currency: str
    access_fee_amount: Decimal
    billing_frequency: PlatformAccessBillingFrequency
    effective_from: str
    evidence_refs: Tuple[str, ...]
    accepted: bool
    effective_to: Optional[str] = None

    def __post_init__(self) -> None:
        _require_canonical_id("access_terms_id", self.access_terms_id)
        _require_canonical_currency(self.billing_currency)
        if self.billing_currency != "USD":
            raise ValueError("billing_currency must be USD for COM-002U")
        amount = _require_finite_decimal(
            "access_fee_amount", self.access_fee_amount,
        )
        if amount < Decimal("0"):
            raise ValueError("access_fee_amount cannot be negative")
        if not isinstance(self.billing_frequency, PlatformAccessBillingFrequency):
            raise TypeError("billing_frequency must be PlatformAccessBillingFrequency")
        start = _parse_canonical_utc_timestamp(
            "effective_from", self.effective_from,
        )
        if self.effective_to is not None:
            end = _parse_canonical_utc_timestamp("effective_to", self.effective_to)
            if end <= start:
                raise ValueError("effective_to must be after effective_from")
        if not isinstance(self.accepted, bool):
            raise TypeError("accepted must be bool")
        if not isinstance(self.evidence_refs, tuple):
            raise TypeError("evidence_refs must be an immutable tuple")
        _require_evidence_refs(self.evidence_refs)

    @property
    def real_fee_collection_allowed(self) -> bool:
        return False

    @property
    def money_movement_allowed(self) -> bool:
        return False

    @property
    def invoice_creation_allowed(self) -> bool:
        return False

    @property
    def receivable_recognition_allowed(self) -> bool:
        return False

    @property
    def tax_calculation_allowed(self) -> bool:
        return False

    @property
    def ledger_posting_allowed(self) -> bool:
        return False

    @property
    def execution_authority(self) -> bool:
        return False

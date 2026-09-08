from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Sequence, Tuple

from backend.commercialization.performance_crystallization import (
    CrystallizationAssessment,
    CrystallizationStatus,
)


class SettlementReadinessError(ValueError):
    """Base COM-002F settlement-readiness contract error."""


class SettlementReadinessIneligibleError(SettlementReadinessError):
    """Raised when settlement readiness cannot be established."""


class SettlementReadinessStatus(str, Enum):
    """
    Explicit administrative readiness decision for a crystallized
    commercial period.

    Deliberately excludes money-state vocabulary such as PAID,
    COLLECTED, SETTLED, DEBITED, or INVOICED.
    """

    NOT_READY = "NOT_READY"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    READY = "READY"
    BLOCKED = "BLOCKED"
    EXPIRED = "EXPIRED"


def _require_canonical_id(name: str, value: str) -> None:
    if not value or value != value.strip():
        raise ValueError(
            f"{name} is required and must be canonical"
        )


def _require_canonical_currency(currency: str) -> None:
    if (
        not currency
        or currency != currency.strip()
        or currency != currency.upper()
    ):
        raise ValueError(
            "currency must be canonical uppercase text"
        )


def _require_finite_decimal(name: str, value: object) -> Decimal:
    if not isinstance(value, Decimal):
        raise TypeError(f"{name} must be Decimal")

    if not value.is_finite():
        raise ValueError(f"{name} must be finite")

    return value


def _require_evidence_refs(evidence_refs: Sequence[str]) -> None:
    if not evidence_refs:
        raise ValueError("evidence_refs must be non-empty")

    for ref in evidence_refs:
        if not isinstance(ref, str) or not ref or ref != ref.strip():
            raise ValueError(
                "evidence refs must be nonblank canonical strings"
            )


def _parse_canonical_utc_timestamp(name: str, value: str) -> datetime:
    """
    Localized COM-002F datetime rule.

    Accepts timezone-aware ISO-8601 timestamps whose offset is UTC
    (+00:00 or Z). Naive datetimes and non-UTC offsets are rejected.
    """

    if not value or value != value.strip():
        raise ValueError(
            f"{name} is required and must be canonical"
        )

    text = value.strip()
    try:
        parsed = datetime.fromisoformat(
            text.replace("Z", "+00:00")
        )
    except ValueError as exc:
        raise ValueError(
            f"{name} must be timezone-aware UTC ISO-8601"
        ) from exc

    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(
            f"{name} must be timezone-aware UTC ISO-8601"
        )

    if parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise ValueError(
            f"{name} must use UTC offset only"
        )

    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True, slots=True)
class CommercialSettlementReadiness:
    """
    Immutable commercial settlement-readiness decision for one
    crystallized commercial period.

    Keyed one-to-one with COM-002E crystallization by:
    (policy_id, period_start, period_end)

    READY means only that the crystallized economic entitlement has
    passed the explicit non-cash readiness decision represented here.
    It does not collect, debit, invoice, settle, transfer, withdraw,
    or execute.
    """

    policy_id: str
    terms_id: str
    currency: str
    period_start: str
    period_end: str
    crystallizable_amount: Decimal
    assessed_at: str
    status: SettlementReadinessStatus
    evidence_refs: Tuple[str, ...]

    def __post_init__(self) -> None:
        _require_canonical_id("policy_id", self.policy_id)
        _require_canonical_id("terms_id", self.terms_id)
        _require_canonical_currency(self.currency)

        period_start = _parse_canonical_utc_timestamp(
            "period_start",
            self.period_start,
        )
        period_end = _parse_canonical_utc_timestamp(
            "period_end",
            self.period_end,
        )
        _parse_canonical_utc_timestamp(
            "assessed_at",
            self.assessed_at,
        )

        if period_end <= period_start:
            raise ValueError(
                "period_end must be after period_start"
            )

        amount = _require_finite_decimal(
            "crystallizable_amount",
            self.crystallizable_amount,
        )

        if amount < Decimal("0"):
            raise ValueError(
                "crystallizable_amount cannot be negative"
            )

        if not isinstance(self.status, SettlementReadinessStatus):
            raise TypeError(
                "status must be SettlementReadinessStatus"
            )

        _require_evidence_refs(self.evidence_refs)

    @property
    def real_fee_collection_allowed(self) -> bool:
        return False

    @property
    def client_funds_deduction_allowed(self) -> bool:
        return False

    @property
    def automatic_debit_allowed(self) -> bool:
        return False

    @property
    def invoice_settlement_allowed(self) -> bool:
        return False

    @property
    def money_movement_allowed(self) -> bool:
        return False

    @property
    def broker_withdrawal_allowed(self) -> bool:
        return False

    @property
    def payment_initiation_allowed(self) -> bool:
        return False

    @property
    def execution_authority(self) -> bool:
        return False


def build_settlement_readiness(
    assessment: CrystallizationAssessment,
    status: SettlementReadinessStatus,
    assessed_at: str,
    evidence_refs: Tuple[str, ...],
) -> CommercialSettlementReadiness:
    """
    Fail-closed COM-002F readiness builder.

    Copies crystallized economics from the upstream assessment.
    Does not recalculate compensation and does not infer readiness
    gates. READY requires CrystallizationStatus.ELIGIBLE.
    """

    if not isinstance(assessment, CrystallizationAssessment):
        raise TypeError(
            "assessment must be CrystallizationAssessment"
        )

    if not isinstance(status, SettlementReadinessStatus):
        raise TypeError(
            "status must be SettlementReadinessStatus"
        )

    _parse_canonical_utc_timestamp("assessed_at", assessed_at)
    _require_evidence_refs(evidence_refs)

    if status == SettlementReadinessStatus.READY and (
        assessment.status != CrystallizationStatus.ELIGIBLE
    ):
        raise SettlementReadinessIneligibleError(
            "READY requires ELIGIBLE crystallization assessment"
        )

    return CommercialSettlementReadiness(
        policy_id=assessment.policy_id,
        terms_id=assessment.terms_id,
        currency=assessment.currency,
        period_start=assessment.period_start,
        period_end=assessment.period_end,
        crystallizable_amount=assessment.crystallizable_amount,
        assessed_at=assessed_at,
        status=status,
        evidence_refs=evidence_refs,
    )

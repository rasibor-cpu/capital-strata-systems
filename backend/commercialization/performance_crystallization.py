from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Optional, Sequence, Tuple

from backend.commercialization.performance_compensation import (
    ShadowCompensationEntitlement,
)


class PerformanceCrystallizationError(ValueError):
    """Base COM-002E crystallization-contract error."""


class PerformanceCrystallizationIneligibleError(
    PerformanceCrystallizationError
):
    """Raised when a crystallization assessment cannot be established."""


class CrystallizationFrequency(str, Enum):
    """
    Explicit commercial crystallization cadence capabilities.

    These are supported policy vocabulary values, not a statement that
    CSS commercially uses every cadence by default.
    """

    MONTHLY = "MONTHLY"
    QUARTERLY = "QUARTERLY"
    ANNUALLY = "ANNUALLY"
    TERMINATION_ONLY = "TERMINATION_ONLY"
    MANUAL_REVIEW = "MANUAL_REVIEW"


class CrystallizationStatus(str, Enum):
    """
    Economic lifecycle classification for a commercial period.

    Deliberately excludes money-state vocabulary such as PAID,
    COLLECTED, SETTLED, or INVOICED.
    """

    NOT_DUE = "NOT_DUE"
    ELIGIBLE = "ELIGIBLE"
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
    Localized COM-002E datetime rule.

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
class PerformanceCompensationLifecyclePolicy:
    """
    Immutable commercial lifecycle policy for shadow compensation.

    Crystallization frequency must be stated explicitly. There is no
    default cadence.

    crystallize_on_termination is configuration only. This object does
    not implement termination lifecycle, cancellation, or collection.

    PerformanceCompensationTerms.effective_to remains terms effectivity
    only and must not be treated as termination or crystallization.
    """

    policy_id: str
    terms_id: str
    currency: str
    crystallization_frequency: CrystallizationFrequency
    effective_from: str
    evidence_refs: Tuple[str, ...]
    crystallize_on_termination: bool = False
    effective_to: Optional[str] = None

    def __post_init__(self) -> None:
        _require_canonical_id("policy_id", self.policy_id)
        _require_canonical_id("terms_id", self.terms_id)
        _require_canonical_currency(self.currency)

        if not isinstance(
            self.crystallization_frequency,
            CrystallizationFrequency,
        ):
            raise TypeError(
                "crystallization_frequency must be "
                "CrystallizationFrequency"
            )

        if not isinstance(self.crystallize_on_termination, bool):
            raise TypeError(
                "crystallize_on_termination must be bool"
            )

        effective_from = _parse_canonical_utc_timestamp(
            "effective_from",
            self.effective_from,
        )

        if self.effective_to is not None:
            effective_to = _parse_canonical_utc_timestamp(
                "effective_to",
                self.effective_to,
            )
            if effective_to < effective_from:
                raise ValueError(
                    "effective_to must not precede effective_from"
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
    def execution_authority(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class CrystallizationAssessment:
    """
    Immutable economic classification for one commercial period.

    Aggregation scope is terms_id + currency + explicit period.
    Crystallization fixes economic entitlement for the period. It does
    not collect, debit, invoice, settle, transfer, or withdraw funds.
    """

    policy_id: str
    terms_id: str
    currency: str
    period_start: str
    period_end: str
    assessed_at: str
    shadow_entitlement_total: Decimal
    crystallizable_amount: Decimal
    status: CrystallizationStatus
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

        total = _require_finite_decimal(
            "shadow_entitlement_total",
            self.shadow_entitlement_total,
        )
        amount = _require_finite_decimal(
            "crystallizable_amount",
            self.crystallizable_amount,
        )

        if total < Decimal("0"):
            raise ValueError(
                "shadow_entitlement_total cannot be negative"
            )

        if amount < Decimal("0"):
            raise ValueError(
                "crystallizable_amount cannot be negative"
            )

        if amount > total:
            raise ValueError(
                "crystallizable_amount cannot exceed "
                "shadow_entitlement_total"
            )

        if not isinstance(self.status, CrystallizationStatus):
            raise TypeError(
                "status must be CrystallizationStatus"
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
    def execution_authority(self) -> bool:
        return False


def build_crystallization_assessment(
    policy: PerformanceCompensationLifecyclePolicy,
    entitlements: Sequence[ShadowCompensationEntitlement],
    period_start: str,
    period_end: str,
    assessed_at: str,
    status: CrystallizationStatus,
    evidence_refs: Tuple[str, ...],
) -> CrystallizationAssessment:
    """
    Fail-closed COM-002E assessment builder.

    The caller supplies an explicit commercial period. This function
    does not infer month/quarter/year boundaries and does not filter
    entitlements by calculation_timestamp.
    """

    if not isinstance(
        policy,
        PerformanceCompensationLifecyclePolicy,
    ):
        raise TypeError(
            "policy must be PerformanceCompensationLifecyclePolicy"
        )

    if not isinstance(status, CrystallizationStatus):
        raise TypeError(
            "status must be CrystallizationStatus"
        )

    period_start_dt = _parse_canonical_utc_timestamp(
        "period_start",
        period_start,
    )
    period_end_dt = _parse_canonical_utc_timestamp(
        "period_end",
        period_end,
    )
    _parse_canonical_utc_timestamp("assessed_at", assessed_at)

    if period_end_dt <= period_start_dt:
        raise ValueError(
            "period_end must be after period_start"
        )

    policy_from = _parse_canonical_utc_timestamp(
        "effective_from",
        policy.effective_from,
    )

    if period_end_dt <= policy_from:
        raise PerformanceCrystallizationIneligibleError(
            "assessment period is outside policy effective window"
        )

    if policy.effective_to is not None:
        policy_to = _parse_canonical_utc_timestamp(
            "effective_to",
            policy.effective_to,
        )
        if period_start_dt >= policy_to:
            raise PerformanceCrystallizationIneligibleError(
                "assessment period is outside policy effective window"
            )

    seen_trade_ids: set[str] = set()
    total = Decimal("0")

    for entitlement in entitlements:
        if not isinstance(
            entitlement,
            ShadowCompensationEntitlement,
        ):
            raise TypeError(
                "entitlements must be ShadowCompensationEntitlement"
            )

        if entitlement.terms_id != policy.terms_id:
            raise PerformanceCrystallizationIneligibleError(
                "entitlement terms_id does not match policy"
            )

        if entitlement.currency != policy.currency:
            raise PerformanceCrystallizationIneligibleError(
                "entitlement currency does not match policy"
            )

        if entitlement.trade_id in seen_trade_ids:
            raise PerformanceCrystallizationIneligibleError(
                "duplicate entitlement trade_id"
            )

        seen_trade_ids.add(entitlement.trade_id)

        amount = _require_finite_decimal(
            "shadow_compensation_amount",
            entitlement.shadow_compensation_amount,
        )

        if amount < Decimal("0"):
            raise PerformanceCrystallizationIneligibleError(
                "shadow_compensation_amount cannot be negative"
            )

        total += amount

    if status == CrystallizationStatus.ELIGIBLE:
        crystallizable_amount = total
    else:
        crystallizable_amount = Decimal("0")

    return CrystallizationAssessment(
        policy_id=policy.policy_id,
        terms_id=policy.terms_id,
        currency=policy.currency,
        period_start=period_start,
        period_end=period_end,
        assessed_at=assessed_at,
        shadow_entitlement_total=total,
        crystallizable_amount=crystallizable_amount,
        status=status,
        evidence_refs=evidence_refs,
    )

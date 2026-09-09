from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Sequence, Tuple

from backend.commercialization.final_fee_settlement_readiness import (
    CommercialFinalFeeSettlementReadiness,
)
from backend.commercialization.settlement_readiness import (
    CommercialSettlementReadiness,
    SettlementReadinessStatus,
)


class BillableObligationError(ValueError):
    """Base COM-002G billable-obligation contract error."""


class BillableObligationIneligibleError(BillableObligationError):
    """Raised when a billable obligation cannot be established."""


class BillableObligationStatus(str, Enum):
    """
    Explicit pre-accounting billable recognition for a crystallized
    commercial period that has passed COM-002F readiness.

    Deliberately excludes invoice/receivable/money-state vocabulary
    such as INVOICED, RECEIVABLE, DUE, OVERDUE, PAID, COLLECTED,
    SETTLED, VOID, or CREDITED.
    """

    NOT_BILLABLE = "NOT_BILLABLE"
    BILLABLE = "BILLABLE"
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
    Localized COM-002G datetime rule.

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
class CommercialBillableObligation:
    """
    Immutable pre-accounting billable recognition for one
    commercial period sourced from final-fee or legacy readiness.

    Keyed one-to-one with COM-002F readiness / COM-002E period by:
    (policy_id, period_start, period_end)

    BILLABLE means only that a READY crystallized amount has been
    explicitly recognized as billable. It does not create an invoice,
    receivable, due amount, tax consequence, ledger posting, payment,
    collection, debit, transfer, withdrawal, or execution.
    """

    policy_id: str
    terms_id: str
    currency: str
    period_start: str
    period_end: str
    billable_amount: Decimal
    recognized_at: str
    status: BillableObligationStatus
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
            "recognized_at",
            self.recognized_at,
        )

        if period_end <= period_start:
            raise ValueError(
                "period_end must be after period_start"
            )

        amount = _require_finite_decimal(
            "billable_amount",
            self.billable_amount,
        )

        if amount < Decimal("0"):
            raise ValueError(
                "billable_amount cannot be negative"
            )

        if not isinstance(self.status, BillableObligationStatus):
            raise TypeError(
                "status must be BillableObligationStatus"
            )

        _require_evidence_refs(self.evidence_refs)

    @property
    def invoice_creation_allowed(self) -> bool:
        return False

    @property
    def receivable_recognition_allowed(self) -> bool:
        return False

    @property
    def ledger_posting_allowed(self) -> bool:
        return False

    @property
    def revenue_recognition_allowed(self) -> bool:
        return False

    @property
    def tax_calculation_allowed(self) -> bool:
        return False

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
    def payment_initiation_allowed(self) -> bool:
        return False

    @property
    def money_movement_allowed(self) -> bool:
        return False

    @property
    def broker_withdrawal_allowed(self) -> bool:
        return False

    @property
    def execution_authority(self) -> bool:
        return False


def build_billable_obligation(
    readiness: CommercialSettlementReadiness | CommercialFinalFeeSettlementReadiness,
    status: BillableObligationStatus,
    recognized_at: str,
    evidence_refs: Tuple[str, ...],
) -> CommercialBillableObligation:
    """
    Fail-closed COM-002G billable-obligation builder.

    Copies the final selected fee from COM-002X readiness, or legacy
    crystallized economics from COM-002F readiness. The final fee is never
    recalculated or added to any other amount. The canonical period key
    links persisted obligations back to readiness and its final selection.
    Does not recalculate compensation and does not infer billable
    gates. BILLABLE requires SettlementReadinessStatus.READY.
    """

    if not isinstance(
        readiness, (CommercialSettlementReadiness, CommercialFinalFeeSettlementReadiness),
    ):
        raise TypeError(
            "readiness must be CommercialSettlementReadiness or CommercialFinalFeeSettlementReadiness"
        )

    if not isinstance(status, BillableObligationStatus):
        raise TypeError(
            "status must be BillableObligationStatus"
        )

    _parse_canonical_utc_timestamp("recognized_at", recognized_at)
    _require_evidence_refs(evidence_refs)

    if status == BillableObligationStatus.BILLABLE and (
        readiness.status != SettlementReadinessStatus.READY
    ):
        raise BillableObligationIneligibleError(
            "BILLABLE requires READY settlement readiness"
        )

    return CommercialBillableObligation(
        policy_id=readiness.policy_id,
        terms_id=readiness.terms_id,
        currency=readiness.currency,
        period_start=readiness.period_start,
        period_end=readiness.period_end,
        billable_amount=(
            readiness.selected_fee_amount
            if isinstance(readiness, CommercialFinalFeeSettlementReadiness)
            else readiness.crystallizable_amount
        ),
        recognized_at=recognized_at,
        status=status,
        evidence_refs=evidence_refs,
    )

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Tuple

from backend.commercialization.final_fee_selection import CommercialFinalFeeSelection
from backend.commercialization.settlement_readiness import (
    SettlementReadinessStatus,
    _parse_canonical_utc_timestamp,
    _require_evidence_refs,
)


@dataclass(frozen=True, slots=True)
class CommercialFinalFeeSettlementReadiness:
    """COM-002X readiness for the selected commercial fee, not crystallization.

    Embedding the immutable source prevents independent period, currency,
    identity or amount overrides. READY is an explicit commercial decision
    permitting billable-obligation processing only. No payment, collection,
    invoice issuance, receivable recognition or posting authority is granted.
    """

    selection: CommercialFinalFeeSelection
    status: SettlementReadinessStatus
    assessed_at: str
    evidence_refs: Tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.selection, CommercialFinalFeeSelection):
            raise TypeError("selection must be CommercialFinalFeeSelection")
        if not isinstance(self.status, SettlementReadinessStatus):
            raise TypeError("status must be SettlementReadinessStatus")
        _parse_canonical_utc_timestamp("assessed_at", self.assessed_at)
        if not isinstance(self.evidence_refs, tuple):
            raise TypeError("evidence_refs must be an immutable tuple")
        _require_evidence_refs(self.evidence_refs)

    @property
    def final_fee_selection_id(self) -> str:
        return self.selection.fee_selection_id

    @property
    def policy_id(self) -> str:
        return self.selection.policy_id

    @property
    def terms_id(self) -> str:
        return self.selection.terms_id

    @property
    def currency(self) -> str:
        return self.selection.billing_currency

    @property
    def period_start(self) -> str:
        return self.selection.period_start

    @property
    def period_end(self) -> str:
        return self.selection.period_end

    @property
    def selected_fee_amount(self) -> Decimal:
        return self.selection.selected_fee_amount

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


def build_final_fee_settlement_readiness(
    selection: CommercialFinalFeeSelection,
    status: SettlementReadinessStatus,
    assessed_at: str,
    evidence_refs: Tuple[str, ...],
) -> CommercialFinalFeeSettlementReadiness:
    """Attach an explicit readiness decision; copy the selected source exactly.

    No economics are calculated here. Persistence verifies this source against
    the canonical stored selection before accepting a readiness record.
    """
    return CommercialFinalFeeSettlementReadiness(selection, status, assessed_at, evidence_refs)

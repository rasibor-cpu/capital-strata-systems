from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Optional

from backend.app.persistence.services.persistence_service import PersistenceService
from backend.commercialization.trial_contract import (
    CommercialAgreementSnapshot,
    TrialCancellation,
    TrialContractError,
    TrialEnrollment,
)


def _parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise TrialContractError("timestamp must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _canonical_z(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class TrialContractEnrollmentService:
    """Creates immutable trial enrollment/cancellation evidence from governing terms."""

    def __init__(self, persistence_service: Optional[PersistenceService] = None) -> None:
        self._service = persistence_service or PersistenceService()

    def load_agreement(
        self,
        agreement_id: str,
        agreement_version: str,
    ) -> CommercialAgreementSnapshot:
        row = self._service.trial_contracts.get_agreement(
            agreement_id,
            agreement_version,
        )
        if row is None:
            raise TrialContractError("governing commercial agreement is missing")
        return CommercialAgreementSnapshot(
            agreement_id=row["agreement_id"],
            agreement_version=row["agreement_version"],
            jurisdiction_code=row["jurisdiction_code"],
            pricing_plan_id=row["pricing_plan_id"],
            pricing_summary=row["pricing_summary"],
            trial_duration_days=int(row["trial_duration_days"]),
            automatic_conversion_disclosure=row["automatic_conversion_disclosure"],
            effective_from=row["effective_from"],
            evidence_refs=tuple(json.loads(row["evidence_refs_json"])),
        )

    def enroll(
        self,
        *,
        customer_id: str,
        account_reference: str,
        agreement_id: str,
        agreement_version: str,
        accepted_at: str,
        displayed_pricing_summary: str,
        displayed_conversion_disclosure: str,
        acceptance_audit_reference: str,
        evidence_refs: tuple[str, ...],
    ) -> TrialEnrollment:
        agreement = self.load_agreement(agreement_id, agreement_version)

        if displayed_pricing_summary != agreement.pricing_summary:
            raise TrialContractError("displayed pricing does not match governing agreement")
        if displayed_conversion_disclosure != agreement.automatic_conversion_disclosure:
            raise TrialContractError(
                "displayed automatic-conversion disclosure does not match governing agreement"
            )

        accepted = _parse_utc(accepted_at)
        effective_from = _parse_utc(agreement.effective_from)
        if accepted < effective_from:
            raise TrialContractError("agreement is not yet effective")

        trial_start = accepted
        trial_expires = trial_start + timedelta(days=agreement.trial_duration_days)

        enrollment = TrialEnrollment(
            customer_id=customer_id,
            account_reference=account_reference,
            agreement_id=agreement.agreement_id,
            agreement_version=agreement.agreement_version,
            pricing_plan_id=agreement.pricing_plan_id,
            accepted_at=_canonical_z(accepted),
            trial_start_at=_canonical_z(trial_start),
            trial_expires_at=_canonical_z(trial_expires),
            displayed_pricing_summary=displayed_pricing_summary,
            displayed_conversion_disclosure=displayed_conversion_disclosure,
            acceptance_audit_reference=acceptance_audit_reference,
            evidence_refs=evidence_refs,
        )
        self._service.trial_contracts.create_enrollment(enrollment)
        return enrollment

    def cancel(
        self,
        *,
        customer_id: str,
        account_reference: str,
        canceled_at: str,
        cancellation_audit_reference: str,
        evidence_refs: tuple[str, ...],
    ) -> TrialCancellation:
        cancellation = TrialCancellation(
            customer_id=customer_id,
            account_reference=account_reference,
            canceled_at=_canonical_z(_parse_utc(canceled_at)),
            cancellation_audit_reference=cancellation_audit_reference,
            evidence_refs=evidence_refs,
        )
        self._service.trial_contracts.create_cancellation(cancellation)
        return cancellation

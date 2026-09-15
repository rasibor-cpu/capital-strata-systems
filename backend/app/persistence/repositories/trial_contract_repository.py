from __future__ import annotations

import json
from typing import Any

from backend.app.persistence.repositories.base_repository import BaseRepository
from backend.commercialization.trial_contract import (
    CommercialAgreementSnapshot,
    TrialCancellation,
    TrialEnrollment,
)


class TrialContractRepository(BaseRepository):
    """Append-only persistence for commercial trial contract evidence."""

    def create_agreement(self, agreement: CommercialAgreementSnapshot) -> None:
        self.execute(
            """
            INSERT INTO commercial_agreement_snapshots (
                agreement_id,
                agreement_version,
                jurisdiction_code,
                pricing_plan_id,
                pricing_summary,
                trial_duration_days,
                automatic_conversion_disclosure,
                effective_from,
                evidence_refs_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                agreement.agreement_id,
                agreement.agreement_version,
                agreement.jurisdiction_code,
                agreement.pricing_plan_id,
                agreement.pricing_summary,
                agreement.trial_duration_days,
                agreement.automatic_conversion_disclosure,
                agreement.effective_from,
                json.dumps(list(agreement.evidence_refs), separators=(",", ":")),
            ),
        )

    def create_enrollment(self, enrollment: TrialEnrollment) -> None:
        self.execute(
            """
            INSERT INTO commercial_trial_enrollments (
                customer_id,
                account_reference,
                agreement_id,
                agreement_version,
                pricing_plan_id,
                accepted_at,
                trial_start_at,
                trial_expires_at,
                displayed_pricing_summary,
                displayed_conversion_disclosure,
                acceptance_audit_reference,
                evidence_refs_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                enrollment.customer_id,
                enrollment.account_reference,
                enrollment.agreement_id,
                enrollment.agreement_version,
                enrollment.pricing_plan_id,
                enrollment.accepted_at,
                enrollment.trial_start_at,
                enrollment.trial_expires_at,
                enrollment.displayed_pricing_summary,
                enrollment.displayed_conversion_disclosure,
                enrollment.acceptance_audit_reference,
                json.dumps(list(enrollment.evidence_refs), separators=(",", ":")),
            ),
        )

    def create_cancellation(self, cancellation: TrialCancellation) -> None:
        self.execute(
            """
            INSERT INTO commercial_trial_cancellations (
                customer_id,
                account_reference,
                canceled_at,
                cancellation_audit_reference,
                evidence_refs_json
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                cancellation.customer_id,
                cancellation.account_reference,
                cancellation.canceled_at,
                cancellation.cancellation_audit_reference,
                json.dumps(list(cancellation.evidence_refs), separators=(",", ":")),
            ),
        )

    def get_agreement(
        self,
        agreement_id: str,
        agreement_version: str,
    ) -> dict[str, Any] | None:
        row = self.fetch_one(
            """
            SELECT *
            FROM commercial_agreement_snapshots
            WHERE agreement_id = ? AND agreement_version = ?
            """,
            (agreement_id, agreement_version),
        )
        return dict(row) if row is not None else None

    def get_enrollment(
        self,
        *,
        customer_id: str,
        account_reference: str,
        agreement_id: str,
        agreement_version: str,
    ) -> dict[str, Any] | None:
        row = self.fetch_one(
            """
            SELECT *
            FROM commercial_trial_enrollments
            WHERE customer_id = ?
              AND account_reference = ?
              AND agreement_id = ?
              AND agreement_version = ?
            """,
            (
                customer_id,
                account_reference,
                agreement_id,
                agreement_version,
            ),
        )
        return dict(row) if row is not None else None

    def latest_cancellation(
        self,
        *,
        customer_id: str,
        account_reference: str,
    ) -> dict[str, Any] | None:
        row = self.fetch_one(
            """
            SELECT *
            FROM commercial_trial_cancellations
            WHERE customer_id = ? AND account_reference = ?
            ORDER BY canceled_at DESC, cancellation_id DESC
            LIMIT 1
            """,
            (customer_id, account_reference),
        )
        return dict(row) if row is not None else None

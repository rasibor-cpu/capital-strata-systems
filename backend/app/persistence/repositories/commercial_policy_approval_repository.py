from __future__ import annotations

import json
from typing import Any

from backend.app.persistence.repositories.base_repository import BaseRepository
from backend.commercialization.independent_platform_charge_policy import (
    IndependentPlatformChargePolicy,
)
from backend.commercialization.jurisdiction_service_mode import (
    JurisdictionServiceModeApproval,
)


class CommercialPolicyApprovalRepository(BaseRepository):
    """Append-only approval evidence for pricing and jurisdiction service modes."""

    def create_independent_charge_policy(
        self,
        policy: IndependentPlatformChargePolicy,
    ) -> None:
        self.execute(
            """
            INSERT INTO independent_platform_charge_policies (
                policy_id, model, rate, currency, approved_for_production,
                approved_at, approval_reference, evidence_refs_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                policy.policy_id,
                policy.model.value,
                str(policy.rate),
                policy.currency,
                int(policy.approved_for_production),
                policy.approved_at,
                policy.approval_reference,
                json.dumps(list(policy.evidence_refs), separators=(",", ":")),
            ),
        )

    def get_independent_charge_policy(
        self,
        policy_id: str,
    ) -> dict[str, Any] | None:
        row = self.fetch_one(
            "SELECT * FROM independent_platform_charge_policies WHERE policy_id = ?",
            (policy_id,),
        )
        return dict(row) if row is not None else None

    def create_jurisdiction_mode_approval(
        self,
        record: JurisdictionServiceModeApproval,
    ) -> None:
        self.execute(
            """
            INSERT INTO jurisdiction_service_mode_approvals (
                approval_id, jurisdiction_code, service_mode, status,
                approved_at, approval_reference, evidence_refs_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.approval_id,
                record.jurisdiction_code,
                record.service_mode.value,
                record.status.value,
                record.approved_at,
                record.approval_reference,
                json.dumps(list(record.evidence_refs), separators=(",", ":")),
            ),
        )

    def latest_jurisdiction_mode_approval(
        self,
        jurisdiction_code: str,
        service_mode: str,
    ) -> dict[str, Any] | None:
        row = self.fetch_one(
            """
            SELECT *
            FROM jurisdiction_service_mode_approvals
            WHERE jurisdiction_code = ? AND service_mode = ?
            ORDER BY created_at DESC, approval_id DESC
            LIMIT 1
            """,
            (jurisdiction_code, service_mode),
        )
        return dict(row) if row is not None else None

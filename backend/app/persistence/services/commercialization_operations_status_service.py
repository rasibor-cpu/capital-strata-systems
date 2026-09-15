from __future__ import annotations

import json
from typing import Any, Optional

from backend.app.persistence.services.commercialization_release_status_service import (
    CommercializationReleaseStatusService,
)
from backend.app.persistence.services.persistence_service import PersistenceService
from backend.commercialization.commercialization_uat import (
    CommercializationUatResult,
    CommercializationUatScenario,
    UatResultStatus,
    assess_commercialization_uat,
)
from backend.commercialization.jurisdiction_service_mode import ServiceMode
from backend.commercialization.launch_evidence_dossier import (
    LaunchEvidenceCategory,
    LaunchEvidenceItem,
    assess_launch_dossier,
)


class CommercializationOperationsStatusService:
    """Read-only operator view across launch evidence and blockers."""

    def __init__(self, persistence_service: Optional[PersistenceService] = None) -> None:
        self._service = persistence_service or PersistenceService()

    def build_status(
        self,
        *,
        customer_id: str,
        account_reference: str,
        agreement_id: str,
        agreement_version: str,
        jurisdiction_code: str,
        assessed_at: str,
        uat_run_id: str,
        dossier_id: str,
    ) -> dict[str, Any]:
        release = CommercializationReleaseStatusService(self._service).assess(
            customer_id=customer_id,
            account_reference=account_reference,
            agreement_id=agreement_id,
            agreement_version=agreement_version,
            jurisdiction_code=jurisdiction_code,
            assessed_at=assessed_at,
        )

        uat_results = []
        for row in self._service.commercialization_uat.list_run(uat_run_id):
            uat_results.append(
                CommercializationUatResult(
                    run_id=row["run_id"],
                    scenario=CommercializationUatScenario(row["scenario"]),
                    status=UatResultStatus(row["status"]),
                    executed_at=row["executed_at"],
                    environment_reference=row["environment_reference"],
                    evidence_refs=tuple(json.loads(row["evidence_refs_json"])),
                )
            )
        uat = assess_commercialization_uat(tuple(uat_results))

        dossier_items = []
        for row in self._service.launch_operations.list_launch_evidence(dossier_id):
            dossier_items.append(
                LaunchEvidenceItem(
                    category=LaunchEvidenceCategory(row["category"]),
                    evidence_reference=row["evidence_reference"],
                    approved=bool(row["approved"]),
                )
            )
        dossier = assess_launch_dossier(tuple(dossier_items))

        modes = {}
        for mode in ServiceMode:
            row = self._service.commercial_policy_approvals.latest_jurisdiction_mode_approval(
                jurisdiction_code,
                mode.value,
            )
            modes[mode.value] = (
                {
                    "status": row["status"],
                    "approval_id": row["approval_id"],
                    "approval_reference": row["approval_reference"],
                }
                if row is not None
                else {
                    "status": "MISSING",
                    "approval_id": None,
                    "approval_reference": None,
                }
            )

        notifications = self._service.launch_operations.list_notification_intents(
            customer_id,
            account_reference,
        )

        return {
            "production_commercial_ready": release.production_ready,
            "release_reason_codes": list(release.reason_codes),
            "validation_id": release.validation_id,
            "validated_commit_sha": release.validated_commit_sha,
            "uat_complete": uat.complete,
            "uat_missing_scenarios": [s.value for s in uat.missing_scenarios],
            "uat_failed_scenarios": [s.value for s in uat.failed_scenarios],
            "uat_blocked_scenarios": [s.value for s in uat.blocked_scenarios],
            "launch_dossier_complete": dossier.complete,
            "launch_dossier_missing_categories": [
                c.value for c in dossier.missing_categories
            ],
            "launch_dossier_unapproved_categories": [
                c.value for c in dossier.unapproved_categories
            ],
            "jurisdiction_service_modes": modes,
            "notification_intent_count": len(notifications),
            "notification_intents": notifications,
            "payment_execution_available_from_this_view": False,
            "money_movement_available_from_this_view": False,
            "trading_execution_authority": False,
            "read_only": True,
        }

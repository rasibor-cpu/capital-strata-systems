from __future__ import annotations

from typing import Any, Optional

from backend.app.persistence.services.persistence_service import PersistenceService
from backend.commercialization.launch_evidence_dossier import (
    LaunchEvidenceCategory,
    LaunchEvidenceItem,
    assess_launch_dossier,
)


class LaunchDossierExportService:
    """Read-only canonical launch dossier export."""

    def __init__(self, persistence_service: Optional[PersistenceService] = None) -> None:
        self._service = persistence_service or PersistenceService()

    def export(self, *, dossier_id: str) -> dict[str, Any]:
        rows = self._service.launch_operations.list_launch_evidence(dossier_id)
        items = tuple(
            LaunchEvidenceItem(
                category=LaunchEvidenceCategory(row["category"]),
                evidence_reference=row["evidence_reference"],
                approved=bool(row["approved"]),
            )
            for row in rows
        )
        assessment = assess_launch_dossier(items)
        return {
            "dossier_id": dossier_id,
            "complete": assessment.complete,
            "missing_categories": [
                category.value for category in assessment.missing_categories
            ],
            "unapproved_categories": [
                category.value for category in assessment.unapproved_categories
            ],
            "evidence": [
                {
                    "category": item.category.value,
                    "evidence_reference": item.evidence_reference,
                    "approved": item.approved,
                }
                for item in items
            ],
            "read_only": True,
        }

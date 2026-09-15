from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Tuple


class LaunchEvidenceCategory(str, Enum):
    APPROVED_CUSTOMER_AGREEMENT = "APPROVED_CUSTOMER_AGREEMENT"
    JURISDICTION_LEGAL_REVIEW = "JURISDICTION_LEGAL_REVIEW"
    TECHNICAL_VALIDATION = "TECHNICAL_VALIDATION"
    SECURITY_CERTIFICATION = "SECURITY_CERTIFICATION"
    RECONCILIATION_CERTIFICATION = "RECONCILIATION_CERTIFICATION"
    PAYMENT_PROVIDER_AUTHORITY = "PAYMENT_PROVIDER_AUTHORITY"
    PRODUCTION_UAT = "PRODUCTION_UAT"
    ROLLBACK_PLAN = "ROLLBACK_PLAN"
    OWNER_SIGNOFF = "OWNER_SIGNOFF"


REQUIRED_LAUNCH_EVIDENCE = tuple(LaunchEvidenceCategory)


@dataclass(frozen=True, slots=True)
class LaunchEvidenceItem:
    category: LaunchEvidenceCategory
    evidence_reference: str
    approved: bool

    def __post_init__(self) -> None:
        if not isinstance(self.category, LaunchEvidenceCategory):
            raise TypeError("category must be LaunchEvidenceCategory")
        if not self.evidence_reference or self.evidence_reference != self.evidence_reference.strip():
            raise ValueError("evidence_reference is required and must be canonical")


@dataclass(frozen=True, slots=True)
class LaunchDossierAssessment:
    complete: bool
    missing_categories: Tuple[LaunchEvidenceCategory, ...]
    unapproved_categories: Tuple[LaunchEvidenceCategory, ...]


def assess_launch_dossier(
    items: Tuple[LaunchEvidenceItem, ...],
) -> LaunchDossierAssessment:
    by_category = {item.category: item for item in items}
    missing = tuple(
        category for category in REQUIRED_LAUNCH_EVIDENCE
        if category not in by_category
    )
    unapproved = tuple(
        category for category, item in by_category.items()
        if not item.approved
    )
    return LaunchDossierAssessment(
        complete=not missing and not unapproved,
        missing_categories=missing,
        unapproved_categories=unapproved,
    )

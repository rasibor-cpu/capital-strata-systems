from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping, Tuple


class ProductionEvidenceCategory(str, Enum):
    CUSTOMER_AGREEMENT = "CUSTOMER_AGREEMENT"
    JURISDICTION_LEGAL_REVIEW = "JURISDICTION_LEGAL_REVIEW"
    SERVICE_MODE_APPROVALS = "SERVICE_MODE_APPROVALS"
    PAYMENT_PROVIDER = "PAYMENT_PROVIDER"
    PAYMENT_COLLECTION_AUTHORITY = "PAYMENT_COLLECTION_AUTHORITY"
    NOTIFICATION_PROVIDER = "NOTIFICATION_PROVIDER"
    NOTIFICATION_POLICY = "NOTIFICATION_POLICY"
    SECURITY_OPERATIONS = "SECURITY_OPERATIONS"
    BACKUP_RESTORE = "BACKUP_RESTORE"
    INCIDENT_TABLETOP = "INCIDENT_TABLETOP"
    PRODUCTION_UAT = "PRODUCTION_UAT"
    RECONCILIATION = "RECONCILIATION"
    OWNER_SIGNOFF = "OWNER_SIGNOFF"


REQUIRED_PRODUCTION_EVIDENCE = tuple(ProductionEvidenceCategory)


@dataclass(frozen=True, slots=True)
class ProductionEvidenceValidation:
    valid_for_review: bool
    missing_categories: Tuple[str, ...]
    invalid_reasons: Tuple[str, ...]
    package_id: str | None
    jurisdiction_code: str | None
    agreement_id: str | None
    agreement_version: str | None

    @property
    def production_authorized(self) -> bool:
        # Documentary validation never authorizes production.
        return False

    @property
    def money_movement_authorized(self) -> bool:
        return False

    @property
    def trading_execution_authority(self) -> bool:
        return False


def _canonical_text(value: Any) -> str:
    return str(value or "").strip()


def _is_test_reference(value: str) -> bool:
    normalized = value.upper()
    return (
        "TEST_ONLY" in normalized
        or "SANDBOX" in normalized
        or normalized.startswith("TEST:")
    )


def _validate_evidence_item(
    category: ProductionEvidenceCategory,
    item: Any,
    *,
    jurisdiction_code: str,
    agreement_id: str,
    agreement_version: str,
) -> list[str]:
    reasons: list[str] = []
    prefix = category.value

    if not isinstance(item, Mapping):
        return [f"{prefix}:ITEM_MUST_BE_OBJECT"]

    status = _canonical_text(item.get("status")).upper()
    if status != "APPROVED":
        reasons.append(f"{prefix}:STATUS_NOT_APPROVED")

    reference = _canonical_text(item.get("evidence_reference"))
    if not reference:
        reasons.append(f"{prefix}:EVIDENCE_REFERENCE_MISSING")
    elif _is_test_reference(reference):
        reasons.append(f"{prefix}:TEST_OR_SANDBOX_EVIDENCE_FORBIDDEN")

    reviewer = _canonical_text(
        item.get("reviewer_reference")
        or item.get("provider_reference")
        or item.get("signer_reference")
    )
    if not reviewer:
        reasons.append(f"{prefix}:REVIEWER_OR_AUTHORITY_REFERENCE_MISSING")
    elif _is_test_reference(reviewer):
        reasons.append(f"{prefix}:TEST_OR_SANDBOX_AUTHORITY_FORBIDDEN")

    approved_at = _canonical_text(
        item.get("approved_at")
        or item.get("reviewed_at")
        or item.get("signed_at")
        or item.get("completed_at")
    )
    if not approved_at:
        reasons.append(f"{prefix}:APPROVAL_TIMESTAMP_MISSING")

    scoped_jurisdiction = _canonical_text(item.get("jurisdiction_code"))
    if scoped_jurisdiction and scoped_jurisdiction != jurisdiction_code:
        reasons.append(f"{prefix}:JURISDICTION_SCOPE_MISMATCH")

    scoped_agreement = _canonical_text(item.get("agreement_id"))
    if scoped_agreement and scoped_agreement != agreement_id:
        reasons.append(f"{prefix}:AGREEMENT_SCOPE_MISMATCH")

    scoped_version = _canonical_text(item.get("agreement_version"))
    if scoped_version and scoped_version != agreement_version:
        reasons.append(f"{prefix}:AGREEMENT_VERSION_SCOPE_MISMATCH")

    if category in {
        ProductionEvidenceCategory.PAYMENT_PROVIDER,
        ProductionEvidenceCategory.NOTIFICATION_PROVIDER,
    }:
        environment = _canonical_text(item.get("environment")).lower()
        if environment != "production":
            reasons.append(f"{prefix}:PRODUCTION_ENVIRONMENT_REQUIRED")
        provider_id = _canonical_text(item.get("provider_id"))
        if not provider_id:
            reasons.append(f"{prefix}:PROVIDER_ID_MISSING")

    if category == ProductionEvidenceCategory.SERVICE_MODE_APPROVALS:
        modes = item.get("modes")
        if not isinstance(modes, Mapping):
            reasons.append(f"{prefix}:MODES_OBJECT_MISSING")
        else:
            for mode in ("DISCOVER", "CONFIRM", "AUTO"):
                mode_status = _canonical_text(modes.get(mode)).upper()
                if mode_status not in {
                    "APPROVED",
                    "RESTRICTED",
                    "PROHIBITED",
                }:
                    reasons.append(
                        f"{prefix}:{mode}_DETERMINATION_MISSING"
                    )

    if category == ProductionEvidenceCategory.SECURITY_OPERATIONS:
        controls = item.get("controls")
        required = (
            "secrets_management",
            "tls_transport",
            "access_control",
            "audit_logging",
            "monitoring_alerting",
            "backup_restore",
            "rollback",
            "reconciliation",
            "incident_response",
            "dependency_vulnerability_review",
        )
        if not isinstance(controls, Mapping):
            reasons.append(f"{prefix}:CONTROLS_OBJECT_MISSING")
        else:
            for control in required:
                if controls.get(control) is not True:
                    reasons.append(
                        f"{prefix}:CONTROL_NOT_VERIFIED:{control}"
                    )

    if category == ProductionEvidenceCategory.OWNER_SIGNOFF:
        signed_by = _canonical_text(item.get("signed_by"))
        decision = _canonical_text(item.get("decision")).upper()
        if not signed_by:
            reasons.append(f"{prefix}:SIGNED_BY_MISSING")
        if decision != "APPROVE":
            reasons.append(f"{prefix}:DECISION_NOT_APPROVE")

    return reasons


def validate_production_evidence_package(
    package: Mapping[str, Any],
) -> ProductionEvidenceValidation:
    if not isinstance(package, Mapping):
        raise TypeError("package must be a mapping")

    package_id = _canonical_text(package.get("package_id")) or None
    jurisdiction_code = (
        _canonical_text(package.get("jurisdiction_code")) or None
    )
    agreement_id = _canonical_text(package.get("agreement_id")) or None
    agreement_version = (
        _canonical_text(package.get("agreement_version")) or None
    )

    invalid: list[str] = []
    if not package_id:
        invalid.append("PACKAGE_ID_MISSING")
    elif _is_test_reference(package_id):
        invalid.append("TEST_OR_SANDBOX_PACKAGE_ID_FORBIDDEN")
    if not jurisdiction_code:
        invalid.append("JURISDICTION_CODE_MISSING")
    if not agreement_id:
        invalid.append("AGREEMENT_ID_MISSING")
    if not agreement_version:
        invalid.append("AGREEMENT_VERSION_MISSING")

    evidence = package.get("evidence")
    if not isinstance(evidence, Mapping):
        evidence = {}
        invalid.append("EVIDENCE_OBJECT_MISSING")

    missing = tuple(
        category.value
        for category in REQUIRED_PRODUCTION_EVIDENCE
        if category.value not in evidence
    )

    if jurisdiction_code and agreement_id and agreement_version:
        for category in REQUIRED_PRODUCTION_EVIDENCE:
            if category.value in evidence:
                invalid.extend(
                    _validate_evidence_item(
                        category,
                        evidence[category.value],
                        jurisdiction_code=jurisdiction_code,
                        agreement_id=agreement_id,
                        agreement_version=agreement_version,
                    )
                )

    return ProductionEvidenceValidation(
        valid_for_review=not missing and not invalid,
        missing_categories=missing,
        invalid_reasons=tuple(invalid),
        package_id=package_id,
        jurisdiction_code=jurisdiction_code,
        agreement_id=agreement_id,
        agreement_version=agreement_version,
    )

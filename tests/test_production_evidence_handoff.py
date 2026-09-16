import json

from backend.commercialization.production_evidence_handoff import (
    ProductionEvidenceCategory,
    REQUIRED_PRODUCTION_EVIDENCE,
    validate_production_evidence_package,
)


def _item(**changes):
    value = {
        "status": "APPROVED",
        "evidence_reference": "evidence:external:1",
        "reviewer_reference": "authority:external:1",
        "approved_at": "2026-10-01T00:00:00Z",
        "jurisdiction_code": "CA-ON",
        "agreement_id": "AGR-PROD-1",
        "agreement_version": "v1",
    }
    value.update(changes)
    return value


def _package():
    evidence = {
        category.value: _item()
        for category in REQUIRED_PRODUCTION_EVIDENCE
    }
    evidence[ProductionEvidenceCategory.SERVICE_MODE_APPROVALS.value] = _item(
        modes={
            "DISCOVER": "APPROVED",
            "CONFIRM": "APPROVED",
            "AUTO": "RESTRICTED",
        }
    )
    evidence[ProductionEvidenceCategory.PAYMENT_PROVIDER.value] = _item(
        provider_id="PAYMENT-PROD-1",
        environment="production",
        provider_reference="provider:contract:1",
    )
    evidence[ProductionEvidenceCategory.NOTIFICATION_PROVIDER.value] = _item(
        provider_id="NOTIFY-PROD-1",
        environment="production",
        provider_reference="provider:notify:1",
    )
    evidence[ProductionEvidenceCategory.SECURITY_OPERATIONS.value] = _item(
        controls={
            "secrets_management": True,
            "tls_transport": True,
            "access_control": True,
            "audit_logging": True,
            "monitoring_alerting": True,
            "backup_restore": True,
            "rollback": True,
            "reconciliation": True,
            "incident_response": True,
            "dependency_vulnerability_review": True,
        }
    )
    evidence[ProductionEvidenceCategory.OWNER_SIGNOFF.value] = _item(
        signed_by="release-owner",
        signer_reference="owner:signoff:1",
        signed_at="2026-10-01T00:00:00Z",
        decision="APPROVE",
    )
    return {
        "package_id": "PROD-EVIDENCE-001",
        "jurisdiction_code": "CA-ON",
        "agreement_id": "AGR-PROD-1",
        "agreement_version": "v1",
        "evidence": evidence,
    }


def test_complete_external_package_is_valid_for_review_but_not_authorizing():
    result = validate_production_evidence_package(_package())
    assert result.valid_for_review is True
    assert result.missing_categories == ()
    assert result.invalid_reasons == ()
    assert result.production_authorized is False
    assert result.money_movement_authorized is False
    assert result.trading_execution_authority is False


def test_missing_category_blocks_review():
    package = _package()
    del package["evidence"][
        ProductionEvidenceCategory.OWNER_SIGNOFF.value
    ]
    result = validate_production_evidence_package(package)
    assert result.valid_for_review is False
    assert "OWNER_SIGNOFF" in result.missing_categories


def test_test_only_or_sandbox_evidence_is_rejected():
    package = _package()
    package["evidence"][
        ProductionEvidenceCategory.PAYMENT_PROVIDER.value
    ]["environment"] = "sandbox"
    package["evidence"][
        ProductionEvidenceCategory.PAYMENT_PROVIDER.value
    ]["evidence_reference"] = "TEST_ONLY:sandbox-provider"
    result = validate_production_evidence_package(package)
    assert result.valid_for_review is False
    assert any(
        "PAYMENT_PROVIDER:PRODUCTION_ENVIRONMENT_REQUIRED" == reason
        for reason in result.invalid_reasons
    )
    assert any(
        "PAYMENT_PROVIDER:TEST_OR_SANDBOX_EVIDENCE_FORBIDDEN"
        == reason
        for reason in result.invalid_reasons
    )


def test_scope_mismatch_is_rejected():
    package = _package()
    package["evidence"][
        ProductionEvidenceCategory.JURISDICTION_LEGAL_REVIEW.value
    ]["agreement_version"] = "v2"
    result = validate_production_evidence_package(package)
    assert result.valid_for_review is False
    assert (
        "JURISDICTION_LEGAL_REVIEW:AGREEMENT_VERSION_SCOPE_MISMATCH"
        in result.invalid_reasons
    )

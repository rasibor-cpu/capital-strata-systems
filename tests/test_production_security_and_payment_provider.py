from decimal import Decimal

import pytest

from backend.commercialization.payment_collection_provider import (
    DisabledPaymentCollectionProvider,
    PaymentCollectionRequest,
    PaymentProviderConfiguration,
    PaymentProviderStatus,
    assess_payment_collection_preflight,
)
from backend.commercialization.production_charging_gate import (
    ProductionChargingAssessment,
)
from backend.commercialization.production_security_certification import (
    ProductionSecurityOperationalCertification,
    SecurityOperationalApprovalStatus,
)


REFS = ("evidence:1",)


def _charging(allowed=True, reasons=()):
    return ProductionChargingAssessment(
        allowed=allowed,
        reason_codes=tuple(reasons),
        agreement_id="AGR-1",
        agreement_version="v1",
        jurisdiction_code="CA-ON",
    )


def test_security_certification_requires_every_control():
    record = ProductionSecurityOperationalCertification(
        certification_id="SEC-1",
        status=SecurityOperationalApprovalStatus.APPROVED,
        certified_at="2026-10-01T00:00:00Z",
        secrets_management_verified=True,
        tls_transport_verified=True,
        access_control_verified=True,
        audit_logging_verified=True,
        monitoring_alerting_verified=True,
        backup_restore_tested=True,
        rollback_tested=False,
        reconciliation_verified=True,
        incident_response_verified=True,
        dependency_vulnerability_reviewed=True,
        reviewer_reference="security:review",
        evidence_refs=REFS,
    )
    assert record.production_security_ready is False


def test_disabled_provider_blocks_preflight():
    provider = PaymentProviderConfiguration(
        provider_id="PAYMENTS-DISABLED",
        status=PaymentProviderStatus.DISABLED,
        environment="production",
        provider_account_reference=None,
        approval_reference=None,
        evidence_refs=REFS,
    )
    result = assess_payment_collection_preflight(
        charging_assessment=_charging(),
        provider=provider,
    )
    assert result.allowed is False
    assert "PAYMENT_PROVIDER_NOT_APPROVED" in result.reason_codes


def test_approved_provider_still_requires_green_charging_gate():
    provider = PaymentProviderConfiguration(
        provider_id="PROVIDER-1",
        status=PaymentProviderStatus.APPROVED,
        environment="production",
        provider_account_reference="provider:merchant",
        approval_reference="payments:counsel-approved",
        evidence_refs=REFS,
    )
    result = assess_payment_collection_preflight(
        charging_assessment=_charging(False, ("LEGAL_REVIEW_MISSING",)),
        provider=provider,
    )
    assert result.allowed is False
    assert "PRODUCTION_CHARGING_GATE_BLOCKED" in result.reason_codes
    assert "CHARGING_GATE:LEGAL_REVIEW_MISSING" in result.reason_codes


def test_disabled_adapter_never_moves_money_even_with_valid_request():
    request = PaymentCollectionRequest(
        collection_id="COLL-1",
        customer_id="CUST-1",
        account_reference="account:A",
        amount=Decimal("10"),
        currency="USD",
        idempotency_key="idem:1",
        invoice_reference="INV-1",
        evidence_refs=REFS,
    )
    with pytest.raises(RuntimeError, match="disabled"):
        DisabledPaymentCollectionProvider().collect(
            request,
            assess_payment_collection_preflight(
                charging_assessment=_charging(),
                provider=PaymentProviderConfiguration(
                    provider_id="PAYMENTS-DISABLED",
                    status=PaymentProviderStatus.DISABLED,
                    environment="production",
                    provider_account_reference=None,
                    approval_reference=None,
                    evidence_refs=REFS,
                ),
            ),
        )

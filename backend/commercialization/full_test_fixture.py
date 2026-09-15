from __future__ import annotations

import os
from decimal import Decimal

from backend.app.persistence.services.persistence_service import PersistenceService
from backend.commercialization.commercialization_release_status import (
    CommercializationTechnicalValidation,
)
from backend.commercialization.commercialization_uat import (
    CommercializationUatResult,
    REQUIRED_COMMERCIALIZATION_UAT_SCENARIOS,
    UatResultStatus,
)
from backend.commercialization.customer_notifications import (
    CustomerNotificationPolicy,
    CustomerNotificationType,
    build_notification_intent,
)
from backend.commercialization.independent_platform_charge_policy import (
    IndependentPlatformChargeModel,
    IndependentPlatformChargePolicy,
)
from backend.commercialization.jurisdiction_service_mode import (
    JurisdictionModeApprovalStatus,
    JurisdictionServiceModeApproval,
    ServiceMode,
)
from backend.commercialization.launch_evidence_dossier import (
    LaunchEvidenceItem,
    REQUIRED_LAUNCH_EVIDENCE,
)
from backend.commercialization.notification_delivery_provider import (
    NotificationChannel,
    NotificationProviderConfiguration,
    NotificationProviderStatus,
)
from backend.commercialization.payment_collection_provider import (
    PaymentProviderConfiguration,
    PaymentProviderStatus,
)
from backend.commercialization.production_charging_gate import (
    ApprovalStatus,
    JurisdictionLegalReview,
    PaymentCollectionAuthorityApproval,
    ProductionCommercializationCertification,
)
from backend.commercialization.production_security_certification import (
    ProductionSecurityOperationalCertification,
    SecurityOperationalApprovalStatus,
)
from backend.commercialization.trial_contract import (
    CommercialAgreementSnapshot,
    TrialEnrollment,
)


FULL_TEST_ENV_VAR = "CSS_FULL_TEST_MODE"
FULL_TEST_ENV_VALUE = "1"

TEST_CUSTOMER_ID = "TEST-CUST-001"
TEST_ACCOUNT_REFERENCE = "test:account:001"
TEST_AGREEMENT_ID = "TEST-AGR-001"
TEST_AGREEMENT_VERSION = "test-v1"
TEST_JURISDICTION = "TEST-JURISDICTION"
TEST_PAYMENT_PROVIDER_ID = "CSS-SANDBOX-PAYMENTS"
TEST_NOTIFICATION_PROVIDER_ID = "CSS-SANDBOX-NOTIFY"
TEST_UAT_RUN_ID = "FULL-TEST-UAT-001"
TEST_DOSSIER_ID = "FULL-TEST-DOSSIER-001"
TEST_VALIDATION_ID = "FULL-TEST-VALIDATION-001"
TEST_EVIDENCE = ("TEST_ONLY:synthetic-full-test-evidence",)


def _require_full_test_mode() -> None:
    if os.getenv(FULL_TEST_ENV_VAR) != FULL_TEST_ENV_VALUE:
        raise RuntimeError(
            "synthetic full-test fixtures require CSS_FULL_TEST_MODE=1"
        )


def seed_full_test_fixture(
    service: PersistenceService,
    *,
    validated_commit_sha: str,
    test_count: int,
) -> None:
    """Seed an isolated sandbox DB with synthetic test-only approvals.

    These records are deliberately marked TEST_ONLY and must never be used as
    production evidence.
    """

    _require_full_test_mode()

    agreement = CommercialAgreementSnapshot(
        agreement_id=TEST_AGREEMENT_ID,
        agreement_version=TEST_AGREEMENT_VERSION,
        jurisdiction_code=TEST_JURISDICTION,
        pricing_plan_id="TEST-PLAN-001",
        pricing_summary="TEST ONLY: 20% of qualifying new economic gain.",
        trial_duration_days=30,
        automatic_conversion_disclosure=(
            "TEST ONLY: sandbox trial converts after the synthetic expiry."
        ),
        effective_from="2026-01-01T00:00:00Z",
        evidence_refs=TEST_EVIDENCE,
    )
    service.trial_contracts.create_agreement(agreement)
    service.trial_contracts.create_enrollment(
        TrialEnrollment(
            customer_id=TEST_CUSTOMER_ID,
            account_reference=TEST_ACCOUNT_REFERENCE,
            agreement_id=TEST_AGREEMENT_ID,
            agreement_version=TEST_AGREEMENT_VERSION,
            pricing_plan_id=agreement.pricing_plan_id,
            accepted_at="2026-01-01T00:00:00Z",
            trial_start_at="2026-01-01T00:00:00Z",
            trial_expires_at="2026-01-31T00:00:00Z",
            displayed_pricing_summary=agreement.pricing_summary,
            displayed_conversion_disclosure=(
                agreement.automatic_conversion_disclosure
            ),
            acceptance_audit_reference="TEST_ONLY:acceptance",
            evidence_refs=TEST_EVIDENCE,
        )
    )

    approvals = service.production_charging_approvals
    approvals.create_legal_review(
        JurisdictionLegalReview(
            jurisdiction_code=TEST_JURISDICTION,
            agreement_id=TEST_AGREEMENT_ID,
            agreement_version=TEST_AGREEMENT_VERSION,
            status=ApprovalStatus.APPROVED,
            reviewed_at="2026-02-01T00:00:00Z",
            reviewer_reference="TEST_ONLY:synthetic-counsel",
            evidence_refs=TEST_EVIDENCE,
        )
    )
    approvals.create_certification(
        ProductionCommercializationCertification(
            certification_id="TEST-COM-CERT-001",
            agreement_id=TEST_AGREEMENT_ID,
            agreement_version=TEST_AGREEMENT_VERSION,
            jurisdiction_code=TEST_JURISDICTION,
            status=ApprovalStatus.APPROVED,
            certified_at="2026-02-01T00:00:00Z",
            reconciliation_verified=True,
            security_release_blockers_clear=True,
            charging_controls_verified=True,
            evidence_refs=TEST_EVIDENCE,
        )
    )
    approvals.create_payment_authority(
        PaymentCollectionAuthorityApproval(
            authority_id="TEST-PAY-AUTH-001",
            agreement_id=TEST_AGREEMENT_ID,
            agreement_version=TEST_AGREEMENT_VERSION,
            jurisdiction_code=TEST_JURISDICTION,
            status=ApprovalStatus.APPROVED,
            approved_at="2026-02-01T00:00:00Z",
            authority_reference="TEST_ONLY:synthetic-payment-authority",
            evidence_refs=TEST_EVIDENCE,
        )
    )

    service.production_infrastructure.create_security_certification(
        ProductionSecurityOperationalCertification(
            certification_id="TEST-SEC-CERT-001",
            status=SecurityOperationalApprovalStatus.APPROVED,
            certified_at="2026-02-01T00:00:00Z",
            secrets_management_verified=True,
            tls_transport_verified=True,
            access_control_verified=True,
            audit_logging_verified=True,
            monitoring_alerting_verified=True,
            backup_restore_tested=True,
            rollback_tested=True,
            reconciliation_verified=True,
            incident_response_verified=True,
            dependency_vulnerability_reviewed=True,
            reviewer_reference="TEST_ONLY:synthetic-security-review",
            evidence_refs=TEST_EVIDENCE,
        )
    )
    service.production_infrastructure.create_payment_provider_configuration(
        PaymentProviderConfiguration(
            provider_id=TEST_PAYMENT_PROVIDER_ID,
            status=PaymentProviderStatus.APPROVED,
            environment="sandbox",
            provider_account_reference="TEST_ONLY:sandbox-merchant",
            approval_reference="TEST_ONLY:sandbox-provider-approval",
            evidence_refs=TEST_EVIDENCE,
        )
    )

    service.commercialization_technical_validations.create_validation(
        CommercializationTechnicalValidation(
            validation_id=TEST_VALIDATION_ID,
            commit_sha=validated_commit_sha,
            validated_at="2026-02-01T00:00:00Z",
            test_count=test_count,
            full_regression_passed=True,
            governance_validation_passed=True,
            commercialization_consistency_passed=True,
            evidence_refs=TEST_EVIDENCE,
        )
    )

    service.commercial_policy_approvals.create_independent_charge_policy(
        IndependentPlatformChargePolicy(
            policy_id="TEST-IND-POLICY-001",
            model=IndependentPlatformChargeModel.POSITIVE_REALIZED_PERCENTAGE,
            rate=Decimal("0.01"),
            currency="USD",
            approved_for_production=True,
            approved_at="2026-02-01T00:00:00Z",
            approval_reference="TEST_ONLY:synthetic-independent-policy",
            evidence_refs=TEST_EVIDENCE,
        )
    )
    for mode in ServiceMode:
        service.commercial_policy_approvals.create_jurisdiction_mode_approval(
            JurisdictionServiceModeApproval(
                approval_id=f"TEST-MODE-{mode.value}",
                jurisdiction_code=TEST_JURISDICTION,
                service_mode=mode,
                status=JurisdictionModeApprovalStatus.APPROVED,
                approved_at="2026-02-01T00:00:00Z",
                approval_reference=f"TEST_ONLY:synthetic-{mode.value.lower()}",
                evidence_refs=TEST_EVIDENCE,
            )
        )

    notice_policy = CustomerNotificationPolicy(
        policy_id="TEST-NOTICE-POLICY-001",
        jurisdiction_code=TEST_JURISDICTION,
        notification_type=CustomerNotificationType.TRIAL_EXPIRY_REMINDER,
        lead_time_hours=72,
        approved_for_production=True,
        approval_reference="TEST_ONLY:synthetic-notice-policy",
        evidence_refs=TEST_EVIDENCE,
    )
    service.launch_operations.create_notification_policy(notice_policy)
    service.launch_operations.create_notification_provider_configuration(
        NotificationProviderConfiguration(
            provider_id=TEST_NOTIFICATION_PROVIDER_ID,
            channel=NotificationChannel.EMAIL,
            status=NotificationProviderStatus.APPROVED,
            environment="sandbox",
            provider_account_reference="TEST_ONLY:sandbox-notify-account",
            approval_reference="TEST_ONLY:sandbox-notify-approval",
            evidence_refs=TEST_EVIDENCE,
        )
    )
    service.launch_operations.create_notification_intent(
        build_notification_intent(
            notification_id="TEST-NOTIFY-001",
            customer_id=TEST_CUSTOMER_ID,
            account_reference=TEST_ACCOUNT_REFERENCE,
            notification_type=CustomerNotificationType.TRIAL_EXPIRY_REMINDER,
            scheduled_for="2026-01-28T00:00:00Z",
            policy=notice_policy,
            evidence_refs=TEST_EVIDENCE,
        )
    )

    for scenario in REQUIRED_COMMERCIALIZATION_UAT_SCENARIOS:
        service.commercialization_uat.create_result(
            CommercializationUatResult(
                run_id=TEST_UAT_RUN_ID,
                scenario=scenario,
                status=UatResultStatus.PASSED,
                executed_at="2026-02-01T00:00:00Z",
                environment_reference="TEST_ONLY:isolated-sandbox",
                evidence_refs=(
                    f"TEST_ONLY:uat:{scenario.value}",
                ),
            )
        )

    for category in REQUIRED_LAUNCH_EVIDENCE:
        service.launch_operations.create_launch_evidence_item(
            TEST_DOSSIER_ID,
            LaunchEvidenceItem(
                category=category,
                evidence_reference=(
                    f"TEST_ONLY:launch-evidence:{category.value}"
                ),
                approved=True,
            ),
        )

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Tuple

from backend.app.persistence.services.commercialization_operations_status_service import (
    CommercializationOperationsStatusService,
)
from backend.app.persistence.services.notification_delivery_preflight_service import (
    NotificationDeliveryPreflightService,
)
from backend.app.persistence.services.persistence_service import PersistenceService
from backend.commercialization.full_test_fixture import (
    TEST_ACCOUNT_REFERENCE,
    TEST_AGREEMENT_ID,
    TEST_AGREEMENT_VERSION,
    TEST_CUSTOMER_ID,
    TEST_DOSSIER_ID,
    TEST_JURISDICTION,
    TEST_NOTIFICATION_PROVIDER_ID,
    TEST_PAYMENT_PROVIDER_ID,
    TEST_UAT_RUN_ID,
    seed_full_test_fixture,
)
from backend.commercialization.payment_collection_provider import (
    PaymentCollectionRequest,
)
from backend.commercialization.sandbox_notification_provider import (
    SandboxNotificationDeliveryProvider,
)
from backend.commercialization.sandbox_payment_provider import (
    SandboxPaymentCollectionProvider,
    build_sandbox_payment_preflight,
)


@dataclass(frozen=True, slots=True)
class FullTestReadinessReport:
    ready_for_full_testing: bool
    production_commercial_ready: bool
    uat_complete: bool
    launch_dossier_complete: bool
    sandbox_payment_succeeded: bool
    sandbox_notification_succeeded: bool
    production_block_reason_codes: Tuple[str, ...]
    trading_execution_authority: bool
    broker_execution_authority: bool
    money_movement_to_external_provider: bool


class FullTestReadinessRunner:
    """Run deterministic isolated commercialization release-candidate checks."""

    def __init__(self, service: PersistenceService) -> None:
        self._service = service

    def run(
        self,
        *,
        validated_commit_sha: str,
        test_count: int,
    ) -> FullTestReadinessReport:
        seed_full_test_fixture(
            self._service,
            validated_commit_sha=validated_commit_sha,
            test_count=test_count,
        )

        operations = CommercializationOperationsStatusService(
            self._service
        ).build_status(
            customer_id=TEST_CUSTOMER_ID,
            account_reference=TEST_ACCOUNT_REFERENCE,
            agreement_id=TEST_AGREEMENT_ID,
            agreement_version=TEST_AGREEMENT_VERSION,
            jurisdiction_code=TEST_JURISDICTION,
            assessed_at="2026-02-05T00:00:00Z",
            provider_id=TEST_PAYMENT_PROVIDER_ID,
            uat_run_id=TEST_UAT_RUN_ID,
            dossier_id=TEST_DOSSIER_ID,
        )

        payment_provider = SandboxPaymentCollectionProvider()
        request = PaymentCollectionRequest(
            collection_id="TEST-COLLECTION-001",
            customer_id=TEST_CUSTOMER_ID,
            account_reference=TEST_ACCOUNT_REFERENCE,
            amount=Decimal("10.00"),
            currency="USD",
            idempotency_key="TEST_ONLY:idem:collection-001",
            invoice_reference="TEST-INV-001",
            evidence_refs=("TEST_ONLY:sandbox-payment",),
        )
        sandbox_preflight = build_sandbox_payment_preflight()
        payment_tx_1 = payment_provider.collect(request, sandbox_preflight)
        payment_tx_2 = payment_provider.collect(request, sandbox_preflight)
        payment_ok = (
            payment_tx_1 == payment_tx_2
            and payment_provider.receipt_for(
                request.idempotency_key
            ).status == "SIMULATED_SUCCEEDED"
        )

        notification_preflight = NotificationDeliveryPreflightService(
            self._service
        ).assess(
            notification_id="TEST-NOTIFY-001",
            provider_id=TEST_NOTIFICATION_PROVIDER_ID,
        )
        notification_provider = SandboxNotificationDeliveryProvider()
        intent_row = self._service.launch_operations.get_notification_intent(
            "TEST-NOTIFY-001"
        )
        from backend.commercialization.customer_notifications import (
            CustomerNotificationIntent,
            CustomerNotificationType,
        )
        import json

        intent = CustomerNotificationIntent(
            notification_id=intent_row["notification_id"],
            customer_id=intent_row["customer_id"],
            account_reference=intent_row["account_reference"],
            notification_type=CustomerNotificationType(
                intent_row["notification_type"]
            ),
            scheduled_for=intent_row["scheduled_for"],
            policy_id=intent_row["policy_id"],
            evidence_refs=tuple(
                json.loads(intent_row["evidence_refs_json"])
            ),
        )
        message_1 = notification_provider.send(
            intent,
            notification_preflight,
        )
        message_2 = notification_provider.send(
            intent,
            notification_preflight,
        )
        notification_ok = (
            message_1 == message_2
            and notification_provider.receipt_for(
                intent.notification_id
            ).status == "SIMULATED_DELIVERED"
        )

        production_reasons = tuple(
            operations["release_reason_codes"]
        )
        expected_sandbox_block = any(
            "PAYMENT_PROVIDER_NOT_PRODUCTION_ENVIRONMENT" in reason
            for reason in production_reasons
        )

        ready = all(
            (
                operations["uat_complete"],
                operations["launch_dossier_complete"],
                payment_ok,
                notification_ok,
                not operations["production_commercial_ready"],
                expected_sandbox_block,
                operations["trading_execution_authority"] is False,
                operations[
                    "money_movement_available_from_this_view"
                ] is False,
            )
        )

        return FullTestReadinessReport(
            ready_for_full_testing=ready,
            production_commercial_ready=bool(
                operations["production_commercial_ready"]
            ),
            uat_complete=bool(operations["uat_complete"]),
            launch_dossier_complete=bool(
                operations["launch_dossier_complete"]
            ),
            sandbox_payment_succeeded=payment_ok,
            sandbox_notification_succeeded=notification_ok,
            production_block_reason_codes=production_reasons,
            trading_execution_authority=False,
            broker_execution_authority=False,
            money_movement_to_external_provider=False,
        )

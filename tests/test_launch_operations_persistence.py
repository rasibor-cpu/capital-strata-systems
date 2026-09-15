import sqlite3

import backend.app.persistence.migrations.runner as migration_runner
import backend.app.persistence.repositories.base_repository as base_repository
from backend.app.persistence.services.persistence_service import PersistenceService
from backend.commercialization.commercialization_uat import (
    CommercializationUatResult,
    CommercializationUatScenario,
    UatResultStatus,
)
from backend.commercialization.customer_notifications import (
    CustomerNotificationIntent,
    CustomerNotificationPolicy,
    CustomerNotificationType,
)
from backend.commercialization.launch_evidence_dossier import (
    LaunchEvidenceCategory,
    LaunchEvidenceItem,
)


REFS = ("evidence:1",)


def test_launch_operations_evidence_persists(monkeypatch):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    monkeypatch.setattr(base_repository, "get_connection", lambda: conn)
    monkeypatch.setattr(migration_runner, "get_connection", lambda: conn)

    try:
        service = PersistenceService()

        service.commercialization_uat.create_result(
            CommercializationUatResult(
                run_id="UAT-1",
                scenario=CommercializationUatScenario.TRIAL_SIGNUP,
                status=UatResultStatus.PASSED,
                executed_at="2026-09-15T21:00:00Z",
                environment_reference="env:production-like",
                evidence_refs=REFS,
            )
        )
        rows = service.commercialization_uat.list_run("UAT-1")
        assert len(rows) == 1
        assert rows[0]["scenario"] == "TRIAL_SIGNUP"

        policy = CustomerNotificationPolicy(
            policy_id="NOTICE-1",
            jurisdiction_code="CA-ON",
            notification_type=CustomerNotificationType.CANCELLATION_CONFIRMATION,
            lead_time_hours=0,
            approved_for_production=True,
            approval_reference="counsel:notice",
            evidence_refs=REFS,
        )
        service.launch_operations.create_notification_policy(policy)
        service.launch_operations.create_notification_intent(
            CustomerNotificationIntent(
                notification_id="N-1",
                customer_id="CUST-1",
                account_reference="account:A",
                notification_type=CustomerNotificationType.CANCELLATION_CONFIRMATION,
                scheduled_for="2026-09-15T21:05:00Z",
                policy_id="NOTICE-1",
                evidence_refs=REFS,
            )
        )
        intents = service.launch_operations.list_notification_intents(
            "CUST-1",
            "account:A",
        )
        assert len(intents) == 1
        assert intents[0]["notification_type"] == "CANCELLATION_CONFIRMATION"

        service.launch_operations.create_launch_evidence_item(
            "DOSSIER-1",
            LaunchEvidenceItem(
                category=LaunchEvidenceCategory.TECHNICAL_VALIDATION,
                evidence_reference="ci:run-61",
                approved=True,
            ),
        )
        evidence = service.launch_operations.list_launch_evidence("DOSSIER-1")
        assert len(evidence) == 1
        assert evidence[0]["category"] == "TECHNICAL_VALIDATION"
    finally:
        conn.close()

import sqlite3

import backend.app.persistence.migrations.runner as migration_runner
import backend.app.persistence.repositories.base_repository as base_repository
from backend.app.persistence.repositories.commercial_policy_approval_repository import (
    CommercialPolicyApprovalRepository,
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
from decimal import Decimal


REFS = ("evidence:1",)


def test_policy_and_jurisdiction_approval_evidence_persist(monkeypatch):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    monkeypatch.setattr(base_repository, "get_connection", lambda: conn)
    monkeypatch.setattr(migration_runner, "get_connection", lambda: conn)
    migration_runner.run_migrations()

    try:
        repo = CommercialPolicyApprovalRepository()
        repo.create_independent_charge_policy(
            IndependentPlatformChargePolicy(
                policy_id="POL-1",
                model=IndependentPlatformChargeModel.POSITIVE_REALIZED_PERCENTAGE,
                rate=Decimal("0.01"),
                currency="USD",
                approved_for_production=False,
                approved_at=None,
                approval_reference=None,
                evidence_refs=REFS,
            )
        )
        assert repo.get_independent_charge_policy("POL-1")["approved_for_production"] == 0

        repo.create_jurisdiction_mode_approval(
            JurisdictionServiceModeApproval(
                approval_id="JUR-1",
                jurisdiction_code="CA-ON",
                service_mode=ServiceMode.DISCOVER,
                status=JurisdictionModeApprovalStatus.PENDING,
                approved_at=None,
                approval_reference=None,
                evidence_refs=REFS,
            )
        )
        row = repo.latest_jurisdiction_mode_approval("CA-ON", "DISCOVER")
        assert row["status"] == "PENDING"
    finally:
        conn.close()

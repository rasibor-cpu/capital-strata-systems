from pathlib import Path

import backend.app.persistence.db as db
from backend.app.persistence.services.persistence_service import PersistenceService
from backend.commercialization.trial_contract import CommercialAgreementSnapshot


REFS = ("uat:restart:evidence",)


def test_trial_agreement_persists_across_database_restart(tmp_path, monkeypatch):
    db.close_connection()
    path = tmp_path / "css_uat_restart.db"
    monkeypatch.setattr(db, "DEFAULT_DB_PATH", path)

    first = PersistenceService()
    first.trial_contracts.create_agreement(
        CommercialAgreementSnapshot(
            agreement_id="UAT-AGR-RESTART",
            agreement_version="v1",
            jurisdiction_code="TEST-JURISDICTION",
            pricing_plan_id="UAT-PLAN",
            pricing_summary="TEST ONLY",
            trial_duration_days=30,
            automatic_conversion_disclosure="TEST ONLY disclosure",
            effective_from="2026-09-16T00:00:00Z",
            evidence_refs=REFS,
        )
    )

    db.close_connection()

    second = PersistenceService()
    row = second.trial_contracts.get_agreement(
        "UAT-AGR-RESTART",
        "v1",
    )

    assert row is not None
    assert row["agreement_id"] == "UAT-AGR-RESTART"
    assert row["agreement_version"] == "v1"
    assert Path(path).exists()

    db.close_connection()

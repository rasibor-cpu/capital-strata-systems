from pathlib import Path

import backend.app.persistence.db as db
from backend.app.persistence.services.persistence_service import PersistenceService
from backend.commercialization.trial_contract import CommercialAgreementSnapshot
from backend.operations.backup_restore import (
    create_sqlite_backup,
    restore_sqlite_backup,
)


def _seed(path: Path, monkeypatch):
    db.close_connection()
    monkeypatch.setattr(db, "DEFAULT_DB_PATH", path)
    service = PersistenceService()
    service.trial_contracts.create_agreement(
        CommercialAgreementSnapshot(
            agreement_id="DR-AGR-1",
            agreement_version="v1",
            jurisdiction_code="TEST-JURISDICTION",
            pricing_plan_id="DR-PLAN",
            pricing_summary="TEST ONLY",
            trial_duration_days=30,
            automatic_conversion_disclosure="TEST ONLY",
            effective_from="2026-09-16T00:00:00Z",
            evidence_refs=("TEST_ONLY:dr",),
        )
    )
    db.close_connection()


def test_backup_restore_round_trip_preserves_canonical_state(tmp_path, monkeypatch):
    source = tmp_path / "source.db"
    backup = tmp_path / "backup.db"
    restored = tmp_path / "restored.db"
    _seed(source, monkeypatch)

    artifact = create_sqlite_backup(
        source_path=source,
        backup_path=backup,
    )
    assert artifact.integrity_check == "ok"
    assert artifact.schema_version_count > 0

    result = restore_sqlite_backup(
        backup_path=backup,
        restored_path=restored,
        expected_backup_sha256=artifact.sha256,
        required_tables=(
            "schema_migrations",
            "commercial_agreement_snapshots",
        ),
    )
    assert result.valid is True
    assert result.integrity_check == "ok"
    assert result.schema_version_count == artifact.schema_version_count

    conn = __import__("sqlite3").connect(restored)
    try:
        row = conn.execute(
            "SELECT agreement_id, agreement_version "
            "FROM commercial_agreement_snapshots "
            "WHERE agreement_id='DR-AGR-1'"
        ).fetchone()
        assert row == ("DR-AGR-1", "v1")
    finally:
        conn.close()


def test_restore_rejects_checksum_tampering(tmp_path, monkeypatch):
    source = tmp_path / "source.db"
    backup = tmp_path / "backup.db"
    restored = tmp_path / "restored.db"
    _seed(source, monkeypatch)

    artifact = create_sqlite_backup(
        source_path=source,
        backup_path=backup,
    )
    with backup.open("ab") as handle:
        handle.write(b"tamper")

    result = restore_sqlite_backup(
        backup_path=backup,
        restored_path=restored,
        expected_backup_sha256=artifact.sha256,
    )
    assert result.valid is False
    assert "BACKUP_CHECKSUM_MISMATCH" in result.reason_codes
    assert not restored.exists()


def test_restore_rejects_corrupt_database(tmp_path):
    backup = tmp_path / "corrupt.db"
    restored = tmp_path / "restored.db"
    backup.write_bytes(b"this is not sqlite")

    import hashlib
    checksum = hashlib.sha256(backup.read_bytes()).hexdigest()

    result = restore_sqlite_backup(
        backup_path=backup,
        restored_path=restored,
        expected_backup_sha256=checksum,
    )
    assert result.valid is False
    assert "BACKUP_DATABASE_CORRUPT" in result.reason_codes
    assert not restored.exists()


def test_rollback_restores_pre_change_canonical_state(tmp_path, monkeypatch):
    source = tmp_path / "source.db"
    backup = tmp_path / "backup.db"
    restored = tmp_path / "restored.db"
    _seed(source, monkeypatch)

    artifact = create_sqlite_backup(
        source_path=source,
        backup_path=backup,
    )

    db.close_connection()
    monkeypatch.setattr(db, "DEFAULT_DB_PATH", source)
    service = PersistenceService()
    service.trial_contracts.create_agreement(
        CommercialAgreementSnapshot(
            agreement_id="DR-AGR-AFTER-SNAPSHOT",
            agreement_version="v1",
            jurisdiction_code="TEST-JURISDICTION",
            pricing_plan_id="DR-PLAN-2",
            pricing_summary="POST SNAPSHOT TEST ONLY",
            trial_duration_days=30,
            automatic_conversion_disclosure="TEST ONLY",
            effective_from="2026-09-16T01:00:00Z",
            evidence_refs=("TEST_ONLY:post-snapshot",),
        )
    )
    db.close_connection()

    result = restore_sqlite_backup(
        backup_path=backup,
        restored_path=restored,
        expected_backup_sha256=artifact.sha256,
        required_tables=(
            "schema_migrations",
            "commercial_agreement_snapshots",
        ),
    )
    assert result.valid is True

    conn = __import__("sqlite3").connect(restored)
    try:
        before = conn.execute(
            "SELECT COUNT(*) FROM commercial_agreement_snapshots "
            "WHERE agreement_id='DR-AGR-1'"
        ).fetchone()[0]
        after = conn.execute(
            "SELECT COUNT(*) FROM commercial_agreement_snapshots "
            "WHERE agreement_id='DR-AGR-AFTER-SNAPSHOT'"
        ).fetchone()[0]
        assert before == 1
        assert after == 0
    finally:
        conn.close()

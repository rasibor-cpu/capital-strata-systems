"""Phase 191 — enterprise certification registry tests (offline)."""

from __future__ import annotations

import pytest

from backend.app.governance.enterprise_certification_registry import (
    CertificationClaimError,
    CertificationRegistryEntry,
    RegistryEntityType,
    RegistryExporter,
    RegistryHash,
    RegistryQuery,
    RegistryRepository,
    RegistrySnapshot,
    RegistryValidator,
    assert_valid_certification_claim,
    seed_phase_registry,
)
from backend.app.governance.enterprise_certification_registry.audit import RegistryAudit


def test_seed_registers_phases_187_through_193() -> None:
    repo = seed_phase_registry()
    query = RegistryQuery(repo)
    for phase in ("187A", "188", "189", "190", "191", "192", "193"):
        hits = query.by_phase(phase)
        assert hits, f"missing phase registration: {phase}"
    assert len(repo) >= 10


def test_entries_never_grant_execution() -> None:
    repo = seed_phase_registry()
    assert RegistryQuery(repo).claims_execution() == ()
    for entry in repo:
        assert entry.execution_authority is False
        assert entry.live_status in {"NOT_AUTHORIZED", "BLOCKED", "SUSPENDED", "NOT_STARTED"}


def test_validator_rejects_execution_authority() -> None:
    with pytest.raises(ValueError):
        CertificationRegistryEntry(
            registry_id="bad",
            entity_type=RegistryEntityType.BROKER.value,
            entity_name="X",
            execution_authority=True,
        )


def test_repository_rejects_duplicates() -> None:
    repo = RegistryRepository()
    entry = CertificationRegistryEntry(
        registry_id="x",
        entity_type=RegistryEntityType.PLUGIN.value,
        entity_name="P",
        certification_status="NOT_STARTED",
        live_status="NOT_AUTHORIZED",
    )
    repo.register(entry)
    with pytest.raises(ValueError):
        repo.register(entry)


def test_query_by_broker_and_asset() -> None:
    repo = seed_phase_registry()
    query = RegistryQuery(repo)
    assert any(e.broker_type == "OANDA" for e in query.by_broker("OANDA"))
    assert any(e.asset_class == "FX" for e in query.by_asset_class("FX"))


def test_claim_requires_registry_entry() -> None:
    repo = seed_phase_registry()
    with pytest.raises(CertificationClaimError):
        assert_valid_certification_claim(repo, registry_id="missing:id")
    entry = assert_valid_certification_claim(repo, registry_id="phase:191")
    assert entry.entity_name.startswith("PHASE_191")
    assert entry.execution_authority is False


def test_suspended_claim_denied() -> None:
    repo = seed_phase_registry()
    with pytest.raises(CertificationClaimError):
        assert_valid_certification_claim(repo, registry_id="broker:IBKR")


def test_snapshot_and_export_hash_stable() -> None:
    repo = seed_phase_registry()
    snap = RegistrySnapshot.capture(repo, timestamp="2026-08-01T12:00:00Z")
    assert snap.entry_count == len(repo)
    assert snap.snapshot_hash == RegistryHash.hash_entries(snap.entries)
    exported = RegistryExporter().export_snapshot(snap)
    assert exported["execution_authority"] is False
    assert exported["export_hash"]
    assert "secret" not in str(exported).lower() or "[REDACTED]" in str(exported)


def test_audit_report() -> None:
    repo = seed_phase_registry()
    report = RegistryAudit(repo).report()
    assert report.event_count == len(repo)
    assert report.execution_authority_observed is False


def test_validator_batch() -> None:
    repo = seed_phase_registry()
    result = RegistryValidator().validate_many(repo.all_entries())
    assert result.ok is True


def test_extensible_custom_entity_type() -> None:
    repo = RegistryRepository()
    entry = CertificationRegistryEntry(
        registry_id="custom:FOO",
        entity_type="CUSTOM",
        entity_name="FOO",
        certification_status="NOT_STARTED",
        live_status="NOT_AUTHORIZED",
    )
    repo.register(entry)
    assert repo.get("custom:FOO") is not None


def test_governance_doc_exists() -> None:
    from pathlib import Path

    doc = Path(__file__).resolve().parents[1] / "docs" / "governance" / "PHASE_191_ENTERPRISE_CERTIFICATION_REGISTRY.md"
    assert doc.is_file()
    text = doc.read_text(encoding="utf-8")
    assert "RegistryRepository" in text
    assert "execution_authority" in text
    assert "NO RUNTIME" in text or "No runtime" in text

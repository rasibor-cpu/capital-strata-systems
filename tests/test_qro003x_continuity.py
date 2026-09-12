from datetime import datetime, timezone
from decimal import Decimal

import pytest

from backend.brokers.portfolio_continuity import AuditEvent, AuditHistory, PortfolioContinuity, PortfolioSnapshotStore, SNAPSHOT_SCHEMA
from backend.brokers.replay_provider import ReplayBrokerProvider, ReplayScenario
from backend.brokers.readonly_domain import SnapshotSource


NOW = datetime(2026, 9, 11, 12, tzinfo=timezone.utc)


def continuity(tmp_path):
    return PortfolioContinuity(PortfolioSnapshotStore(tmp_path / "snapshot.json"), AuditHistory(tmp_path / "audit.jsonl"))


def test_snapshot_store_is_atomic_decimal_safe_and_reloadable(tmp_path):
    source = ReplayBrokerProvider(now=NOW).snapshot()
    manager = continuity(tmp_path)
    assert manager.accept(source) is True
    assert manager.accept(source) is False
    status, loaded = manager.reload(now=NOW)
    assert status == "LAST_KNOWN_GOOD_STALE"
    assert loaded is not None
    assert loaded.cash == Decimal("5000")
    assert loaded.snapshot_id == source.snapshot_id
    assert loaded.snapshot_source is SnapshotSource.STALE
    assert loaded.broker_data_freshness == "STALE"
    assert len(manager.audit.read()) == 2


def test_corrupt_and_unsupported_snapshot_fail_closed(tmp_path):
    path = tmp_path / "snapshot.json"
    path.write_text('{"schema":"wrong","snapshot":{},"checksum":"bad"}', encoding="utf-8")
    status, loaded = PortfolioSnapshotStore(path).load()
    assert status == "CORRUPT"
    assert loaded is None
    path.write_text("not-json", encoding="utf-8")
    assert PortfolioSnapshotStore(path).load() == ("CORRUPT", None)


def test_restart_stale_reload_and_provider_recovery_are_explicit(tmp_path):
    manager = continuity(tmp_path)
    stale = ReplayBrokerProvider(ReplayScenario.STALE_DATA, now=NOW).snapshot()
    assert manager.accept(stale)
    status, loaded = continuity(tmp_path).reload(now=NOW)
    assert status == "LAST_KNOWN_GOOD_STALE"
    assert loaded.snapshot_source is SnapshotSource.STALE
    fresh = ReplayBrokerProvider(now=NOW).snapshot()
    recovered = continuity(tmp_path)
    assert recovered.accept(fresh)
    assert fresh.snapshot_source is SnapshotSource.REPLAY
    _, reloaded = recovered.reload(now=NOW)
    assert reloaded.snapshot_source is SnapshotSource.STALE


def test_audit_history_is_append_only_and_deduplicated(tmp_path):
    audit = AuditHistory(tmp_path / "audit.jsonl")
    event = AuditEvent("event-1", "PROVIDER_UNAVAILABLE", NOW, None, "****001", "warning", "Provider unavailable.")
    assert audit.append(event) is True
    assert audit.append(event) is False
    assert len(audit.read()) == 1
    assert "token" not in (tmp_path / "audit.jsonl").read_text(encoding="utf-8").lower()


def test_snapshot_has_lineage_but_no_raw_provider_payload():
    snapshot = ReplayBrokerProvider(now=NOW).snapshot()
    payload = snapshot.as_dict()
    assert payload["provider"] == "REPLAY"
    assert payload["snapshot_id"]
    assert payload["validation_status"] == "VALIDATED"
    assert "access_token" not in payload
    assert "refresh_token" not in payload

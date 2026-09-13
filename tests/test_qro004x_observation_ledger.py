from datetime import datetime, timezone
from decimal import Decimal

import pytest

from backend.brokers.continuity_projection import build_continuity_state
from backend.brokers.observation_ledger import BrokerObservation, ObservationLedger, ReconciliationLedger
from backend.brokers.portfolio_continuity import SnapshotStoreError
from backend.brokers.replay_provider import ReplayBrokerProvider
from backend.brokers.continuity_evidence import export_continuity_evidence


NOW = datetime(2026, 9, 11, 12, tzinfo=timezone.utc)


def observation(kind="EXECUTION", entity="exec-1"):
    return BrokerObservation(kind, "REPLAY", "**********-001", NOW, "snapshot-1", {"symbol": "SHOP", "quantity": Decimal("10"), "price": Decimal("80")}, entity)


def test_observation_ledger_is_normalized_atomic_and_restart_idempotent(tmp_path):
    path = tmp_path / "observations.json"
    ledger = ObservationLedger(path)
    first = observation()
    assert ledger.append(first) is True
    assert ledger.append(first) is False
    restarted = ObservationLedger(path)
    assert restarted.append(first) is False
    assert restarted.entry_count == 1
    record = restarted.entries()[0]
    assert record["observation_id"] == first.with_identity().observation_id
    assert "access_token" not in str(record)
    assert "refresh_token" not in str(record)


def test_observation_identity_changes_with_normalized_economic_fields():
    assert observation().with_identity().observation_id != observation(entity="exec-2").with_identity().observation_id
    assert observation().with_identity().observation_id == observation().with_identity().observation_id


def test_observation_ledger_redacts_sensitive_payload_keys(tmp_path):
    path = tmp_path / "observations.json"
    ledger = ObservationLedger(path)
    item = BrokerObservation(
        "ACTIVITY",
        "REPLAY",
        "**********-001",
        NOW,
        "snapshot-1",
        {
            "symbol": "SHOP",
            "access_token": "DO-NOT-PERSIST",
            "nested": {
                "refresh_token": "DO-NOT-PERSIST-EITHER",
                "safe_value": "visible",
            },
        },
        "activity-1",
    )

    assert ledger.append(item) is True

    persisted = path.read_text(encoding="utf-8")
    record = ledger.entries()[0]

    assert "DO-NOT-PERSIST" not in persisted
    assert "DO-NOT-PERSIST-EITHER" not in persisted
    assert record["payload"]["access_token"] == "REDACTED"
    assert record["payload"]["nested"]["refresh_token"] == "REDACTED"
    assert record["payload"]["nested"]["safe_value"] == "visible"


def test_corrupt_ledger_fails_closed(tmp_path):
    path = tmp_path / "observations.json"
    path.write_text('{"schema":"wrong","entries":[],"checksum":"bad"}', encoding="utf-8")
    with pytest.raises(SnapshotStoreError):
        ObservationLedger(path)


def test_reconciliation_lifecycle_survives_restart_and_stale_does_not_resolve(tmp_path):
    path = tmp_path / "reconciliation.json"
    ledger = ReconciliationLedger(path)
    assert ledger.observe("cash-mismatch", status="ISSUES") == "CREATED"
    assert ledger.observe("cash-mismatch", status="ISSUES") == "UNCHANGED"
    assert ReconciliationLedger(path).observe("cash-mismatch", status="MATCH", stale=True) == "UNCHANGED"
    assert ReconciliationLedger(path).observe("cash-mismatch", status="MATCH", stale=False) == "RESOLVED"


def test_continuity_projection_is_fail_closed_and_explicit(tmp_path):
    ledger = ObservationLedger(tmp_path / "observations.json")
    ledger.append(observation())
    state = build_continuity_state(ReplayBrokerProvider(now=NOW).snapshot(), snapshot_status="CURRENT_FRESH", ledger=ledger)
    assert state["snapshot_source"] == "REPLAY"
    assert state["ledger_entry_count"] == 1
    assert state["execution_allowed"] is False
    assert state["live_trading_blocked"] is True
    assert state["broker_execution_armed"] is False
    assert state["advisory_only"] is True


def test_snapshot_lineage_can_reference_observations(tmp_path):
    ledger = ObservationLedger(tmp_path / "observations.json")
    item = observation()
    ledger.append(item)
    snapshot = ReplayBrokerProvider(now=NOW).snapshot()
    assert snapshot.observation_ids == ()
    payload = snapshot.as_dict()
    payload["observation_ids"] = [item.with_identity().observation_id]
    assert payload["observation_ids"]


def test_evidence_export_is_safe_json_and_markdown(tmp_path):
    export_continuity_evidence(
        tmp_path / "evidence.json",
        tmp_path / "evidence.md",
        continuity={"provider": "REPLAY", "snapshot_source": "REPLAY", "snapshot_status": "CURRENT_FRESH", "execution_allowed": False},
        observations=[{"observation_id": "obs-1", "payload": {"symbol": "SHOP"}}],
        test_metadata={"access_token": "must-not-export"},
    )
    content = (tmp_path / "evidence.json").read_text(encoding="utf-8")
    assert "must-not-export" not in content
    assert "obs-1" in content
    assert "QRO-004X Continuity Evidence" in (tmp_path / "evidence.md").read_text(encoding="utf-8")

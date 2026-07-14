from __future__ import annotations

import json

import pytest

import backend.app.brokers.broker_registry as broker_registry
from backend.app.audit.persistent_execution_journal import (
    JOURNAL_VERSION,
    RETENTION_POLICY,
    ExecutionJournalValidationError,
    PersistentExecutionJournal,
    canonical_record_json,
    stable_evidence_payload,
)
from dashboard.runtime.evidence_hashing import hash_evidence_payload


def _append_sample(journal: PersistentExecutionJournal, **overrides):
    payload = {
        "strategy_id": "mean-reversion-v1",
        "asset_class": "OPTIONS",
        "execution_intent": "OPEN_LONG_CALL",
        "broker_mode": "paper",
        "broker_name": "SIM_OPTIONS",
        "decision": "APPROVED",
        "reason": "unit-test",
        "correlation_id": "corr-001",
        "metadata": {"symbol": "SPY-C-500", "nested": {"b": 2, "a": 1}},
        "timestamp_utc": "2026-07-14T12:00:00",
    }
    payload.update(overrides)
    return journal.append_record(**payload)


def test_journal_creation_and_append_behavior(tmp_path):
    path = tmp_path / "execution_journal.jsonl"
    journal = PersistentExecutionJournal(path)

    first = _append_sample(journal)
    second = _append_sample(
        journal,
        execution_intent="CLOSE_LONG_CALL",
        correlation_id="corr-002",
    )

    assert path.exists()
    assert first["journal_version"] == JOURNAL_VERSION
    assert first["retention_policy"] == RETENTION_POLICY
    assert first["sequence"] == 1
    assert second["sequence"] == 2
    assert journal.total_records() == 2
    assert len(path.read_text(encoding="utf-8").splitlines()) == 2


def test_deterministic_serialization_and_evidence_hash(tmp_path):
    journal = PersistentExecutionJournal(tmp_path / "execution_journal.jsonl")
    first = _append_sample(
        journal,
        timestamp_utc="2026-07-14T12:00:00",
        metadata={"nested": {"z": 2, "a": 1}, "tuple_like": ("A", None)},
    )
    second = _append_sample(
        journal,
        timestamp_utc="2026-07-15T12:00:00",
        metadata={"tuple_like": ["A", None], "nested": {"a": 1, "z": 2}},
    )

    assert first["evidence_hash"] == second["evidence_hash"]
    assert first["evidence_hash_id"] == second["evidence_hash_id"]
    assert first["timestamp_utc"] != second["timestamp_utc"]
    assert first["sequence"] != second["sequence"]
    assert canonical_record_json(first) == json.dumps(
        first,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        default=str,
    )


def test_supplied_evidence_hash_is_preserved(tmp_path):
    journal = PersistentExecutionJournal(tmp_path / "execution_journal.jsonl")
    evidence = hash_evidence_payload(
        stable_evidence_payload(
            asset_class="FUTURES",
            execution_intent="OPEN_LONG",
            broker_mode="paper",
            broker_name="SIM_FUTURES",
            decision="BLOCKED",
            metadata={"symbol": "ES"},
        ),
        source_type="unit_test",
        source_reference="corr-003",
    )

    record = _append_sample(
        journal,
        asset_class="FUTURES",
        execution_intent="OPEN_LONG",
        broker_mode="paper",
        broker_name="SIM_FUTURES",
        decision="BLOCKED",
        metadata={"symbol": "ES"},
        evidence_hash=evidence,
    )

    assert record["evidence_hash"] == evidence["evidence_hash"]
    assert record["evidence_hash_id"] == evidence["evidence_hash_id"]
    assert record["evidence_algorithm"] == "sha256"


def test_replay_ordering_and_malformed_entry_handling(tmp_path):
    path = tmp_path / "execution_journal.jsonl"
    journal = PersistentExecutionJournal(path)
    _append_sample(journal, correlation_id="corr-1")
    with path.open("a", encoding="utf-8") as handle:
        handle.write("{not-json}\n")
    _append_sample(journal, correlation_id="corr-2")

    replay = journal.replay_records()

    assert [record["sequence"] for record in replay] == [1, 2]
    assert journal.total_records() == 2
    with pytest.raises(ExecutionJournalValidationError):
        journal.read_records(strict=True)


def test_schema_validation_rejects_missing_required_fields(tmp_path):
    journal = PersistentExecutionJournal(tmp_path / "execution_journal.jsonl")

    with pytest.raises(ExecutionJournalValidationError):
        journal.append_record(
            asset_class="",
            execution_intent="OPEN",
            broker_mode="paper",
            broker_name="SIM",
            decision="APPROVED",
        )

    with pytest.raises(ExecutionJournalValidationError):
        journal.validate_record({"journal_version": JOURNAL_VERSION})


def test_append_only_behavior_preserves_existing_lines(tmp_path):
    path = tmp_path / "execution_journal.jsonl"
    journal = PersistentExecutionJournal(path)
    _append_sample(journal, correlation_id="corr-1")
    before = path.read_text(encoding="utf-8")
    _append_sample(journal, correlation_id="corr-2")
    after = path.read_text(encoding="utf-8")

    assert after.startswith(before)
    assert len(after.splitlines()) == 2


def test_journal_redacts_secrets_and_does_not_call_broker_registry(tmp_path, monkeypatch):
    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("broker registry must not be called")

    monkeypatch.setattr(broker_registry, "get_broker_spec", fail_if_called)
    journal = PersistentExecutionJournal(tmp_path / "execution_journal.jsonl")
    record = _append_sample(
        journal,
        metadata={
            "api_key": "SHOULD_NOT_LEAK",
            "operator_note": "token=SHOULD_NOT_LEAK",
            "execution_allowed": False,
        },
    )
    encoded = json.dumps(record, sort_keys=True)

    assert "SHOULD_NOT_LEAK" not in encoded
    assert record["metadata"]["api_key"] == "REDACTED"
    assert record["metadata"]["operator_note"] == "REDACTED"
    assert record["metadata"]["execution_allowed"] is False

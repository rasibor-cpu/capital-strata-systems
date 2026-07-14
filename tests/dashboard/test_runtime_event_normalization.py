from __future__ import annotations

import json

import pytest

from backend.app.audit.persistent_execution_journal import PersistentExecutionJournal
from backend.events.runtime_event_normalization import (
    RUNTIME_EVENT_SCHEMA_VERSION,
    RuntimeEventValidationError,
    canonical_runtime_event_json,
    normalize_runtime_event,
    order_runtime_events,
    runtime_event_evidence_hash,
    runtime_event_journal_metadata,
    stable_runtime_event_evidence_payload,
    validate_runtime_event,
)


BASE_EVENT = {
    "event_type": "runtime.health_check",
    "event_category": "runtime",
    "event_severity": "info",
    "event_source": "tests.runtime",
    "timestamp_utc": "2026-07-14T12:00:00Z",
    "correlation_id": "corr-001",
    "payload": {"status": "ok", "count": 2},
    "metadata": {"node": "laptop1"},
}


def test_schema_validation_and_version_handling() -> None:
    event = normalize_runtime_event(BASE_EVENT)

    assert event["schema_version"] == RUNTIME_EVENT_SCHEMA_VERSION
    assert event["event_severity"] == "INFO"
    assert event["timestamp_utc"] == "2026-07-14T12:00:00Z"
    validate_runtime_event(event)

    unsupported = dict(event, schema_version="css.runtime_event.normalized.v0")
    with pytest.raises(RuntimeEventValidationError, match="Unsupported"):
        validate_runtime_event(unsupported)


def test_deterministic_serialization_and_evidence_hash() -> None:
    first = normalize_runtime_event(BASE_EVENT)
    second = normalize_runtime_event(dict(reversed(list(BASE_EVENT.items()))))

    assert canonical_runtime_event_json(first) == canonical_runtime_event_json(second)
    assert first["event_id"] == second["event_id"]
    assert first["evidence_hash"] == second["evidence_hash"]
    assert stable_runtime_event_evidence_payload(first) == stable_runtime_event_evidence_payload(second)

    decoded = json.loads(canonical_runtime_event_json(first))
    assert list(decoded) == sorted(decoded)


def test_malformed_event_rejection() -> None:
    with pytest.raises(RuntimeEventValidationError, match="event_source"):
        normalize_runtime_event({**BASE_EVENT, "event_source": ""})

    with pytest.raises(RuntimeEventValidationError, match="severity"):
        normalize_runtime_event({**BASE_EVENT, "event_severity": "loud"})

    with pytest.raises(RuntimeEventValidationError, match="payload"):
        normalize_runtime_event({**BASE_EVENT, "payload": ["not", "a", "mapping"]})


def test_metadata_redaction_and_correlation_ids() -> None:
    event = normalize_runtime_event(
        {
            **BASE_EVENT,
            "payload": {"authorization": "Bearer SHOULD_NOT_LEAK"},
            "metadata": {
                "approval_token": "SHOULD_NOT_LEAK",
                "broker_mutation_allowed": False,
            },
            "correlation_id": "corr-redaction",
        }
    )

    assert event["correlation_id"] == "corr-redaction"
    assert event["payload"]["authorization"] == "REDACTED"
    assert event["metadata"]["approval_token"] == "REDACTED"
    assert event["metadata"]["broker_mutation_allowed"] is False


def test_event_ordering_uses_timestamp_then_event_id() -> None:
    later = normalize_runtime_event({**BASE_EVENT, "timestamp_utc": "2026-07-14T12:00:02Z"})
    earlier = normalize_runtime_event({**BASE_EVENT, "timestamp_utc": "2026-07-14T12:00:01Z"})

    ordered = order_runtime_events([later, earlier])

    assert [event["timestamp_utc"] for event in ordered] == [
        "2026-07-14T12:00:01Z",
        "2026-07-14T12:00:02Z",
    ]


def test_evidence_hash_compatibility_preserves_supplied_hash() -> None:
    source = runtime_event_evidence_hash(BASE_EVENT)
    event = normalize_runtime_event(BASE_EVENT, evidence_hash=source)

    assert event["evidence_hash"] == source["evidence_hash"]
    assert event["evidence_hash_id"] == source["evidence_hash_id"]
    assert event["evidence_algorithm"] == "sha256"


def test_journal_compatibility_without_execution_side_effects(tmp_path) -> None:
    event = normalize_runtime_event(BASE_EVENT)
    metadata = runtime_event_journal_metadata(event)
    journal = PersistentExecutionJournal(tmp_path / "execution_journal.jsonl")

    record = journal.append_record(
        asset_class="equity",
        execution_intent="runtime_event_observation",
        broker_mode="paper",
        broker_name="none",
        decision="observed",
        correlation_id=event["correlation_id"],
        metadata=metadata,
        evidence_hash=event["evidence_hash"],
    )

    assert record["metadata"]["runtime_event_id"] == event["event_id"]
    assert record["evidence_hash"] == event["evidence_hash"]
    assert journal.total_records() == 1

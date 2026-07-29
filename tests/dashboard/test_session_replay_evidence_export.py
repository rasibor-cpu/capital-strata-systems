from __future__ import annotations

import builtins
import os
import socket
import subprocess
from pathlib import Path
from typing import Any

import pytest

from dashboard.runtime.session_replay_evidence_export import (
    SESSION_REPLAY_EVIDENCE_EXPORT_VERSION,
    build_session_replay_evidence_export_payload,
)

GENERATED_AT = "2026-07-29T00:00:00+00:00"


def _event(**overrides: Any) -> dict[str, Any]:
    event = {
        "schema_version": "css.replay_event_envelope.v1",
        "event_id": "EVT-1",
        "correlation_id": "CORR-1",
        "session_id": "SESSION-1",
        "event_type": "position_exit_booked",
        "timestamp_utc": "2026-07-29T00:00:01+00:00",
        "subsystem": "trade_lifecycle",
        "symbol": "MSFT",
        "asset_class": "EQUITY",
        "broker": "OANDA",
        "broker_mode": "LIVE_READ_ONLY",
        "engine_mode": "SAFE",
        "cycle": "42",
        "payload": {"safe": True},
    }
    event.update(overrides)
    return event


def test_import_and_public_api() -> None:
    assert SESSION_REPLAY_EVIDENCE_EXPORT_VERSION == (
        "css.session_replay_evidence_export.v2"
    )
    assert callable(build_session_replay_evidence_export_payload)


def test_deterministic_replay_projection() -> None:
    first = build_session_replay_evidence_export_payload(
        session_id="SESSION-1",
        replay_correlation_ids=["CORR-1"],
        replay_events=[_event()],
        audit_events=[
            {
                "event_id": "AUD-1",
                "timestamp_utc": "2026-07-29T00:00:03+00:00",
                "event_type": "review",
                "correlation_id": "CORR-1",
                "session_id": "SESSION-1",
            }
        ],
        execution_history=[
            {
                "execution_id": "EXE-1",
                "timestamp_utc": "2026-07-29T00:00:02+00:00",
                "correlation_id": "CORR-1",
                "session_id": "SESSION-1",
                "execution_state": "BLOCKED",
            }
        ],
        generated_at_utc=GENERATED_AT,
    )
    second = build_session_replay_evidence_export_payload(
        session_id="SESSION-1",
        replay_correlation_ids=["CORR-1"],
        replay_events=[_event()],
        audit_events=[
            {
                "event_id": "AUD-1",
                "timestamp_utc": "2026-07-29T00:00:03+00:00",
                "event_type": "review",
                "correlation_id": "CORR-1",
                "session_id": "SESSION-1",
            }
        ],
        execution_history=[
            {
                "execution_id": "EXE-1",
                "timestamp_utc": "2026-07-29T00:00:02+00:00",
                "correlation_id": "CORR-1",
                "session_id": "SESSION-1",
                "execution_state": "BLOCKED",
            }
        ],
        generated_at_utc=GENERATED_AT,
    )

    assert first == second
    assert first["status"] == "OK"
    assert first["generated_at_utc"] == GENERATED_AT
    assert first["matched_replay_correlation_ids"] == ["CORR-1"]
    assert first["trade_lifecycle_replay_summary"]["by_symbol"] == {"MSFT": 1}
    assert first["execution_history"][0]["order_mutation_allowed"] is False


def test_empty_replay_fails_closed_without_file_access() -> None:
    payload = build_session_replay_evidence_export_payload(
        session_id="SESSION-1",
        replay_path="ignored.jsonl",
        generated_at_utc=GENERATED_AT,
    )

    assert payload["status"] == "DATA_UNAVAILABLE"
    assert payload["replay_sink_path"] == "ignored.jsonl"
    assert payload["source_metadata"]["replay_path_ignored"] is True
    assert "replay_events_missing" in payload["authority_blockers"]
    assert "REPLAY_EVENTS_NOT_SUPPLIED" in payload["warnings"]


def test_malformed_replay_fails_closed() -> None:
    payload = build_session_replay_evidence_export_payload(
        session_id="SESSION-1",
        replay_events=[{"event_id": "EVT-1", "correlation_id": "CORR-1"}],
        generated_at_utc=GENERATED_AT,
    )

    assert payload["status"] == "DATA_UNAVAILABLE"
    assert payload["replay_event_count"] == 0
    assert payload["malformed_replay_event_count"] == 1
    assert "replay_event_0_missing_event_type" in payload["authority_blockers"]


def test_duplicate_replay_events_are_explicit_and_fail_closed() -> None:
    payload = build_session_replay_evidence_export_payload(
        session_id="SESSION-1",
        replay_events=[
            _event(event_id="EVT-DUP", timestamp_utc="2026-07-29T00:00:02+00:00"),
            _event(event_id="EVT-DUP", correlation_id="CORR-2"),
        ],
        generated_at_utc=GENERATED_AT,
    )

    assert payload["status"] == "DATA_UNAVAILABLE"
    assert payload["duplicate_replay_event_count"] == 1
    assert payload["duplicate_replay_event_ids"] == ["EVT-DUP"]
    assert "duplicate_event_id:EVT-DUP" in payload["authority_blockers"]


def test_deterministic_ordering() -> None:
    payload = build_session_replay_evidence_export_payload(
        session_id="SESSION-1",
        replay_events=[
            _event(event_id="EVT-2", timestamp_utc="2026-07-29T00:00:02+00:00"),
            _event(event_id="EVT-1", timestamp_utc="2026-07-29T00:00:01+00:00"),
        ],
        audit_events=[
            {"event_id": "AUD-2", "timestamp_utc": "T2"},
            {"event_id": "AUD-1", "timestamp_utc": "T1"},
        ],
        execution_history=[
            {"execution_id": "EXE-2", "timestamp_utc": "T2"},
            {"execution_id": "EXE-1", "timestamp_utc": "T1"},
        ],
        generated_at_utc=GENERATED_AT,
    )

    assert [event["event_id"] for event in payload["trade_lifecycle_replay_events"]] == [
        "EVT-1",
        "EVT-2",
    ]
    assert [event["event_id"] for event in payload["audit_events"]] == ["AUD-1", "AUD-2"]
    assert [event["event_id"] for event in payload["execution_history"]] == [
        "EXE-1",
        "EXE-2",
    ]


def test_missing_session_and_order_ids_fail_closed_without_invention() -> None:
    payload = build_session_replay_evidence_export_payload(
        replay_events=[
            _event(
                session_id="",
                event_type="order_submission_attempt",
                order_id="",
            )
        ],
        generated_at_utc=GENERATED_AT,
    )

    assert payload["session_id"] == ""
    assert payload["status"] == "DATA_UNAVAILABLE"
    assert payload["replay_event_count"] == 0
    assert "session_id_missing" in payload["authority_blockers"]
    assert "replay_event_0_missing_order_id" in payload["authority_blockers"]


def test_projection_has_no_runtime_side_effects(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_side_effect(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("session replay projection attempted a side effect")

    with monkeypatch.context() as side_effect_guard:
        side_effect_guard.setattr(os, "getenv", fail_side_effect)
        side_effect_guard.setattr(os, "putenv", fail_side_effect)
        side_effect_guard.setattr(os, "system", fail_side_effect)
        side_effect_guard.setattr(socket, "socket", fail_side_effect)
        side_effect_guard.setattr(socket, "create_connection", fail_side_effect)
        side_effect_guard.setattr(subprocess, "run", fail_side_effect)
        side_effect_guard.setattr(subprocess, "Popen", fail_side_effect)
        side_effect_guard.setattr(Path, "open", fail_side_effect)
        side_effect_guard.setattr(Path, "read_text", fail_side_effect)
        side_effect_guard.setattr(Path, "write_text", fail_side_effect)
        side_effect_guard.setattr(builtins, "open", fail_side_effect)

        payload = build_session_replay_evidence_export_payload(
            session_id="SESSION-1",
            replay_events=[_event()],
            generated_at_utc=GENERATED_AT,
        )

    assert payload["status"] == "OK"
    assert payload["execution_allowed"] is False
    assert payload["orders_enabled"] is False
    assert payload["broker_mutation_allowed"] is False
    assert payload["persistence_enabled"] is False
    assert payload["source_metadata"]["no_filesystem_reads"] is True
    assert payload["source_metadata"]["no_filesystem_writes"] is True

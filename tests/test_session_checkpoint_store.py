from __future__ import annotations

import json

from backend.validation.session_checkpoint_store import SessionCheckpointStore


def test_session_checkpoint_store_handles_missing_file(tmp_path) -> None:
    store = SessionCheckpointStore(tmp_path / "validation")

    listed = store.list_checkpoints()
    summary = store.summarize_session()

    assert listed["status"] == "OK"
    assert listed["checkpoints"] == []
    assert summary["status"] == "DATA UNAVAILABLE"
    assert summary["final_validation_status"] == "RED"


def test_session_checkpoint_store_append_list_and_summary(tmp_path) -> None:
    store = SessionCheckpointStore(tmp_path / "validation")

    first = store.append_checkpoint(
        {
            "session_id": "paper-a",
            "timestamp": "2026-06-29T10:00:00Z",
            "cycle_count": 1,
            "runtime_health_status": "GREEN",
            "portfolio_decision_status": "GREEN",
            "pipeline_latency_ms": 100.0,
        }
    )
    second = store.append_checkpoint(
        {
            "session_id": "paper-a",
            "timestamp": "2026-06-29T10:05:00Z",
            "cycle_count": 2,
            "runtime_health_status": "GREEN",
            "portfolio_decision_status": "GREEN",
            "pipeline_latency_ms": 200.0,
            "recommendation_stability": 90.0,
        }
    )

    listed = store.list_checkpoints("paper-a")
    summary = store.summarize_session("paper-a")

    assert first["count"] == 1
    assert second["count"] == 2
    assert listed["count"] == 2
    assert listed["checkpoints"][0]["paper_validation_only"] is True
    assert summary["status"] == "OK"
    assert summary["cycle_count"] == 2
    assert summary["average_pipeline_latency"] == 150.0


def test_session_checkpoint_store_handles_corrupt_file_safely(tmp_path) -> None:
    storage_dir = tmp_path / "validation"
    storage_dir.mkdir()
    path = storage_dir / "paper_validation_checkpoints.json"
    path.write_text("{bad json", encoding="utf-8")
    store = SessionCheckpointStore(storage_dir)

    listed = store.list_checkpoints()
    appended = store.append_checkpoint({"session_id": "paper-b", "runtime_health_status": "GREEN"})

    assert listed["status"] == "OK"
    assert listed["checkpoints"] == []
    assert appended["status"] == "OK"
    assert json.loads(path.read_text(encoding="utf-8"))[0]["session_id"] == "paper-b"


def test_session_checkpoint_store_rejects_malformed_checkpoint(tmp_path) -> None:
    store = SessionCheckpointStore(tmp_path / "validation")

    result = store.append_checkpoint(["not", "a", "mapping"])  # type: ignore[arg-type]

    assert result["status"] == "DATA UNAVAILABLE"
    assert result["execution_allowed"] is False

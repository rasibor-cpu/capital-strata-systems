from __future__ import annotations

import json
import os
import time
from pathlib import Path

from backend.runtime.runtime_artifact_freshness import RuntimeArtifactFreshnessManager


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _manager(tmp_path: Path) -> RuntimeArtifactFreshnessManager:
    artifacts = tmp_path / "artifacts"
    return RuntimeArtifactFreshnessManager(
        artifacts_dir=artifacts,
        account_state_path=artifacts / "account.json",
        session_state_path=artifacts / "session.json",
        supervisor_state_path=tmp_path / "runtime" / "supervisor.json",
        closed_trade_ledger_path=tmp_path / "audit" / "closed.jsonl",
        stale_after_seconds=300,
    )


def _write_required(tmp_path: Path) -> None:
    artifacts = tmp_path / "artifacts"
    _write_json(artifacts / "account.json", {"account_balance": 1000.0})
    _write_json(artifacts / "session.json", {"session": {"engine_mode": "PAPER", "start_time": "2026-06-30T00:00:00Z"}})
    _write_json(tmp_path / "runtime" / "supervisor.json", {"status": "RUNNING"})


def test_artifact_freshness_active_runtime_with_fresh_artifacts_green(tmp_path: Path) -> None:
    _write_required(tmp_path)
    ledger = tmp_path / "audit" / "closed.jsonl"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    ledger.write_text("", encoding="utf-8")
    for name in (
        "portfolio_snapshot.json",
        "runtime_portfolio_state.json",
        "runtime_advisory_snapshot.json",
        "portfolio_decision.json",
        "validation_summary.json",
    ):
        _write_json(tmp_path / "artifacts" / name, {"status": "OK"})

    result = _manager(tmp_path).evaluate(runtime_active=True)

    assert result["freshness_status"] == "GREEN"
    assert result["runtime_active"] is True
    assert result["blockers"] == []
    assert result["warnings"] == []
    assert result["execution_allowed"] is False


def test_artifact_freshness_stale_account_is_amber_warning(tmp_path: Path) -> None:
    _write_required(tmp_path)
    old = time.time() - 600
    os.utime(tmp_path / "artifacts" / "account.json", (old, old))

    result = _manager(tmp_path).evaluate(runtime_active=True)

    assert result["freshness_status"] == "AMBER"
    assert "account_state" in result["stale_artifacts"]
    assert "stale_account_state" in result["warnings"]
    assert result["blockers"] == []


def test_artifact_freshness_old_closed_ledger_no_recent_trades_not_blocker(tmp_path: Path) -> None:
    _write_required(tmp_path)
    for name in (
        "portfolio_snapshot.json",
        "runtime_portfolio_state.json",
        "runtime_advisory_snapshot.json",
        "portfolio_decision.json",
        "validation_summary.json",
    ):
        _write_json(tmp_path / "artifacts" / name, {"status": "OK"})
    ledger = tmp_path / "audit" / "closed.jsonl"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    ledger.write_text("", encoding="utf-8")
    old = time.time() - 3600
    os.utime(ledger, (old, old))

    result = _manager(tmp_path).evaluate(runtime_active=True)

    assert result["artifacts"]["closed_trade_ledger"]["freshness"] == "NO_RECENT_TRADES"
    assert "closed_trade_ledger" not in result["stale_artifacts"]
    assert result["freshness_status"] == "GREEN"
    assert "no_recent_closed_trades" in result["warnings"]
    assert result["blockers"] == []


def test_artifact_freshness_stale_supervisor_or_session_blocks(tmp_path: Path) -> None:
    _write_required(tmp_path)
    old = time.time() - 600
    os.utime(tmp_path / "runtime" / "supervisor.json", (old, old))

    result = _manager(tmp_path).evaluate(runtime_active=True)

    assert result["freshness_status"] == "RED"
    assert "stale_supervisor_state" in result["blockers"]


def test_artifact_freshness_missing_critical_blocks_optional_warns(tmp_path: Path) -> None:
    artifacts = tmp_path / "artifacts"
    _write_json(artifacts / "session.json", {"session": {"engine_mode": "PAPER"}})
    _write_json(tmp_path / "runtime" / "supervisor.json", {"status": "RUNNING"})

    result = _manager(tmp_path).evaluate(runtime_active=True)

    assert result["freshness_status"] == "RED"
    assert "missing_account_state" in result["blockers"]
    assert "missing_closed_trade_ledger" in result["warnings"]


def test_artifact_freshness_safe_refresh_updates_mtime_only(tmp_path: Path) -> None:
    _write_required(tmp_path)
    account = tmp_path / "artifacts" / "account.json"
    old_payload = account.read_text(encoding="utf-8")
    old = time.time() - 600
    os.utime(account, (old, old))

    result = _manager(tmp_path).evaluate(runtime_active=True, refresh=True)

    assert "account_state" in result["refreshed_artifacts"]
    assert account.read_text(encoding="utf-8") == old_payload

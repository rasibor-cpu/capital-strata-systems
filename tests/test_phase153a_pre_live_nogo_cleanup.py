from __future__ import annotations

import datetime
import json
import os
import time
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.runtime.runtime_session_continuity import RuntimeSessionContinuityMonitor
from backend.validation.live_readiness_certification import (
    certify_live_readiness,
    git_metadata,
    live_readiness_blocker_diagnostics,
)
from dashboard.runtime.api_bridge import create_app
import launcher.css_mobile_launcher as launcher


NOW = datetime.datetime(2026, 7, 3, 12, 0, tzinfo=datetime.timezone.utc)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_phase153a_default_blocker_diagnostics_list_exact_baseline_blockers() -> None:
    report = certify_live_readiness({})
    diagnostics = live_readiness_blocker_diagnostics({})

    assert diagnostics["blocker_count"] == len(report["known_blockers"]) == 24
    assert diagnostics["overall_certification_decision"] == "NO GO"
    assert diagnostics["execution_allowed"] is False
    assert diagnostics["advisory_only"] is True

    required = {
        "blocker_id",
        "component",
        "severity",
        "reason",
        "recommended_remediation",
        "expected_before_live_broker_validation",
    }
    for blocker in diagnostics["blockers"]:
        assert required.issubset(blocker)

    summary = diagnostics["summary"]
    assert summary["total"] == 24
    assert summary["engineering_dashboard_blockers"] > 0
    assert summary["expected_operational_blockers"] > 0
    assert "runtime_supervisor" in summary["engineering_blocker_ids"]
    assert "broker_authentication_state" in summary["expected_operational_blocker_ids"]


def test_phase153a_read_only_blocker_api_is_exposed() -> None:
    client = TestClient(create_app())

    response = client.get("/api/v1/live-readiness-blockers")

    assert response.status_code == 200
    payload = response.json()
    assert payload["payload_version"] == "css.phase153a.live_readiness_blockers.v1"
    assert payload["execution_allowed"] is False


def test_phase153a_heartbeat_uses_fresh_supervisor_timestamp_over_old_artifact_mtime() -> None:
    stale_mtime = time.time() - 3600
    fresh = datetime.datetime.now(datetime.UTC).isoformat()

    state = launcher._heartbeat_state(
        latest_artifact_mtime=stale_mtime,
        supervisor={"last_heartbeat": fresh},
        threshold_seconds=60.0,
    )

    assert state["staleness"] == "ACTIVE"
    assert state["source"] == "supervisor_heartbeat"
    assert state["age_seconds"] <= 60.0


def test_phase153a_heartbeat_preserves_true_stale_detection() -> None:
    stale = (datetime.datetime.now(datetime.UTC) - datetime.timedelta(minutes=10)).isoformat()

    state = launcher._heartbeat_state(
        latest_artifact_mtime=time.time(),
        supervisor={"last_heartbeat": stale},
        threshold_seconds=60.0,
    )

    assert state["staleness"] == "STALE"
    assert state["source"] == "supervisor_heartbeat"


def test_phase153a_runtime_artifact_refresh_publishes_missing_supervisor_snapshot(tmp_path, monkeypatch) -> None:
    artifacts = tmp_path / "artifacts"
    runtime = tmp_path / "runtime" / "supervisor"
    audit = tmp_path / "audit_logs"
    account = artifacts / "css_account_state_pcnrass.json"
    session = artifacts / "css_session_state_pcnrass.json"
    supervisor = runtime / "css_runtime_supervisor_state.json"

    monkeypatch.setattr(launcher.LauncherConfig, "ARTIFACTS_DIR", str(artifacts))
    monkeypatch.setattr(launcher.LauncherConfig, "ACCOUNT_STATE_FILE", str(account))
    monkeypatch.setattr(launcher.LauncherConfig, "SESSION_STATE_FILE", str(session))
    monkeypatch.setattr(launcher.LauncherConfig, "SUPERVISOR_STATE_FILE", str(supervisor))
    monkeypatch.setattr(launcher.LauncherConfig, "CLOSED_TRADE_LEDGER_PATH", str(audit / "closed_trades.jsonl"))

    _write_json(account, {"account_balance": 1000.0})
    _write_json(session, {"session": {"engine_mode": "PAPER", "start_time": NOW.isoformat()}})
    _write_json(artifacts / "portfolio_snapshot.json", {"status": "OK"})
    _write_json(artifacts / "runtime_portfolio_state.json", {"status": "OK"})
    _write_json(artifacts / "runtime_advisory_snapshot.json", {"status": "OK"})
    _write_json(artifacts / "portfolio_decision.json", {"status": "OK"})
    _write_json(artifacts / "validation_summary.json", {"status": "OK"})
    audit.mkdir(parents=True, exist_ok=True)
    (audit / "closed_trades.jsonl").write_text("", encoding="utf-8")

    with patch.object(launcher, "publish_runtime_artifacts", return_value={"status": "OK", "patched": True}):
        result = launcher.ensure_runtime_artifacts_current()

    assert result["status"] == "OK"
    assert result["supervisor_published"]["status"] == "OK"
    assert supervisor.exists()
    assert result["freshness"]["artifacts"]["closed_trade_ledger"]["freshness"] in {"FRESH", "NO_RECENT_TRADES"}
    assert result["execution_allowed"] is False


def test_phase153a_paper_auto_renewal_clears_misleading_reauth_required() -> None:
    payload = {
        "session": {
            "start_time": (NOW - datetime.timedelta(seconds=3700)).isoformat(),
            "max_session_seconds": 3600,
            "engine_mode": "PAPER",
            "broker_mode": "PAPER",
            "broker_execution_enabled": False,
            "session_expired_quiet_mode": True,
        }
    }

    result = RuntimeSessionContinuityMonitor().evaluate(payload, now=NOW)

    assert result["session_continuity_status"] == "ACTIVE"
    assert result["renewal_allowed"] is True
    assert result["reauth_required"] is False
    assert result["can_paper_execute"] is True
    assert result["can_live_execute"] is False


def test_phase153a_live_expiry_still_requires_reauth_and_blocks_execution() -> None:
    payload = {
        "session": {
            "start_time": (NOW - datetime.timedelta(seconds=3700)).isoformat(),
            "max_session_seconds": 3600,
            "engine_mode": "LIVE",
            "broker_mode": "LIVE",
            "broker_execution_enabled": True,
            "session_expired_quiet_mode": True,
        }
    }

    result = RuntimeSessionContinuityMonitor().evaluate(payload, now=NOW)

    assert result["session_continuity_status"] == "REAUTH_REQUIRED"
    assert result["renewal_allowed"] is False
    assert result["live_renewal_blocked"] is True
    assert result["reauth_required"] is True
    assert result["execution_allowed"] is False


def test_phase153a_mobile_top_opportunities_excludes_red_and_uses_amber_fallback(monkeypatch) -> None:
    class FakeRankingEngine:
        def top_opportunities(self, limit: int = 10) -> list[dict]:
            return [
                {"rank": 1, "symbol": "RED1", "signal_color": "RED", "status": "NOT_APPROVED", "opportunity_score": 99, "confidence": 0.99},
                {"rank": 2, "symbol": "GREEN1", "signal_color": "GREEN", "status": "APPROVED", "opportunity_score": 80, "confidence": 0.90},
                {"rank": 3, "symbol": "AMBER1", "signal_color": "AMBER", "status": "WATCH", "opportunity_score": 60, "confidence": 0.60},
            ]

    monkeypatch.setattr(launcher, "OpportunityRankingEngine", FakeRankingEngine)

    feed = launcher.get_top_opportunities_feed(limit=10)

    assert feed["display_state"] == "GREEN_APPROVED"
    assert [row["symbol"] for row in feed["top_opportunities"]] == ["GREEN1"]
    assert "RED1" not in [row["symbol"] for row in feed["top_opportunities"]]
    assert feed["excluded_states"] == ["RED", "NOT_APPROVED"]


def test_phase153a_mobile_top_opportunities_all_red_returns_empty_state(monkeypatch) -> None:
    class FakeRankingEngine:
        def top_opportunities(self, limit: int = 10) -> list[dict]:
            return [
                {"rank": 1, "symbol": "RED1", "signal_color": "RED", "status": "NOT_APPROVED"},
                {"rank": 2, "symbol": "RED2", "risk_state": "RED", "approval_state": "BLOCKED"},
            ]

    monkeypatch.setattr(launcher, "OpportunityRankingEngine", FakeRankingEngine)

    feed = launcher.get_top_opportunities_feed(limit=10)

    assert feed["count"] == 0
    assert feed["display_state"] == "CAPITAL_PRESERVATION"
    assert "Capital preservation" in feed["empty_state"]


def test_phase153a_git_metadata_populates_certification_commit_and_tag_when_available() -> None:
    metadata = git_metadata(Path.cwd())
    report = certify_live_readiness({})

    assert metadata["commit"] != ""
    assert report["commit"] == metadata["commit"]
    assert report["commit"] != "DATA UNAVAILABLE"
    assert "metadata_diagnostics" in report
    if metadata.get("git_tag"):
        assert report["git_tag"] == metadata["git_tag"]
    else:
        assert report["metadata_diagnostics"].get("tag_source") == "no_tag_for_head"


def test_phase153a_launcher_live_readiness_blockers_are_read_only(monkeypatch) -> None:
    monkeypatch.setattr(launcher, "ensure_runtime_artifacts_current", lambda: {"freshness": {"freshness_status": "GREEN"}})
    monkeypatch.setattr(launcher, "get_runtime_session_continuity_feed", lambda: {"session_continuity_status": "ACTIVE"})
    monkeypatch.setattr(launcher, "get_runtime_health_feed", lambda **kwargs: {"runtime_health": "GREEN"})
    monkeypatch.setattr(launcher, "get_supervisor_summary", lambda: {"last_heartbeat": datetime.datetime.now(datetime.UTC).isoformat()})
    monkeypatch.setattr(launcher.os.path, "exists", lambda path: False)

    payload = launcher.get_launcher_live_readiness_blockers_feed()
    response = TestClient(launcher.app).get("/api/v1/live-readiness-blockers")

    assert payload["execution_allowed"] is False
    assert payload["advisory_only"] is True
    assert payload["blocker_count"] < 24
    assert response.status_code == 200
    assert response.json()["execution_allowed"] is False

"""OV002-R1 continuity remediation deterministic tests (no endurance runtime)."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from backend.certification.ov002_continuity import (
    STATE_COMPLETED_ELIGIBLE,
    STATE_INVALIDATED,
    STATE_NOT_CERTIFIED,
    STATE_RUNNING,
    build_process_identity_record,
    classify_restart_event,
    evaluate_final_certification,
    freeze_process_identity,
    reject_historical_attempt2_as_pass,
    transition_attempt_state,
    validate_process_identity,
)
from backend.certification.ov002_endurance_monitor import (
    initialize_run,
    reconcile_supervisor_and_alerts,
    run_monitor_loop,
)
from backend.runtime.css_runtime_supervisor import CSSRuntimeSupervisor


def _identity(pid: int, role: str, now: datetime) -> dict:
    return build_process_identity_record(
        pid=pid,
        role=role,
        attempt_id="",
        baseline_commit="",
        repo_root="C:/rasib/source/capital-strata-systems",
        require_live_fields=True,
    )


def _http_ok():
    return {
        "/api/runtime-mode": (
            200,
            {
                "runtime_mode": "DISABLED",
                "advisory_only": True,
                "fail_closed": True,
                "execution_enabled": False,
            },
        ),
        "/api/v1/live-execution-authority": (
            200,
            {
                "data": {
                    "execution_allowed": False,
                    "can_live_execute": False,
                    "advisory_only": True,
                    "live_authority_state": "BLOCKED",
                }
            },
        ),
        "/health": (200, {"status": "healthy"}),
        "/api/runtime-telemetry": (200, {"schema_version": "test"}),
        "/api/options-income/status": (
            200,
            {"status": "ADVISORY_ONLY", "advisory_only": True, "execution_allowed": False},
        ),
    }


def _supervisor(now: datetime, **overrides) -> dict:
    launcher_identity = _identity(os.getpid(), "launcher", now)
    supervisor_identity = _identity(os.getpid(), "supervisor", now)
    payload = {
        "supervisor_id": "sup-r1",
        "started_at": (now - timedelta(minutes=1)).isoformat(),
        "stopped_at": None,
        "last_heartbeat_at": now.isoformat(),
        "failure_count": 0,
        "restart_count": 0,
        "restart_attempt_count": 0,
        "last_failure": None,
        "failure_history": [],
        "restart_limit_exhausted": False,
        "process_generation": 0,
        "process_identity": {
            "launcher_pid": os.getpid(),
            "supervisor_pid": os.getpid(),
            "launcher": launcher_identity,
            "supervisor": supervisor_identity,
            "managed_services": {
                "CSS Runtime": {**_identity(os.getpid(), "CSS Runtime", now), "generation": 0},
                "Mobile Launcher": {**_identity(os.getpid(), "Mobile Launcher", now), "generation": 0},
            },
        },
        "duplicate_canonical_owners": [],
        "shutdown_requested": False,
        "status": "RUNNING",
        "max_restart_limit": 3,
        "failure_history_path": "runtime/supervisor/css_runtime_supervisor_failure_history.jsonl",
    }
    payload.update(overrides)
    return payload


def test_zero_restart_healthy_attempt_remains_eligible(tmp_path: Path) -> None:
    now = datetime.now(timezone.utc)
    supervisor_path = tmp_path / "sup.json"
    alerts_dir = tmp_path / "alerts"
    alerts_dir.mkdir()
    supervisor_path.write_text(json.dumps(_supervisor(now)), encoding="utf-8")

    def _fake(path: str, timeout: float = 8.0):
        return _http_ok().get(path, (404, {"error": "missing"}))

    with patch("backend.certification.ov002_endurance_monitor._http_json", side_effect=_fake), patch(
        "backend.certification.ov002_endurance_monitor._process_rss_mb",
        return_value={"ok": True, "processes": []},
    ), patch(
        "backend.certification.controlled_shutdown_observation.capture_controlled_shutdown_observation",
        return_value={"ok": True},
    ):
        init = initialize_run(
            output_dir=tmp_path / "pkg",
            supervisor_state_path=supervisor_path,
            alerts_dir=alerts_dir,
        )
        result = run_monitor_loop(
            init["package_dir"],
            target_hours=0.0,
            supervisor_state_path=supervisor_path,
            alerts_dir=alerts_dir,
        )
    assert result["status"] == "COMPLETE"
    assert result["final_certification"]["eligible"] is True
    assert result["final_certification"]["attempt_state"] == STATE_COMPLETED_ELIGIBLE
    assert result["final_certification"]["certification"] == STATE_NOT_CERTIFIED


def test_initial_startup_not_counted_as_restart() -> None:
    classified = classify_restart_event(event_type="initial_startup", restart_count_before=0)
    assert classified["counts_as_restart"] is False
    assert classified["classification"] == "INITIAL_STARTUP"


def test_expected_supervised_restart_recorded_correctly(tmp_path: Path) -> None:
    supervisor = CSSRuntimeSupervisor(state_dir=str(tmp_path / "state"), trusted_root=tmp_path, max_restart_limit=3)
    supervisor.start()
    assert supervisor.restart_count == 0
    supervisor.record_failure("boom", service_name="CSS Runtime", pid_before=1)
    assert supervisor.should_restart() is True
    supervisor.record_restart_attempt("CSS Runtime", attempt=1, delay_seconds=1.0)
    supervisor.record_restart(service_name="CSS Runtime", pid_before=1, pid_after=2)
    assert supervisor.restart_count == 1
    assert any(e.get("event_type") == "unexpected_restart_success" for e in supervisor.failure_history)
    ledger = (tmp_path / "state" / "css_runtime_supervisor_failure_history.jsonl").read_text(encoding="utf-8")
    assert "unexpected_restart_success" in ledger


def test_unexpected_restart_invalidates_when_required() -> None:
    now = datetime.now(timezone.utc)
    freeze = freeze_process_identity(_supervisor(now))
    state = _supervisor(now, restart_count=1, process_generation=1)
    result = reconcile_supervisor_and_alerts(
        supervisor_state=state,
        alerts=[],
        run_meta={"supervisor_identity": freeze, "process_identity_freeze": freeze, "start_utc": now.isoformat()},
        now=now,
    )
    assert result["ok"] is False
    assert "unexpected_supervisor_restart_observed" in result["reasons"]


def test_restart_limit_breach_is_terminal(tmp_path: Path) -> None:
    supervisor = CSSRuntimeSupervisor(state_dir=str(tmp_path / "state"), trusted_root=tmp_path, max_restart_limit=3)
    supervisor.start()
    for i in range(3):
        supervisor.record_failure(f"f{i}")
        assert supervisor.should_restart()
        supervisor.record_restart_attempt("CSS Runtime", attempt=i + 1, delay_seconds=1.0)
        supervisor.record_restart(service_name="CSS Runtime", pid_before=i, pid_after=i + 10)
    supervisor.record_failure("f4")
    assert supervisor.should_restart() is False
    supervisor.record_restart_exhausted("CSS Runtime")
    assert supervisor.restart_limit_exhausted is True
    assert supervisor.restart_count >= 3


def test_duplicate_process_tree_fails_closed() -> None:
    now = datetime.now(timezone.utc)
    freeze = freeze_process_identity(_supervisor(now))
    state = _supervisor(now, duplicate_canonical_owners=[{"pid": 999}])
    reasons = validate_process_identity(frozen=freeze, observed_supervisor_state=state)
    assert "duplicate_canonical_runtime_owner" in reasons


def test_process_identity_mismatch_fails_closed() -> None:
    now = datetime.now(timezone.utc)
    freeze = freeze_process_identity(_supervisor(now))
    state = _supervisor(
        now,
        process_identity={
            "launcher_pid": 100,
            "supervisor_pid": 100,
            "managed_services": {
                "CSS Runtime": {"pid": 999, "generation": 0},
                "Mobile Launcher": {"pid": 300, "generation": 0},
            },
        },
    )
    reasons = validate_process_identity(frozen=freeze, observed_supervisor_state=state)
    assert "process_identity_service_pid_mismatch:CSS Runtime" in reasons


def test_heartbeat_loss_durable_and_recovery_does_not_erase() -> None:
    now = datetime.now(timezone.utc)
    alerts = [
        {
            "alert_id": "a1",
            "timestamp": now.isoformat(),
            "severity": "CRITICAL",
            "message": "ENGINE_HEARTBEAT_LOST",
            "metadata": {"event_type": "ENGINE_HEARTBEAT_LOST"},
        }
    ]
    first = reconcile_supervisor_and_alerts(
        supervisor_state=_supervisor(now),
        alerts=alerts,
        run_meta={"start_utc": (now - timedelta(minutes=1)).isoformat()},
        now=now,
    )
    assert "engine_heartbeat_lost" in first["reasons"]
    # Later healthy alerts empty — prior invalidation artifact still terminal via final gate.
    recovered = evaluate_final_certification(
        run_meta={"run_id": "OV002-X", "frozen_sha": "abc"},
        run_status={"status": "INVALIDATED"},
        invalidation={"reasons": ["engine_heartbeat_lost"]},
        reconciliation_ok=True,
        reconciliation_reasons=[],
        alert_errors=[],
        expected_run_id="OV002-X",
        expected_commit="abc",
    )
    assert recovered.attempt_state == STATE_INVALIDATED
    assert recovered.eligible is False


def test_unresolved_critical_alert_and_malformed_evidence_prevent_pass() -> None:
    bad = evaluate_final_certification(
        run_meta={"run_id": "OV002-X", "frozen_sha": "abc"},
        run_status={"status": "COMPLETE"},
        invalidation=None,
        reconciliation_ok=False,
        reconciliation_reasons=["engine_heartbeat_lost"],
        alert_errors=["alert_malformed:x.json"],
        expected_run_id="OV002-X",
        expected_commit="abc",
    )
    assert bad.eligible is False
    assert bad.certification == STATE_NOT_CERTIFIED


def test_attempt_id_and_commit_mismatch_prevent_pass() -> None:
    result = evaluate_final_certification(
        run_meta={"run_id": "OV002-A", "frozen_sha": "sha1"},
        run_status={"status": "COMPLETE"},
        invalidation=None,
        reconciliation_ok=True,
        reconciliation_reasons=[],
        alert_errors=[],
        expected_run_id="OV002-B",
        expected_commit="sha2",
    )
    assert "attempt_id_mismatch" in result.reasons
    assert "commit_mismatch" in result.reasons


def test_invalidated_cannot_transition_back_to_running() -> None:
    with pytest.raises(Exception) as exc:
        transition_attempt_state(STATE_INVALIDATED, STATE_RUNNING)
    assert "invalidated_terminal" in str(exc.value)


def test_historical_attempt2_cannot_be_reclassified_as_valid() -> None:
    result = reject_historical_attempt2_as_pass(
        {
            "elapsed_hours": 72.03,
            "snapshots": 863,
            "restart_count": 8,
            "heartbeat_lost_count": 2,
            "provisional_recommendation": "ENDURANCE PASS WITH RESIDUALS",
        }
    )
    assert result.attempt_state == STATE_INVALIDATED
    assert result.eligible is False
    assert "historical_attempt2_invalidated" in result.reasons

"""OV-002 endurance monitor unit tests (no 72h wait)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from backend.certification.ov002_endurance_monitor import (
    capture_safety_assertions,
    evaluate_invalidation,
    initialize_run,
    reconcile_supervisor_and_alerts,
    run_monitor_loop,
)


def test_safety_assertions_pass_with_mocks() -> None:
    responses = {
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
                    "authority_reason": "Credentials Invalid",
                }
            },
        ),
        "/health": (200, {"status": "healthy", "service": "css_mobile_launcher"}),
    }

    def _fake(path: str, timeout: float = 8.0):
        return responses[path]

    with patch("backend.certification.ov002_endurance_monitor._http_json", side_effect=_fake):
        result = capture_safety_assertions()
    assert result["ok"] is True
    assert result["execution_allowed"] is False
    assert result["can_live_execute"] is False
    assert result["non_claims"]["phase181"] == "NOT_CERTIFIED"


def test_invalidation_on_live_execution() -> None:
    invalid = evaluate_invalidation(
        {
            "execution_allowed": True,
            "can_live_execute": False,
            "commit_drift": False,
            "health_http": 200,
            "runtime_http": 200,
            "elapsed_hours_wall_clock": 1.0,
        },
        last_snapshot_epoch=None,
    )
    assert invalid is not None
    assert "live_execution_enabled" in invalid["reasons"]


def test_initialize_and_once_snapshot(tmp_path: Path) -> None:
    now = datetime.now(timezone.utc)
    supervisor_path = tmp_path / "runtime" / "supervisor" / "css_runtime_supervisor_state.json"
    alerts_dir = tmp_path / "runtime" / "alerts"
    _write_supervisor_state(supervisor_path, now=now)
    responses = {
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

    def _fake(path: str, timeout: float = 8.0):
        return responses.get(path, (404, {"error": "missing"}))

    with patch("backend.certification.ov002_endurance_monitor._http_json", side_effect=_fake), patch(
        "backend.certification.ov002_endurance_monitor._process_rss_mb",
        return_value={"ok": True, "processes": []},
    ):
        init = initialize_run(
            output_dir=tmp_path / "ov002",
            supervisor_state_path=supervisor_path,
            alerts_dir=alerts_dir,
        )
        assert init["ok"] is True
        result = run_monitor_loop(
            init["package_dir"],
            once=True,
            target_hours=72.0,
            supervisor_state_path=supervisor_path,
            alerts_dir=alerts_dir,
        )
    assert result["status"] == "RUNNING"
    assert (tmp_path / "ov002" / "RUN_META.json").is_file()
    assert (tmp_path / "ov002" / "SAFETY_ASSERTIONS.json").is_file()
    assert list((tmp_path / "ov002" / "snapshots").glob("health_*.json"))


def _http_responses() -> dict[str, tuple[int, dict]]:
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


def _write_supervisor_state(path: Path, *, now: datetime, **overrides) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "supervisor_id": "sup-1",
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
            "launcher_pid": 10,
            "supervisor_pid": 10,
            "managed_services": {
                "CSS Runtime": {"pid": 20, "generation": 0},
                "Mobile Launcher": {"pid": 30, "generation": 0},
            },
        },
        "shutdown_requested": False,
        "status": "RUNNING",
        "max_restart_limit": 3,
    }
    payload.update(overrides)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return payload


def _write_alert(path: Path, *, timestamp: datetime, severity: str, message: str, **overrides) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "alert_id": path.stem,
        "timestamp": timestamp.isoformat(),
        "alert_type": "ENGINE",
        "severity": severity,
        "message": message,
        "source": "runtime_supervisor",
        "metadata": {"event_type": "ENGINE_HEARTBEAT_LOST"},
    }
    payload.update(overrides)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _initialized_run(tmp_path: Path, *, now: datetime) -> tuple[dict, Path, Path]:
    supervisor_path = tmp_path / "runtime" / "supervisor" / "css_runtime_supervisor_state.json"
    alerts_dir = tmp_path / "runtime" / "alerts"
    _write_supervisor_state(supervisor_path, now=now)

    def _fake(path: str, timeout: float = 8.0):
        return _http_responses().get(path, (404, {"error": "missing"}))

    with patch("backend.certification.ov002_endurance_monitor._http_json", side_effect=_fake), patch(
        "backend.certification.ov002_endurance_monitor._process_rss_mb",
        return_value={"ok": True, "processes": []},
    ):
        init = initialize_run(
            output_dir=tmp_path / "ov002",
            supervisor_state_path=supervisor_path,
            alerts_dir=alerts_dir,
        )
    assert init["ok"] is True
    return init, supervisor_path, alerts_dir


def _run_once(init: dict, supervisor_path: Path, alerts_dir: Path) -> dict:
    def _fake(path: str, timeout: float = 8.0):
        return _http_responses().get(path, (404, {"error": "missing"}))

    with patch("backend.certification.ov002_endurance_monitor._http_json", side_effect=_fake), patch(
        "backend.certification.ov002_endurance_monitor._process_rss_mb",
        return_value={"ok": True, "processes": []},
    ):
        return run_monitor_loop(
            init["package_dir"],
            once=True,
            supervisor_state_path=supervisor_path,
            alerts_dir=alerts_dir,
        )


def test_http_healthy_plus_engine_heartbeat_lost_invalidates(tmp_path: Path) -> None:
    now = datetime.now(timezone.utc)
    init, supervisor_path, alerts_dir = _initialized_run(tmp_path, now=now)
    _write_alert(
        alerts_dir / "heartbeat_lost.json",
        timestamp=now + timedelta(seconds=1),
        severity="CRITICAL",
        message="ENGINE_HEARTBEAT_LOST - Engine heartbeat lost",
    )

    result = _run_once(init, supervisor_path, alerts_dir)

    assert result["status"] == "INVALIDATED"
    assert "engine_heartbeat_lost" in result["invalidation"]["reasons"]
    status = json.loads((Path(init["package_dir"]) / "RUN_STATUS.json").read_text(encoding="utf-8"))
    assert status["recommendation_pending"] == "ENDURANCE INVALIDATED"
    assert status["invalidation_events"][0]["timestamp"]


def test_supervisor_restart_observed_by_monitor_invalidates(tmp_path: Path) -> None:
    now = datetime.now(timezone.utc)
    init, supervisor_path, alerts_dir = _initialized_run(tmp_path, now=now)
    _write_supervisor_state(
        supervisor_path,
        now=now,
        restart_count=1,
        process_generation=1,
        failure_history=[
            {
                "event_type": "unexpected_restart_success",
                "timestamp": now.isoformat(),
                "service_name": "CSS Runtime",
                "pid_before": 20,
                "pid_after": 21,
                "reason": "unexpected_restart_success",
            }
        ],
    )

    result = _run_once(init, supervisor_path, alerts_dir)

    assert result["status"] == "INVALIDATED"
    assert "unexpected_supervisor_restart_observed" in result["invalidation"]["reasons"]
    assert "process_generation_changed" in result["invalidation"]["reasons"]


def test_irreversible_invalidation_cannot_become_pass(tmp_path: Path) -> None:
    now = datetime.now(timezone.utc)
    init, supervisor_path, alerts_dir = _initialized_run(tmp_path, now=now)
    _write_alert(
        alerts_dir / "heartbeat_lost.json",
        timestamp=now + timedelta(seconds=1),
        severity="CRITICAL",
        message="ENGINE_HEARTBEAT_LOST",
    )
    first = _run_once(init, supervisor_path, alerts_dir)
    assert first["status"] == "INVALIDATED"

    _write_supervisor_state(supervisor_path, now=now + timedelta(seconds=2))
    result = _run_once(init, supervisor_path, alerts_dir)

    assert result["status"] == "INVALIDATED"
    status = json.loads((Path(init["package_dir"]) / "RUN_STATUS.json").read_text(encoding="utf-8"))
    assert status["status"] == "INVALIDATED"
    assert status["recommendation_pending"] == "ENDURANCE INVALIDATED"


def test_clean_uninterrupted_advisory_run_can_complete(tmp_path: Path) -> None:
    now = datetime.now(timezone.utc)
    init, supervisor_path, alerts_dir = _initialized_run(tmp_path, now=now)

    def _fake(path: str, timeout: float = 8.0):
        return _http_responses().get(path, (404, {"error": "missing"}))

    with patch("backend.certification.ov002_endurance_monitor._http_json", side_effect=_fake), patch(
        "backend.certification.ov002_endurance_monitor._process_rss_mb",
        return_value={"ok": True, "processes": []},
    ), patch(
        "backend.certification.controlled_shutdown_observation.capture_controlled_shutdown_observation",
        return_value={"ok": True, "controlled": True},
    ):
        result = run_monitor_loop(
            init["package_dir"],
            target_hours=0.0,
            supervisor_state_path=supervisor_path,
            alerts_dir=alerts_dir,
        )

    assert result["status"] == "COMPLETE"
    status = json.loads((Path(init["package_dir"]) / "RUN_STATUS.json").read_text(encoding="utf-8"))
    assert status["recommendation_pending"] == "ENDURANCE PASS WITH RESIDUALS"


def test_controlled_shutdown_history_not_misclassified_as_unexpected(tmp_path: Path) -> None:
    now = datetime.now(timezone.utc)
    state = _write_supervisor_state(
        tmp_path / "state.json",
        now=now,
        status="STOPPED",
        shutdown_requested=True,
        stopped_at=now.isoformat(),
        failure_history=[
            {
                "event_type": "controlled_shutdown",
                "timestamp": now.isoformat(),
                "reason": "shutdown_requested",
            }
        ],
    )
    result = reconcile_supervisor_and_alerts(
        supervisor_state=state,
        alerts=[],
        run_meta={"start_utc": (now - timedelta(minutes=2)).isoformat()},
        now=now,
    )
    assert "unexpected_restart_alert" not in result["reasons"]
    assert "unexpected_supervisor_restart_observed" not in result["reasons"]


def test_reconcile_detects_duplicate_owner_and_restart_limits() -> None:
    now = datetime.now(timezone.utc)
    state = {
        "supervisor_id": "sup-1",
        "started_at": now.isoformat(),
        "last_heartbeat_at": now.isoformat(),
        "restart_count": 4,
        "restart_attempt_count": 4,
        "max_restart_limit": 3,
        "process_generation": 4,
        "status": "FAILED",
        "restart_limit_exhausted": True,
        "failure_history": [],
        "duplicate_canonical_owners": [{"pid": 999}],
    }

    result = reconcile_supervisor_and_alerts(
        supervisor_state=state,
        alerts=[],
        run_meta={"start_utc": (now - timedelta(minutes=1)).isoformat()},
        now=now,
    )

    assert "duplicate_canonical_runtime_owner" in result["reasons"]
    assert "restart_limit_exceeded" in result["reasons"]
    assert "restart_attempt_limit_exceeded" in result["reasons"]
    assert "restart_limit_exhausted" in result["reasons"]


def test_reconcile_detects_stale_malformed_and_future_timestamps(tmp_path: Path) -> None:
    now = datetime.now(timezone.utc)
    stale = _write_supervisor_state(
        tmp_path / "stale.json",
        now=now,
        last_heartbeat_at=(now - timedelta(hours=1)).isoformat(),
    )
    malformed = _write_supervisor_state(
        tmp_path / "malformed.json",
        now=now,
        last_heartbeat_at="not-a-time",
    )
    future = _write_supervisor_state(
        tmp_path / "future.json",
        now=now,
        last_heartbeat_at=(now + timedelta(hours=1)).isoformat(),
    )
    missing = _write_supervisor_state(
        tmp_path / "missing.json",
        now=now,
        last_heartbeat_at=None,
    )
    non_finite = _write_supervisor_state(
        tmp_path / "non_finite.json",
        now=now,
        last_heartbeat_at=float("nan"),
    )

    base_meta = {"start_utc": (now - timedelta(minutes=5)).isoformat()}
    assert "supervisor_heartbeat_stale" in reconcile_supervisor_and_alerts(
        supervisor_state=stale,
        alerts=[],
        run_meta=base_meta,
        now=now,
    )["reasons"]
    assert "supervisor_last_heartbeat_at_malformed" in reconcile_supervisor_and_alerts(
        supervisor_state=malformed,
        alerts=[],
        run_meta=base_meta,
        now=now,
    )["reasons"]
    assert "supervisor_last_heartbeat_at_future_skew" in reconcile_supervisor_and_alerts(
        supervisor_state=future,
        alerts=[],
        run_meta=base_meta,
        now=now,
    )["reasons"]
    assert "supervisor_last_heartbeat_at_missing" in reconcile_supervisor_and_alerts(
        supervisor_state=missing,
        alerts=[],
        run_meta=base_meta,
        now=now,
    )["reasons"]
    assert "supervisor_last_heartbeat_at_non_finite" in reconcile_supervisor_and_alerts(
        supervisor_state=non_finite,
        alerts=[],
        run_meta=base_meta,
        now=now,
    )["reasons"]

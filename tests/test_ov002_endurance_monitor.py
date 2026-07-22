"""OV-002 endurance monitor unit tests (no 72h wait)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from backend.certification.ov002_endurance_monitor import (
    capture_safety_assertions,
    evaluate_invalidation,
    initialize_run,
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

    with patch("backend.certification.ov002_endurance_monitor._http_json", side_effect=_fake):
        init = initialize_run(output_dir=tmp_path / "ov002")
        assert init["ok"] is True
        result = run_monitor_loop(init["package_dir"], once=True, target_hours=72.0)
    assert result["status"] == "RUNNING"
    assert (tmp_path / "ov002" / "RUN_META.json").is_file()
    assert (tmp_path / "ov002" / "SAFETY_ASSERTIONS.json").is_file()
    assert list((tmp_path / "ov002" / "snapshots").glob("health_*.json"))

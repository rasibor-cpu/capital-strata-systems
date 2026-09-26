from unittest.mock import MagicMock, patch

import launcher.css_runtime_launcher as runtime_launcher
import backend.certification.ov002_endurance_monitor as ov002


def _running_mobile():
    svc = MagicMock()
    svc.service_name = "Mobile Launcher"
    svc.status = "RUNNING"
    svc.check_status.return_value = "RUNNING"
    return svc


def test_mobile_liveness_success_resets_failure_counter():
    svc = _running_mobile()

    with patch.object(runtime_launcher, "probe_mobile_http_health", return_value=True):
        result = runtime_launcher.monitor_mobile_http_liveness(svc, 2)

    assert result == 0
    assert svc.status == "RUNNING"


def test_mobile_liveness_first_two_failures_do_not_restart_or_mark_failed():
    svc = _running_mobile()

    with patch.object(runtime_launcher, "probe_mobile_http_health", return_value=False):
        first = runtime_launcher.monitor_mobile_http_liveness(svc, 0)
        second = runtime_launcher.monitor_mobile_http_liveness(svc, first)

    assert first == 1
    assert second == 2
    assert svc.status == "RUNNING"


def test_mobile_liveness_third_consecutive_failure_escalates():
    svc = _running_mobile()

    with patch.object(runtime_launcher, "probe_mobile_http_health", return_value=False):
        result = runtime_launcher.monitor_mobile_http_liveness(svc, 2)

    assert result == runtime_launcher.MOBILE_HEALTH_FAILURE_THRESHOLD
    assert svc.status == "FAILED"


def test_http_confirmation_recovers_after_single_transport_timeout():
    calls = [
        (None, {"error": "timed out"}),
        (200, {"status": "healthy"}),
    ]

    with patch.object(ov002, "_http_json", side_effect=calls), patch.object(
        ov002.time, "sleep"
    ):
        status, payload, meta = ov002._http_json_confirmed(
            "/health",
            attempts=3,
            delay_seconds=0,
        )

    assert status == 200
    assert payload["status"] == "healthy"
    assert meta["attempts"] == 2
    assert meta["recovered_after_transport_failure"] is True


def test_http_confirmation_persistent_transport_failure_remains_unreachable():
    with patch.object(
        ov002,
        "_http_json",
        return_value=(None, {"error": "timed out"}),
    ), patch.object(ov002.time, "sleep"):
        status, payload, meta = ov002._http_json_confirmed(
            "/health",
            attempts=3,
            delay_seconds=0,
        )

    assert status is None
    assert payload["error"] == "timed out"
    assert meta["attempts"] == 3
    assert meta["recovered_after_transport_failure"] is False


def test_http_confirmation_does_not_retry_real_http_failure():
    with patch.object(
        ov002,
        "_http_json",
        return_value=(503, {"error": "service unavailable"}),
    ) as request:
        status, payload, meta = ov002._http_json_confirmed(
            "/health",
            attempts=3,
            delay_seconds=0,
        )

    assert status == 503
    assert payload["error"] == "service unavailable"
    assert meta["attempts"] == 1
    request.assert_called_once()


def test_persistent_transport_failure_still_invalidates():
    invalid = ov002.evaluate_invalidation(
        {
            "execution_allowed": False,
            "can_live_execute": False,
            "commit_drift": False,
            "health_http": None,
            "runtime_http": None,
            "elapsed_hours_wall_clock": 1.0,
        },
        last_snapshot_epoch=None,
    )

    assert invalid is not None
    assert "health_unreachable" in invalid["reasons"]
    assert "runtime_mode_unreachable" in invalid["reasons"]

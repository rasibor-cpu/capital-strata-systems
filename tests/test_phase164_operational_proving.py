from __future__ import annotations

from fastapi.testclient import TestClient

from backend.runtime.operational_proving import (
    build_operational_proving_report,
    certification_history_trend,
    load_certification_history,
    persist_certification_snapshot,
)
from backend.runtime.runtime_certification_snapshot import build_runtime_certification_snapshot
from dashboard.runtime.api_bridge import create_app
from dashboard.runtime.dashboard_state import DashboardState
from dashboard.runtime.frontend_contract import build_frontend_payload
import launcher.css_mobile_launcher as launcher


def _phase156b(certification: str = "AMBER") -> dict:
    return {
        "broker": "COINBASE",
        "mode": "live",
        "phase156a": "GREEN",
        "authentication": "PASS",
        "account": "PASS",
        "market_data": "PASS",
        "certification": certification,
        "latency_status": certification,
        "connectivity_score": 95.0,
        "latency": {
            "authentication_ms": 40,
            "account_ms": 70,
            "market_data_ms": 35,
            "active_validation_ms": 145,
            "overall_ms": 180,
        },
        "stage_results": {
            "execution_firewall": {"status": "PASS"},
            "market_data": {
                "status": "PASS",
                "details": {
                    "evidence": [
                        {"symbol": "BTC-USD", "success": True, "timestamp": "2026-07-10T12:00:00+00:00"},
                        {"symbol": "ETH-USD", "success": True, "timestamp": "2026-07-10T12:00:00+00:00"},
                    ]
                },
            },
        },
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "advisory_only": True,
    }


def _phase156c(health: str = "AMBER") -> dict:
    return {
        "broker": "COINBASE",
        "health": health,
        "overall_health_score": 87.0,
        "market_data_freshness": {
            "status": "GREEN",
            "reason": "fresh",
            "timestamp": "2026-07-10T12:00:00+00:00",
            "missing_quotes": [],
        },
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "advisory_only": True,
    }


def _snapshot(certification: str = "AMBER", health: str = "AMBER") -> dict:
    return build_runtime_certification_snapshot(
        "coinbase",
        cycle_id=1,
        phase156b=_phase156b(certification),
        phase156c=_phase156c(health),
        telemetry={
            "certification_execution_ms": 150,
            "broker_api_calls_performed": 4,
            "cache_hits": 3,
            "cache_misses": 1,
            "runtime_cycle_duration_ms": 250,
        },
    )


def _runtime_health(status: str = "GREEN") -> dict:
    return {
        "runtime_health": status,
        "overall_operational_health": status,
        "heartbeat_age": 10,
        "restart_count": 0,
        "recovery_count": 0,
        "warnings": [],
        "execution_allowed": False,
        "advisory_only": True,
    }


def _performance() -> dict:
    return {
        "overall_status": "GREEN",
        "pipeline_latency_ms": 200,
        "dashboard_latency_ms": 120,
        "api_latency_ms": 25,
        "cache_hit_rate": 80.0,
        "memory_usage": {"rss_kb": 100000},
        "cpu_usage": {"process_time_seconds": 1.5},
        "execution_allowed": False,
        "advisory_only": True,
    }


def test_phase164_operational_score_and_metrics_are_advisory() -> None:
    report = build_operational_proving_report(
        runtime_summary={"startup_timestamp": "2026-07-10T12:00:00+00:00", "uptime_seconds": 3600, "restart_count": 0},
        runtime_health=_runtime_health(),
        runtime_performance=_performance(),
        certification_snapshot=_snapshot(),
        history=[],
        now=1770000000,
    )

    assert report["operational_scorecard"]["overall_operational_score"] >= 70
    assert report["runtime_metrics"]["heartbeat_continuity"]["status"] == "PASS"
    assert report["runtime_metrics"]["broker_latency"]["active_validation_ms"] == 145
    assert report["execution_allowed"] is False
    assert report["live_trading_blocked"] is True
    assert report["broker_execution_armed"] is False
    assert report["advisory_only"] is True


def test_phase164_persists_certification_history_and_generates_trend(tmp_path) -> None:
    path = tmp_path / "history.json"
    persist_certification_snapshot(_snapshot("AMBER"), path, now=1770000000)
    persist_certification_snapshot(_snapshot("GREEN", "GREEN"), path, now=1770000060)

    history = load_certification_history(path)
    trend = certification_history_trend(history)

    assert len(history) == 2
    assert trend["latest_certification"] == "GREEN"
    assert trend["red_certification_count"] == 0
    assert trend["stable_amber_green_trend"] is True
    assert history[-1]["execution_state"]["execution_allowed"] is False


def test_phase164_pre_pilot_gate_blocks_red_and_safety_bypass() -> None:
    unsafe = _snapshot("RED", "RED")
    unsafe["execution_allowed"] = True
    report = build_operational_proving_report(
        runtime_summary={"uptime_seconds": 1000, "restart_count": 0},
        runtime_health=_runtime_health(),
        runtime_performance=_performance(),
        certification_snapshot=unsafe,
        history=[],
    )

    gate = report["pre_pilot_gate"]
    assert gate["eligible"] is False
    assert "red_certification_present" in gate["blockers"]
    assert "execution_firewall_not_preserved" in gate["blockers"]
    assert report["operational_scorecard"]["dimensions"]["safety"] == 0.0
    assert gate["execution_allowed"] is False


def test_phase164_frontend_and_runtime_api_surface_rc1_dashboard() -> None:
    snapshot = _snapshot()
    state = DashboardState()
    state.broker_state.selected_broker = "COINBASE"
    state.broker_state.runtime_certification_snapshot = snapshot
    state.broker_state.runtime_certification_snapshots = {"COINBASE": snapshot}
    state.last_scan_results["runtime_health"] = _runtime_health()
    state.last_scan_results["runtime_performance"] = _performance()
    state.last_scan_results["opportunities"] = []

    frontend = build_frontend_payload(state)
    assert frontend["sections"]["rc1_operational_dashboard"]["payload_version"].startswith("css.phase164")
    assert frontend["sections"]["rc1_operational_dashboard"]["pre_pilot_gate"]["execution_allowed"] is False

    response = TestClient(create_app(lambda: state)).get("/api/v1/rc1-operational-dashboard")
    assert response.status_code == 200
    assert response.json()["section"] == "rc1_operational_dashboard"
    assert response.json()["data"]["advisory_only"] is True


def test_phase164_launcher_persists_history_without_execution_authority(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(launcher.LauncherConfig, "ARTIFACTS_DIR", str(tmp_path))
    monkeypatch.setattr(launcher, "get_runtime_summary", lambda: {"uptime_seconds": 500, "restart_count": 0})
    monkeypatch.setattr(launcher, "get_runtime_performance_feed", lambda: _performance())
    monkeypatch.setattr(launcher, "get_runtime_health_feed", lambda performance=None: _runtime_health())
    monkeypatch.setattr(launcher, "get_launcher_runtime_certification_snapshot_feed", lambda: _snapshot())

    report = launcher.get_launcher_rc1_operational_dashboard_feed()
    history = load_certification_history(tmp_path / "rc1_operational_certification_history.json")

    assert report["payload_version"].startswith("css.phase164")
    assert len(history) == 1
    assert report["pre_pilot_gate"]["execution_allowed"] is False
    assert report["pre_pilot_gate"]["live_trading_blocked"] is True

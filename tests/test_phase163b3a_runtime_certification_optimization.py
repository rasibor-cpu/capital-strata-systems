from __future__ import annotations

from fastapi.testclient import TestClient

from backend.runtime.runtime_certification_snapshot import (
    build_runtime_certification_snapshot,
    clear_runtime_certification_snapshot_cache,
    get_runtime_certification_snapshot,
    runtime_certification_diagnostics,
)
from dashboard.runtime.api_bridge import create_app
from dashboard.runtime.dashboard_state import DashboardState
from dashboard.runtime.frontend_contract import build_frontend_payload
import launcher.css_mobile_launcher as launcher


def _phase156b(
    broker: str = "COINBASE",
    *,
    certification: str = "GREEN",
    auth: str = "PASS",
    account: str = "PASS",
    market_data: str = "PASS",
) -> dict:
    symbols = ["EUR_USD", "USD_JPY"] if broker.upper() == "OANDA" else ["BTC-USD", "ETH-USD"]
    return {
        "payload_version": "css.phase156b.live_connectivity_certification.v1",
        "broker": broker.upper(),
        "mode": "live",
        "phase156a": "GREEN" if certification != "RED" else "RED",
        "authentication": auth,
        "account": account,
        "market_data": market_data,
        "latency": {
            "authentication_ms": 45,
            "account_ms": 70,
            "market_data_ms": 35,
            "active_validation_ms": 150,
            "overall_ms": 160,
        },
        "latency_status": "GREEN" if certification == "GREEN" else "RED",
        "connectivity_score": 97.5 if certification != "RED" else 0.0,
        "certification": certification,
        "blocker_reasons": [] if certification != "RED" else ["phase156a_not_green"],
        "stage_results": {
            "account": {"status": account, "details": {"balance": "100.00"}},
            "market_data": {
                "status": market_data,
                "details": {
                    "timestamp": "2026-07-10T12:00:00+00:00",
                    "missing_symbols": [],
                    "evidence": [
                        {"symbol": symbol, "success": True, "timestamp": "2026-07-10T12:00:00+00:00"}
                        for symbol in symbols
                    ],
                },
            },
            "execution_firewall": {"status": "PASS"},
        },
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "advisory_only": True,
    }


def _phase156c(broker: str = "COINBASE", health: str = "GREEN") -> dict:
    return {
        "payload_version": "css.phase156c.broker_health_monitor.v1",
        "broker": broker.upper(),
        "mode": "live",
        "health": health,
        "overall_score": 91.0 if health != "RED" else 0.0,
        "overall_health_score": 91.0 if health != "RED" else 0.0,
        "latency_health": health,
        "market_data_freshness": {
            "status": health,
            "reason": "fresh" if health != "RED" else "missing_quotes",
            "timestamp": "2026-07-10T12:00:00+00:00",
            "missing_quotes": [],
        },
        "blocker_reasons": [] if health != "RED" else ["market_data_failed"],
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "advisory_only": True,
    }


def setup_function() -> None:
    clear_runtime_certification_snapshot_cache()


def test_phase163b3a_reuses_canonical_certification_once_per_cycle() -> None:
    calls: list[tuple[str, str]] = []
    health_seen: list[dict] = []

    def certifier(broker: str, *, mode: str = "live") -> dict:
        calls.append((broker, mode))
        return _phase156b(broker)

    def health_monitor(broker: str, *, mode: str = "live", connectivity_certifier_fn=None) -> dict:
        assert connectivity_certifier_fn is not None
        health_seen.append(connectivity_certifier_fn(broker, mode=mode))
        return _phase156c(broker)

    first = get_runtime_certification_snapshot(
        "coinbase",
        cycle_id=42,
        certifier_fn=certifier,
        health_monitor_fn=health_monitor,
    )
    second = get_runtime_certification_snapshot(
        "coinbase",
        cycle_id=42,
        certifier_fn=certifier,
        health_monitor_fn=health_monitor,
    )

    assert calls == [("coinbase", "live")]
    assert health_seen[0]["certification"] == "GREEN"
    assert first == second
    assert first["certification"] == "GREEN"
    assert first["execution_allowed"] is False
    assert first["live_trading_blocked"] is True
    assert first["broker_execution_armed"] is False
    assert first["advisory_only"] is True


def test_phase163b3a_cache_and_capability_telemetry() -> None:
    calls = 0

    def certifier(broker: str, *, mode: str = "live") -> dict:
        nonlocal calls
        calls += 1
        return _phase156b(broker)

    first = get_runtime_certification_snapshot("oanda", cycle_id="A", certifier_fn=certifier)
    second = get_runtime_certification_snapshot("oanda", cycle_id="A", certifier_fn=certifier)
    refreshed = get_runtime_certification_snapshot("oanda", cycle_id="A", force_refresh=True, certifier_fn=certifier)
    diagnostics = runtime_certification_diagnostics(refreshed)

    assert calls == 2
    assert first == second
    assert first["telemetry"]["capability_cache_status"] == "MISS"
    assert refreshed["telemetry"]["capability_cache_status"] == "HIT"
    assert diagnostics["cache_hits"] >= 1
    assert diagnostics["cache_misses"] >= 2
    assert diagnostics["broker_api_calls_performed"] >= refreshed["telemetry"]["broker_api_calls_performed"]
    assert diagnostics["execution_allowed"] is False


def test_phase163b3a_dashboard_sections_share_same_snapshot_values() -> None:
    snapshot = build_runtime_certification_snapshot(
        "coinbase",
        cycle_id=7,
        phase156b=_phase156b("COINBASE"),
        phase156c=_phase156c("COINBASE"),
        source="test",
        telemetry={
            "certification_execution_ms": 10,
            "broker_api_calls_performed": 4,
            "cache_hits": 2,
            "cache_misses": 1,
            "runtime_cycle_duration_ms": 11,
        },
    )
    state = DashboardState()
    state.broker_state.selected_broker = "COINBASE"
    state.broker_state.runtime_certification_snapshot = snapshot
    state.broker_state.runtime_certification_snapshots = {"COINBASE": snapshot}
    state.last_scan_results["opportunities"] = []

    frontend = build_frontend_payload(state)
    sections = frontend["sections"]

    assert sections["runtime_certification_snapshot"]["certification"] == "GREEN"
    assert sections["broker"]["runtime_certification_snapshot"]["certification"] == "GREEN"
    assert sections["broker"]["certification"] == "GREEN"
    assert sections["coinbase_live_validation"]["broker_validation"] == snapshot["phase156b"]
    assert sections["broker_operational_status"]["selected"]["operational_state"] == "READ_ONLY_READY"
    assert sections["runtime_certification_snapshot"]["telemetry"]["broker_api_calls_performed"] == 4


def test_phase163b3a_runtime_api_exposes_same_snapshot_and_diagnostics() -> None:
    snapshot = build_runtime_certification_snapshot(
        "oanda",
        cycle_id=8,
        phase156b=_phase156b("OANDA"),
        phase156c=_phase156c("OANDA"),
        source="test",
        telemetry={
            "certification_execution_ms": 12,
            "broker_api_calls_performed": 5,
            "cache_hits": 3,
            "cache_misses": 1,
            "runtime_cycle_duration_ms": 13,
        },
    )
    state = DashboardState()
    state.broker_state.selected_broker = "OANDA"
    state.broker_state.runtime_certification_snapshot = snapshot
    state.broker_state.runtime_certification_snapshots = {"OANDA": snapshot}
    state.last_scan_results["opportunities"] = []
    client = TestClient(create_app(lambda: state))

    snapshot_response = client.get("/api/v1/runtime-certification-snapshot")
    diagnostics_response = client.get("/api/v1/runtime-certification-diagnostics")
    oanda_response = client.get("/api/v1/oanda-live-read-only-validation")

    assert snapshot_response.status_code == 200
    assert snapshot_response.json()["data"]["certification"] == "GREEN"
    assert diagnostics_response.status_code == 200
    assert diagnostics_response.json()["data"]["certification_execution_ms"] == 12
    assert diagnostics_response.json()["data"]["broker_api_calls_performed"] == 5
    assert oanda_response.json()["data"]["broker_validation"] == snapshot["phase156b"]
    assert oanda_response.json()["data"]["execution_allowed"] is False


def test_phase163b3a_launcher_builds_snapshot_from_artifacts_without_broker_calls(monkeypatch) -> None:
    launcher._LAUNCHER_RUNTIME_CERTIFICATION_SNAPSHOT_CACHE.clear()
    monkeypatch.setattr(launcher, "get_runtime_summary", lambda: {"current_cycle": 99})
    monkeypatch.setattr(launcher, "get_broker_startup_summary", lambda: {"selected_broker": "COINBASE"})
    monkeypatch.setattr(launcher, "get_launcher_coinbase_live_validation_feed", lambda: {
        "broker_validation": _phase156b("COINBASE"),
        "broker_health": _phase156c("COINBASE"),
    })
    monkeypatch.setattr(launcher, "get_launcher_oanda_live_validation_feed", lambda: {
        "broker_validation": _phase156b("OANDA"),
        "broker_health": _phase156c("OANDA"),
    })

    snapshots = launcher.get_launcher_runtime_certification_snapshots_feed()
    selected = launcher.get_launcher_runtime_certification_snapshot_feed()
    diagnostics = launcher.get_launcher_runtime_certification_diagnostics_feed()

    assert selected == snapshots["COINBASE"]
    assert selected["certification"] == "GREEN"
    assert selected["telemetry"]["broker_api_calls_performed"] == 0
    assert diagnostics["broker_api_calls_performed"] == 0
    assert diagnostics["execution_allowed"] is False
    assert selected["advisory_only"] is True


def test_phase163b3a_fail_closed_certifier_exception() -> None:
    def broken_certifier(_broker: str, *, mode: str = "live") -> dict:
        raise RuntimeError("broker unavailable")

    snapshot = get_runtime_certification_snapshot(
        "coinbase",
        cycle_id="failure",
        certifier_fn=broken_certifier,
    )

    assert snapshot["certification"] == "RED"
    assert snapshot["operational_state"] == "RED"
    assert snapshot["phase156b"]["execution_allowed"] is False
    assert snapshot["execution_allowed"] is False
    assert snapshot["live_trading_blocked"] is True
    assert snapshot["broker_execution_armed"] is False

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from dashboard.mission_control.contracts import build_mission_control_state
from dashboard.mission_control.runtime_snapshot_normalizer import normalize_runtime_snapshot
from dashboard.mission_control.runtime_snapshot_provider import RuntimeSnapshotProvider
from dashboard.runtime.frontend_contract import DATA_UNAVAILABLE, build_frontend_payload
from launcher import css_mobile_launcher


def _frontend_snapshot(*, heartbeat: str | None = None) -> dict:
    now = heartbeat or datetime.now(timezone.utc).isoformat()
    payload = build_frontend_payload(
        {
            "generated_at": now,
            "session_id": "runtime-session-1",
            "cycle_number": 77,
            "engine_mode": "SAFE",
            "resolved_mode": "paper",
            "session": {
                "session_id": "runtime-session-1",
                "user_id": "operator",
                "role": "TRADER",
                "cycle_number": 77,
                "engine_mode": "SAFE",
                "resolved_mode": "paper",
            },
            "account_summary": {
                "cash_balance": 321.5,
                "total_equity": 654.25,
                "buying_power": 300.0,
                "margin_used": 0.0,
                "currency": "USD",
                "broker": "COINBASE",
                "account_mode": "paper",
            },
            "pnl_summary": {
                "realized_pnl": 10.0,
                "unrealized_pnl": 2.5,
                "net_pnl": 12.5,
                "total_exposure": 111.0,
            },
            "position_state": {
                "open_count": 1,
                "total_exposure": 111.0,
                "positions": [{"symbol": "BTC-USD", "asset_class": "CRYPTO", "exposure": 111.0}],
            },
            "risk_summary": {
                "risk_state": "GREEN",
                "risk_score": 8.0,
                "gate_status": "BLOCKED",
                "current_drawdown": 0.0,
                "total_exposure": 111.0,
            },
            "market_summary": {
                "regime_state": "RISK_ON",
                "trend_state": "UP",
                "volatility_state": "LOW",
                "liquidity_state": "GOOD",
                "momentum_state": "POSITIVE",
                "vwap_state": "ABOVE",
                "spread_state": "TIGHT",
                "signal_confluence_state": "CONFIRMED",
            },
            "broker_summary": {
                "selected_broker": "COINBASE",
                "broker_mode": "paper",
                "broker_health": "GREEN",
                "connection_status": "PASS",
                "authentication_status": "PASS",
                "account_data_health": "PASS",
                "balance_position_status": "PASS",
                "market_data_status": "PASS",
                "buying_power": 300.0,
                "margin_status": "PASS",
                "last_heartbeat": now,
                "execution_scope": "READ_ONLY",
                "state_hash": "broker-hash",
            },
        }
    )
    payload["generated_at"] = now
    payload["mission_control_data_source"] = "RUNTIME"
    return payload


def test_mc003_runtime_provider_normalizes_in_process_frontend_payload() -> None:
    provider = RuntimeSnapshotProvider(lambda: _frontend_snapshot())
    snapshot = provider.get_snapshot()

    assert snapshot["runtime_id"] == "runtime-session-1"
    assert snapshot["session_id"] == "runtime-session-1"
    assert snapshot["source"] == "RUNTIME"
    assert snapshot["heartbeat_status"] in {"FRESH", "AGING"}
    assert snapshot["broker"]["selected_broker"] == "COINBASE"
    assert snapshot["portfolio"]["equity"] == 654.25
    assert snapshot["execution_allowed"] is False
    assert snapshot["live_trading_blocked"] is True
    assert snapshot["broker_execution_armed"] is False


def test_mc003_mission_control_uses_runtime_snapshot_for_overview_values() -> None:
    state = build_mission_control_state(_frontend_snapshot(), allow_mock=False)

    assert state["mock_data"] is False
    assert state["runtime_snapshot"]["source"] == "RUNTIME"
    assert state["platform"]["selected_broker"] == "COINBASE"
    assert state["platform"]["runtime_health"] != DATA_UNAVAILABLE
    assert state["portfolio"]["equity"] == 654.25
    assert state["portfolio"]["cash"] == 321.5
    assert state["portfolio"]["buying_power"] == 300.0
    assert state["portfolio"]["net_pnl"] == 12.5
    assert state["market_intelligence"]["market_regime"] == "RISK_ON"
    assert state["risk"]["overall_risk_state"] == "GREEN"
    assert state["brokers"]["active_broker"]["selected_broker"] == "COINBASE"


def test_mc003_runtime_offline_does_not_emit_demo_financial_values() -> None:
    state = build_mission_control_state(None, allow_mock=False)

    assert state["runtime_snapshot"]["runtime_status"] == "OFFLINE"
    assert state["platform"]["runtime_offline"] is True
    assert state["platform"]["selected_broker"] == "UNAVAILABLE"
    assert state["portfolio"]["equity"] == "UNAVAILABLE"
    assert state["portfolio"]["cash"] == "UNAVAILABLE"
    assert state["portfolio"]["buying_power"] == "UNAVAILABLE"
    assert state["alerts"]["count"] == "UNAVAILABLE"
    assert state["safety"]["execution_allowed"] is False
    assert state["safety"]["live_trading_blocked"] is True


def test_mc003_stale_heartbeat_downgrades_health() -> None:
    old = (datetime.now(timezone.utc) - timedelta(minutes=20)).isoformat()
    state = build_mission_control_state(_frontend_snapshot(heartbeat=old), allow_mock=False)

    assert state["runtime_snapshot"]["heartbeat_status"] == "STALE"
    assert "runtime_heartbeat_stale" in state["health"]["reasons"]
    assert state["health"]["health"] in {"RED", "FAIL_CLOSED"}


def test_mc003_runtime_and_heartbeat_api_share_state_hash() -> None:
    client = TestClient(css_mobile_launcher.app)

    state = client.get("/mission-control/api/state").json()
    runtime = client.get("/mission-control/api/runtime").json()
    heartbeat = client.get("/mission-control/api/heartbeat").json()

    assert runtime["state_hash"] == state["runtime_snapshot"]["state_hash"]
    assert heartbeat["state_hash"] == runtime["state_hash"]
    assert heartbeat["execution_allowed"] is False
    assert heartbeat["live_trading_blocked"] is True
    assert heartbeat["broker_execution_armed"] is False


def test_mc003_mobile_launcher_registers_mission_control_routes_read_only() -> None:
    client = TestClient(css_mobile_launcher.app)
    endpoints = (
        "/mission-control/api/runtime",
        "/mission-control/api/runtime-source",
        "/mission-control/api/heartbeat",
        "/mission-control/executive-overview",
    )

    for endpoint in endpoints:
        assert client.get(endpoint).status_code == 200
        for method in ("post", "put", "patch", "delete"):
            response = getattr(client, method)(endpoint)
            assert response.status_code in {404, 405}


def test_mc003_artifact_snapshot_cache_path_is_read_only_and_cache_labeled(tmp_path) -> None:
    artifacts = tmp_path / "artifacts"
    supervisor_dir = tmp_path / "runtime" / "supervisor"
    artifacts.mkdir()
    supervisor_dir.mkdir(parents=True)
    heartbeat = datetime.now(timezone.utc).isoformat()
    (artifacts / "css_session_state_pcnrass.json").write_text(
        '{"session":{"session_id":"artifact-session","engine_mode":"SAFE","cycle_number":5,"market_regime":"RISK_ON"}}',
        encoding="utf-8",
    )
    (artifacts / "css_account_state_pcnrass.json").write_text(
        '{"account_balance":42.0,"total_equity":45.0,"buying_power":40.0,"lifetime_realized_pnl":1.0,"unrealized_pnl":2.0}',
        encoding="utf-8",
    )
    (supervisor_dir / "css_runtime_supervisor_state.json").write_text(
        f'{{"status":"RUNNING","last_heartbeat":"{heartbeat}","restart_count":1,"failure_count":0}}',
        encoding="utf-8",
    )

    snapshot = RuntimeSnapshotProvider(
        artifact_root=artifacts,
        supervisor_state_path=supervisor_dir / "css_runtime_supervisor_state.json",
    ).get_snapshot()

    assert snapshot["source"] == "CACHE"
    assert snapshot["runtime_id"] == "artifact-session"
    assert snapshot["portfolio"]["equity"] == 45.0
    assert snapshot["advisory_only"] is True
    assert snapshot["execution_allowed"] is False


def test_mc003_demo_payload_is_labeled_and_cannot_masquerade_as_runtime() -> None:
    demo = _frontend_snapshot()
    demo["mission_control_data_source"] = "DEMO"
    snapshot = normalize_runtime_snapshot(demo)

    assert snapshot["source"] == "DEMO"
    assert snapshot["source"] != "RUNTIME"

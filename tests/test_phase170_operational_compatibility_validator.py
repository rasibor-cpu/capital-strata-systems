from __future__ import annotations

from datetime import datetime, timezone

from backend.runtime.canonical_runtime_snapshot import build_canonical_runtime_snapshot, offline_runtime_snapshot
from backend.runtime.operational_compatibility_validator import evaluate_operational_compatibility_views
from dashboard.mission_control.contracts import build_mission_control_state
from dashboard.runtime.frontend_contract import build_frontend_payload


def _frontend_fixture() -> dict:
    now = datetime.now(timezone.utc).isoformat()
    payload = build_frontend_payload(
        {
            "generated_at": now,
            "session_id": "phase170-session",
            "cycle_number": 9,
            "engine_mode": "SAFE",
            "resolved_mode": "paper",
            "session": {
                "session_id": "phase170-session",
                "engine_mode": "SAFE",
                "resolved_mode": "paper",
            },
            "account_summary": {
                "cash_balance": 900.0,
                "total_equity": 1000.0,
                "buying_power": 850.0,
                "margin_used": 0.0,
                "broker": "COINBASE",
                "account_mode": "paper",
            },
            "pnl_summary": {
                "realized_pnl": 5.0,
                "unrealized_pnl": 2.5,
                "net_pnl": 7.5,
                "total_exposure": 120.0,
            },
            "position_state": {
                "open_count": 1,
                "total_exposure": 120.0,
                "positions": [{"symbol": "BTC-USD", "asset_class": "CRYPTO", "exposure": 120.0}],
            },
            "risk_summary": {
                "risk_state": "GREEN",
                "gate_status": "BLOCKED",
                "risk_score": 8.2,
                "total_exposure": 120.0,
                "current_drawdown": 0.0,
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
                "buying_power": 850.0,
                "last_heartbeat": now,
            },
            "runtime_certification_snapshot": {
                "certification": "GREEN",
                "operational_state": "GREEN",
                "broker": "COINBASE",
                "mode": "paper",
            },
        }
    )
    payload["mission_control_data_source"] = "RUNTIME"
    return payload


def test_phase170_validator_passes_for_aligned_views() -> None:
    frontend = _frontend_fixture()
    runtime_snapshot = build_canonical_runtime_snapshot(frontend)
    mission_state = build_mission_control_state(frontend, allow_mock=False)

    report = evaluate_operational_compatibility_views(
        runtime_snapshot=runtime_snapshot,
        frontend_payload=frontend,
        mission_control_state=mission_state,
        source_diagnostics={"selected_source": runtime_snapshot["source"]},
    )

    assert report["status"] == "PASS"
    assert report["summary"]["fail_count"] == 0
    assert any(item["name"] == "broker_consistency" and item["status"] == "PASS" for item in report["checks"])


def test_phase170_validator_detects_broker_mismatch() -> None:
    frontend = _frontend_fixture()
    runtime_snapshot = build_canonical_runtime_snapshot(frontend)
    mission_state = build_mission_control_state(frontend, allow_mock=False)

    mission_state["brokers"]["active_broker"]["selected_broker"] = "OANDA"

    report = evaluate_operational_compatibility_views(
        runtime_snapshot=runtime_snapshot,
        frontend_payload=frontend,
        mission_control_state=mission_state,
        source_diagnostics={"selected_source": runtime_snapshot["source"]},
    )

    mismatch = next(item for item in report["checks"] if item["name"] == "broker_consistency")
    assert mismatch["status"] == "FAIL"
    assert report["status"] == "FAIL_CLOSED"


def test_phase170_validator_detects_invalid_unavailable_projection() -> None:
    frontend = _frontend_fixture()
    runtime_snapshot = offline_runtime_snapshot(reason="test_unavailable")
    mission_state = build_mission_control_state(None, allow_mock=False)

    mission_state["portfolio"]["equity"] = 1000.0

    report = evaluate_operational_compatibility_views(
        runtime_snapshot=runtime_snapshot,
        frontend_payload=frontend,
        mission_control_state=mission_state,
        source_diagnostics={"selected_source": "UNAVAILABLE"},
    )

    unavailable = next(item for item in report["checks"] if item["name"] == "unavailable_projection")
    assert unavailable["status"] == "FAIL"
    assert report["status"] == "FAIL_CLOSED"


def test_phase170_validator_enforces_read_only_safety_flags() -> None:
    frontend = _frontend_fixture()
    runtime_snapshot = build_canonical_runtime_snapshot(frontend)
    mission_state = build_mission_control_state(frontend, allow_mock=False)

    frontend["sections"]["broker"]["execution_allowed"] = True

    report = evaluate_operational_compatibility_views(
        runtime_snapshot=runtime_snapshot,
        frontend_payload=frontend,
        mission_control_state=mission_state,
        source_diagnostics={"selected_source": runtime_snapshot["source"]},
    )

    safety = next(item for item in report["checks"] if item["name"] == "safety_flags")
    assert safety["status"] == "FAIL"
    assert report["status"] == "FAIL_CLOSED"

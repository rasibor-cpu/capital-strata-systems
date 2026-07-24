from __future__ import annotations

from datetime import datetime, timedelta, timezone
from math import inf

from fastapi.testclient import TestClient

from dashboard.mission_control.app import create_app
from dashboard.mission_control.contracts import build_mission_control_state, validate_mission_control_state
from dashboard.mission_control.layout import render_mission_control_shell


def _runtime_payload(*, heartbeat: str | None = None) -> dict:
    now = heartbeat or datetime.now(timezone.utc).isoformat()
    payload = {
        "payload_schema": "css.frontend.contract.v1",
        "generated_at": now,
        "session_id": "mc005-session",
        "cycle_number": 42,
        "engine_mode": "SAFE",
        "resolved_mode": "paper",
        "mission_control_data_source": "RUNTIME",
        "session": {
            "session_id": "mc005-session",
            "user_id": "operator",
            "role": "TRADER",
            "cycle_number": 42,
            "engine_mode": "SAFE",
            "resolved_mode": "paper",
        },
        "sections": {
            "account_summary": {
                "cash_balance": 1500.0,
                "total_equity": 1525.5,
                "buying_power": 1400.0,
                "margin_used": 0.0,
                "currency": "USD",
                "broker": "COINBASE",
                "account_mode": "paper",
            },
            "pnl_summary": {
                "realized_pnl": 20.0,
                "unrealized_pnl": 5.5,
                "net_pnl": 25.5,
                "total_exposure": 100.0,
            },
            "positions": {
                "total": 1,
                "total_exposure": 100.0,
                "open_positions": [{"symbol": "BTC-USD", "asset_class": "CRYPTO", "exposure": 100.0}],
            },
            "risk": {
                "risk_state": "GREEN",
                "risk_score": 9.0,
                "gate_status": "BLOCKED",
                "current_drawdown": 0.0,
                "total_exposure": 100.0,
            },
            "execution": {
                "execution_state": "BLOCKED",
                "accepted_trade_count": 2,
                "rejected_trade_count": 1,
                "avg_slippage": 0.01,
                "fee_cost": 0.25,
                "execution_cost_state": "PASS",
            },
            "market": {
                "regime_state": "RISK_ON",
                "trend_state": "UP",
                "volatility_state": "LOW",
                "liquidity_state": "GOOD",
                "momentum_state": "POSITIVE",
            },
            "broker": {
                "selected_broker": "COINBASE",
                "broker_mode": "paper",
                "broker_health": "GREEN",
                "connection_status": "PASS",
                "authentication_status": "PASS",
                "account_data_health": "PASS",
                "balance_position_status": "PASS",
                "market_data_status": "PASS",
                "buying_power": 1400.0,
                "last_heartbeat": now,
                "execution_scope": "READ_ONLY",
            },
            "runtime_certification_snapshot": {
                "certification": "GREEN",
                "operational_state": "READ_ONLY",
                "generated_at": now,
            },
        },
    }
    payload["alerts"] = {
        "active": [{"severity": "WARNING", "category": "broker", "message": "latency monitor", "timestamp": now}],
        "count": 1,
        "severity": "WARNING",
        "incident_timeline": [{"timestamp": now, "event": "latency monitor"}],
    }
    payload["sections"]["analytics"] = {"expectancy": 0.2, "win_rate": 0.6, "profit_factor": 1.7, "strategy_rankings": ["safe-momentum"]}
    payload["sections"]["options_income"] = {"status": "PAPER_READY", "opportunities": [{"symbol": "SPY"}], "data_source": "RUNTIME"}
    return payload


def test_mc005_command_center_sections_are_present_and_read_only() -> None:
    state = build_mission_control_state(_runtime_payload(), allow_mock=False)
    required = (
        "operations_timeline",
        "event_stream",
        "trade_lifecycle",
        "portfolio_command",
        "broker_telemetry",
        "risk_command_center",
        "alert_center",
        "executive_kpis",
        "performance_panel",
        "options_income_panel",
        "system_metrics",
        "source_consistency",
    )

    for name in required:
        payload = state[name]
        assert payload["read_only"] is True
        assert payload["source"] == state["runtime"]["source"]
        assert payload["state_hash"] == state["runtime"]["state_hash"]

    assert state["safety"]["execution_allowed"] is False
    assert state["safety"]["live_trading_blocked"] is True
    assert state["safety"]["broker_execution_armed"] is False


def test_mc005_operations_timeline_and_alert_center_group_runtime_events() -> None:
    state = build_mission_control_state(_runtime_payload(), allow_mock=False)

    assert {event["event_type"] for event in state["operations_timeline"]["events"]} >= {"runtime_startup", "heartbeat", "runtime_cycle", "broker_event", "certification_event", "alert"}
    assert state["event_stream"]["event_count"] == len(state["operations_timeline"]["events"])
    assert state["alert_center"]["grouped_by_severity"]["WARNING"]
    assert state["alert_center"]["grouped_by_category"]["broker"]
    assert state["alert_center"]["acknowledgement_actions"] == "DISABLED_READ_ONLY"


def test_mc005_trade_lifecycle_covers_all_required_stages_without_orders() -> None:
    state = build_mission_control_state(_runtime_payload(), allow_mock=False)
    stages = {row["stage"]: row["count"] for row in state["trade_lifecycle"]["stages"]}

    assert set(stages) == {"candidate", "approved", "blocked", "queued", "submitted", "filled", "partially_filled", "cancelled", "rejected", "expired"}
    assert stages["approved"] == 2
    assert stages["blocked"] == 1
    assert state["trade_lifecycle"]["orders"] == []
    assert state["trade_lifecycle"]["execution_controls"] == "DISABLED_READ_ONLY"


def test_mc005_portfolio_broker_risk_and_system_metrics_use_runtime_snapshot() -> None:
    state = build_mission_control_state(_runtime_payload(), allow_mock=False)

    assert state["portfolio_command"]["equity"] == 1525.5
    assert state["portfolio_command"]["pnl"]["net"] == 25.5
    assert state["broker_telemetry"]["broker"] == "COINBASE"
    assert state["broker_telemetry"]["authentication"] == "PASS"
    assert state["risk_command_center"]["risk_gates"]["trade_gate"] == "BLOCKED"
    assert state["risk_command_center"]["overrides"] == "DISABLED_READ_ONLY"
    assert state["system_metrics"]["refresh_interval_seconds"] == 5
    assert state["system_metrics"]["heartbeat_age"] in {0.0, state["runtime"]["heartbeat_age_seconds"]} or isinstance(state["system_metrics"]["heartbeat_age"], float)


def test_mc005_executive_performance_and_options_panels_are_runtime_derived() -> None:
    state = build_mission_control_state(_runtime_payload(), allow_mock=False)

    assert state["executive_kpis"]["broker_health"] == "PASS"
    assert state["executive_kpis"]["alert_count"] == 1
    assert state["performance_panel"]["expectancy"] == 0.2
    assert state["performance_panel"]["profit_factor"] == 1.7
    assert state["options_income_panel"]["status"] == "PAPER_READY"
    assert state["options_income_panel"]["opportunities"] == [{"symbol": "SPY"}]


def test_mc005_options_panel_uses_canonical_runtime_when_frontend_section_empty() -> None:
    payload = _runtime_payload()
    payload["sections"]["options_income"] = {}
    state = build_mission_control_state(payload, allow_mock=False)

    assert state["options_income"]["deployment_state"] == "DEPLOYED"
    assert state["options_income"]["status"] == "ADVISORY_ONLY"
    assert state["options_income_panel"]["status"] == "ADVISORY_ONLY"
    assert state["options_income_panel"]["deployed"] is True
    assert state["options_income_panel"]["execution_blocked"] is True


def test_mc005_offline_state_fails_closed_without_demo_values() -> None:
    state = build_mission_control_state(None, allow_mock=False)

    assert state["runtime_snapshot"]["runtime_status"] == "OFFLINE"
    assert state["portfolio_command"]["equity"] == "UNAVAILABLE"
    assert state["broker_telemetry"]["broker"] == "UNAVAILABLE"
    assert state["source_consistency"]["status"] == "PASS"
    assert state["safety"]["execution_allowed"] is False


def test_mc005_stale_heartbeat_downgrades_health() -> None:
    old = (datetime.now(timezone.utc) - timedelta(minutes=15)).isoformat()
    state = build_mission_control_state(_runtime_payload(heartbeat=old), allow_mock=False)

    assert state["runtime"]["heartbeat_status"] == "STALE"
    assert "runtime_heartbeat_stale" in state["health"]["reasons"]


def test_mc005_source_consistency_failure_is_fail_closed() -> None:
    state = build_mission_control_state(_runtime_payload(), allow_mock=False)
    bad = dict(state)
    bad["source_consistency"] = {**state["source_consistency"], "status": "FAIL_CLOSED", "mismatches": ["broker_telemetry"]}

    validation = validate_mission_control_state(bad)

    assert validation["valid"] is False
    assert "source_consistency_failed" in validation["reasons"]


def test_mc005_non_finite_command_center_metric_is_rejected() -> None:
    state = build_mission_control_state(_runtime_payload(), allow_mock=False)
    bad = dict(state)
    bad["system_metrics"] = {**state["system_metrics"], "api_latency": inf}

    validation = validate_mission_control_state(bad)

    assert validation["valid"] is False
    assert any(reason.startswith("non_finite_value:system_metrics.api_latency") for reason in validation["reasons"])


def test_mc005_desktop_and_mobile_render_command_center_sections() -> None:
    state = build_mission_control_state(_runtime_payload(), allow_mock=False)

    desktop = render_mission_control_shell(state, active_section="runtime_operations")
    mobile = render_mission_control_shell(state, active_section="portfolio")

    assert "Operations Timeline" in desktop
    assert "System Metrics" in desktop
    assert "Source Consistency" in desktop
    assert "Portfolio Command View" in mobile
    assert "@media (max-width: 680px)" in desktop


def test_mc005_fastapi_state_endpoint_exposes_command_center_payloads() -> None:
    client = TestClient(create_app(lambda: _runtime_payload()))

    response = client.get("/mission-control/api/state")
    page = client.get("/mission-control/runtime-operations")

    assert response.status_code == 200
    assert page.status_code == 200
    payload = response.json()
    assert payload["operations_timeline"]["events"]
    assert payload["source_consistency"]["runtime_state_hash"] == payload["runtime"]["state_hash"]
    assert "No execution authority is granted" in page.text

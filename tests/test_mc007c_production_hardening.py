from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from dashboard.mission_control.app import create_app
from dashboard.mission_control.contracts import build_mission_control_state
from dashboard.mission_control.final_certification import CERTIFICATION_AREAS
from dashboard.mission_control.layout import render_mission_control_shell
from dashboard.mission_control.pages._components import detail_table


def _runtime_payload() -> dict:
    now = datetime.now(timezone.utc).isoformat()
    return {
        "payload_schema": "css.frontend.contract.v1",
        "generated_at": now,
        "session_id": "mc007c-session",
        "cycle_number": 79,
        "engine_mode": "SAFE",
        "resolved_mode": "paper",
        "mission_control_data_source": "RUNTIME",
        "session": {"session_id": "mc007c-session", "user_id": "operator", "role": "Operator", "engine_mode": "SAFE"},
        "alerts": {"active": [{"severity": "INFO", "category": "runtime", "message": "stable", "timestamp": now}], "count": 1, "severity": "INFO"},
        "sections": {
            "account_summary": {"cash_balance": 1500.0, "total_equity": 1525.5, "buying_power": 1400.0, "margin_used": 0.0, "currency": "USD", "broker": "COINBASE", "account_mode": "paper"},
            "pnl_summary": {"realized_pnl": 20.0, "unrealized_pnl": 5.5, "net_pnl": 25.5, "total_exposure": 100.0},
            "positions": {"total": 1, "total_exposure": 100.0, "open_positions": [{"symbol": "BTC-USD", "asset_class": "CRYPTO"}], "asset_counts": {"CRYPTO": 1}},
            "risk": {"risk_state": "GREEN", "risk_score": 9.0, "gate_status": "BLOCKED", "current_drawdown": 0.0, "total_exposure": 100.0},
            "execution": {"execution_state": "BLOCKED", "accepted_trade_count": 0, "rejected_trade_count": 1, "avg_slippage": 0.01, "fee_cost": 0.25, "execution_cost_state": "PASS"},
            "market": {"regime_state": "RISK_ON", "trend_state": "UP", "volatility_state": "LOW", "liquidity_state": "GOOD"},
            "broker": {
                "selected_broker": "COINBASE",
                "broker_mode": "paper",
                "broker_health": "GREEN",
                "connection_status": "PASS",
                "authentication_status": "PASS",
                "account_data_health": "PASS",
                "balance_position_status": "PASS",
                "market_data_status": "PASS",
                "supported_assets": ["crypto"],
                "last_heartbeat": now,
                "execution_scope": "READ_ONLY",
            },
            "runtime_certification_snapshot": {"certification": "GREEN", "operational_state": "READ_ONLY", "generated_at": now},
            "configuration": {"feature_flags": {"mission_control": True}},
            "governance": {"governance_status": "GREEN", "audit_enabled": True},
            "analytics": {
                "strategy_rankings": [{"strategy_id": "safe-momentum", "confidence": 0.82, "ranking": 1}],
                "expectancy": 0.3,
                "win_rate": 0.64,
                "profit_factor": 1.8,
            },
            "opportunity_intelligence": {"opportunities": [{"symbol": "BTC-USD", "asset_class": "CRYPTO", "confidence": 0.74, "expected_quality": 91, "risk": "LOW", "blocking_reason": "advisory_only"}]},
            "capital_allocation_intelligence": {"capital_deployed": 100.0, "available_capital": 1400.0, "reserved_capital": 50.0, "utilization": 0.066},
            "audit": {
                "change_history": [{"who": "operator", "what": "documentation review", "when": now, "reason": "final certification", "approval_status": "reviewed", "rollback_available": False}],
                "decisions": [{"decision_id": "decision-btc-1", "symbol": "BTC-USD", "decision": "BLOCKED", "confidence": 0.62, "reason": "advisory_only"}],
                "committees": {
                    "Investment Committee": {"outcome": "WARNING", "reason": "watch"},
                    "Risk Committee": {"outcome": "PASS", "reason": "green"},
                    "Execution Committee": {"outcome": "FAIL", "reason": "read only"},
                    "Capital Committee": {"outcome": "PASS", "reason": "cash"},
                    "Compliance": {"outcome": "PASS", "reason": "reviewed"},
                    "Broker Committee": {"outcome": "PASS", "reason": "ready"},
                },
            },
        },
    }


def test_mc007c_final_certification_has_explicit_status_for_every_area() -> None:
    state = build_mission_control_state(_runtime_payload(), allow_mock=False)
    final = state["final_certification"]
    checks = {row["area"]: row["status"] for row in final["checks"]}

    assert list(checks) == list(CERTIFICATION_AREAS)
    assert final["version"] == "Mission Control v1.0"
    assert final["overall"] == "CERTIFIED"
    assert all(status == "CERTIFIED" for status in checks.values())
    assert final["execution_allowed"] is False
    assert final["live_trading_blocked"] is True
    assert final["broker_execution_armed"] is False
    assert final["advisory_only"] is True


def test_mc007c_api_endpoints_share_runtime_hash_metadata() -> None:
    client = TestClient(create_app(lambda: _runtime_payload()))

    state = client.get("/mission-control/api/state").json()
    metadata = client.get("/mission-control/api/page-metadata").json()
    heartbeat = client.get("/mission-control/api/heartbeat").json()
    runtime = client.get("/mission-control/api/runtime").json()
    final = client.get("/mission-control/api/final-certification").json()

    assert metadata["state_hash"] == state["state_hash"]
    assert metadata["runtime_id"] == state["runtime"]["runtime_id"]
    assert heartbeat["state_hash"] == state["runtime"]["state_hash"]
    assert runtime["state_hash"] == state["runtime"]["state_hash"]
    assert final["api_contracts"]["runtime_state_hash"] == state["runtime"]["state_hash"]
    assert client.post("/mission-control/api/final-certification").status_code in {404, 405}


def test_mc007c_resilience_offline_runtime_fails_closed_and_displays_banner() -> None:
    state = build_mission_control_state(None, allow_mock=False)
    html = render_mission_control_shell(state, active_section="executive_overview")

    assert state["final_certification"]["overall"] == "FAIL_CLOSED"
    assert "runtime" in state["final_certification"]["blockers"]
    assert "Runtime evidence is unavailable or stale" in html
    assert state["safety"]["execution_allowed"] is False
    assert state["safety"]["live_trading_blocked"] is True
    assert state["safety"]["broker_execution_armed"] is False


def test_mc007c_empty_detail_tables_have_operator_friendly_empty_state() -> None:
    assert "No evidence available." in detail_table("Empty", [])
    assert "No evidence available." in detail_table("Empty", {})


def test_mc007c_certification_page_renders_final_certification() -> None:
    state = build_mission_control_state(_runtime_payload(), allow_mock=False)
    html = render_mission_control_shell(state, active_section="certification_readiness")

    assert "Mission Control Final Certification" in html
    assert "Final Certification Checks" in html
    assert "Mission Control v1.0" in html

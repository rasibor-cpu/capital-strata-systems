from __future__ import annotations

from datetime import datetime, timezone
from math import inf

from fastapi.testclient import TestClient

from dashboard.mission_control.app import create_app
from dashboard.mission_control.contracts import build_mission_control_state, validate_mission_control_state
from dashboard.mission_control.layout import render_mission_control_shell


def _runtime_payload() -> dict:
    now = datetime.now(timezone.utc).isoformat()
    return {
        "payload_schema": "css.frontend.contract.v1",
        "generated_at": now,
        "session_id": "mc007a-session",
        "cycle_number": 77,
        "engine_mode": "SAFE",
        "resolved_mode": "paper",
        "mission_control_data_source": "RUNTIME",
        "session": {"session_id": "mc007a-session", "user_id": "operator", "role": "TRADER", "engine_mode": "SAFE"},
        "alerts": {
            "active": [{"severity": "WARNING", "category": "risk", "message": "watch drawdown", "timestamp": now}],
            "count": 1,
            "severity": "WARNING",
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
            "pnl_summary": {"realized_pnl": 20.0, "unrealized_pnl": 5.5, "net_pnl": 25.5, "total_exposure": 100.0},
            "positions": {
                "total": 1,
                "total_exposure": 100.0,
                "open_positions": [{"symbol": "BTC-USD", "asset_class": "CRYPTO", "exposure": 100.0}],
                "asset_counts": {"CRYPTO": 1},
            },
            "risk": {
                "risk_state": "GREEN",
                "risk_score": 9.0,
                "gate_status": "BLOCKED",
                "current_drawdown": 0.0,
                "total_exposure": 100.0,
                "warnings": ["observe concentration"],
                "limit_breaches": [],
            },
            "execution": {
                "execution_state": "BLOCKED",
                "accepted_trade_count": 0,
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
                "latency_ms": 42,
                "last_heartbeat": now,
                "execution_scope": "READ_ONLY",
            },
            "runtime_certification_snapshot": {"certification": "GREEN", "operational_state": "READ_ONLY", "generated_at": now},
            "analytics": {
                "strategy_rankings": [
                    {
                        "strategy_id": "safe-momentum",
                        "status": "ACTIVE",
                        "confidence": 0.82,
                        "allocation": 0.2,
                        "risk": "LOW",
                        "expectancy": 0.3,
                        "capital_usage": 100.0,
                        "win_rate": 0.64,
                        "profit_factor": 1.8,
                        "sharpe": 1.2,
                        "ranking": 1,
                    }
                ],
                "expectancy": 0.3,
                "win_rate": 0.64,
                "profit_factor": 1.8,
                "drawdown": 0.0,
            },
            "opportunity_intelligence": {
                "opportunities": [
                    {"symbol": "BTC-USD", "asset_class": "CRYPTO", "confidence": 0.74, "expected_quality": 91, "risk": "LOW", "blocking_reason": "advisory_only"},
                    {"symbol": "ETH-USD", "asset_class": "CRYPTO", "confidence": 0.61, "expected_quality": 80, "risk": "MEDIUM", "blocking_reason": "needs_evidence"},
                ]
            },
            "capital_allocation_intelligence": {
                "capital_deployed": 100.0,
                "available_capital": 1400.0,
                "reserved_capital": 50.0,
                "utilization": 0.066,
                "strategy_allocation": {"safe-momentum": 100.0},
                "asset_allocation": {"CRYPTO": 100.0},
                "sector_allocation": {"digital_assets": 100.0},
                "currency_allocation": {"USD": 1500.0},
                "institution_allocation": {"paper": 100.0},
            },
            "performance_attribution": {
                "pnl_attribution": {"CRYPTO": 25.5},
                "strategy_attribution": {"safe-momentum": 25.5},
                "broker_attribution": {"COINBASE": "PASS"},
                "timing_attribution": {"entry": "aligned"},
                "execution_attribution": {"quality": "PASS"},
                "risk_attribution": {"drawdown": 0.0},
            },
            "audit": {
                "decisions": [
                    {
                        "decision_id": "decision-btc-1",
                        "symbol": "BTC-USD",
                        "asset_class": "CRYPTO",
                        "decision": "BLOCKED",
                        "confidence": 0.62,
                        "confidence_threshold": 0.7,
                        "decision_score": 72,
                        "probability": 0.58,
                        "quality_score": "PASS",
                        "reason": "confidence_below_threshold",
                        "timestamp": now,
                    }
                ],
                "committees": {
                    "Investment Committee": {"outcome": "WARNING", "reason": "confidence near threshold"},
                    "Risk Committee": {"outcome": "PASS", "reason": "risk green"},
                    "Execution Committee": {"outcome": "FAIL", "reason": "advisory only"},
                    "Capital Committee": {"outcome": "PASS", "reason": "cash available"},
                    "Compliance": {"outcome": "PASS", "reason": "read only"},
                    "Broker Committee": {"outcome": "PASS", "reason": "broker ready"},
                },
            },
            "institutional_investment_committee": {
                "current_decisions": [{"decision_id": "decision-btc-1", "decision": "BLOCKED"}],
                "capital_recommendations": [{"strategy_id": "safe-momentum", "action": "monitor"}],
                "decision_quality": "WATCH",
            },
        },
    }


def test_mc007a_institutional_sections_are_present_read_only_and_source_consistent() -> None:
    state = build_mission_control_state(_runtime_payload(), allow_mock=False)
    required = (
        "strategy_war_room",
        "opportunity_ranking",
        "capital_allocation_center",
        "performance_attribution",
        "institutional_executive_dashboard",
        "investment_committee",
        "risk_committee",
        "execution_committee",
        "capital_committee",
        "institutional_reporting",
    )

    for name in required:
        payload = state[name]
        assert payload["read_only"] is True
        assert payload["execution_allowed"] is False
        assert payload["live_trading_blocked"] is True
        assert payload["broker_execution_armed"] is False
        assert payload["advisory_only"] is True
        assert payload["state_hash"] == state["runtime"]["state_hash"]
        assert payload["runtime_id"] == state["runtime"]["runtime_id"]

    assert set(required).issubset(set(state["source_consistency"]["checked_sections"]))
    assert state["contract_validation"]["valid"] is True


def test_mc007a_strategy_war_room_opportunity_ranking_and_capital_center() -> None:
    state = build_mission_control_state(_runtime_payload(), allow_mock=False)

    assert state["strategy_war_room"]["strategies"][0]["strategy_id"] == "safe-momentum"
    assert state["strategy_war_room"]["strategies"][0]["profit_factor"] == 1.8
    assert [row["symbol"] for row in state["opportunity_ranking"]["opportunities"]] == ["BTC-USD", "ETH-USD"]
    assert state["opportunity_ranking"]["opportunities"][0]["ranking"] == 1
    assert state["capital_allocation_center"]["reserved_capital"] == 50.0
    assert state["capital_allocation_center"]["strategy_allocation"] == {"safe-momentum": 100.0}


def test_mc007a_performance_attribution_and_committees_reuse_existing_state() -> None:
    state = build_mission_control_state(_runtime_payload(), allow_mock=False)

    assert state["performance_attribution"]["pnl_attribution"] == {"CRYPTO": 25.5}
    assert state["investment_committee"]["current_decisions"][0]["decision_id"] == "decision-btc-1"
    assert state["investment_committee"]["confidence_distribution"] == {"low": 0, "medium": 1, "high": 0, "unavailable": 0}
    assert state["risk_committee"]["risk_posture"] == "GREEN"
    assert state["execution_committee"]["execution_quality"] == "PASS"
    assert state["capital_committee"]["unused_capital"] == 1400.0


def test_mc007a_executive_dashboard_and_reporting_summaries() -> None:
    state = build_mission_control_state(_runtime_payload(), allow_mock=False)

    executive = state["institutional_executive_dashboard"]
    reports = state["institutional_reporting"]["summaries"]

    assert executive["platform_health"] == state["platform"]["platform_status"]
    assert executive["top_opportunities"][0]["symbol"] == "BTC-USD"
    assert [row["title"] for row in reports] == [
        "Daily CIO Summary",
        "Risk Summary",
        "Capital Summary",
        "Broker Summary",
        "Performance Summary",
    ]


def test_mc007a_cross_navigation_and_pages_render_institutional_panels() -> None:
    state = build_mission_control_state(_runtime_payload(), allow_mock=False)

    assert state["strategy_war_room"]["links"][0]["route"].startswith("/mission-control/")
    executive = render_mission_control_shell(state, active_section="executive_overview")
    portfolio = render_mission_control_shell(state, active_section="portfolio")
    risk = render_mission_control_shell(state, active_section="risk_command")
    trade = render_mission_control_shell(state, active_section="trade_operations")
    learning = render_mission_control_shell(state, active_section="learning_performance")
    market = render_mission_control_shell(state, active_section="market_intelligence")

    assert "Institutional Dashboard" in executive
    assert "Capital Allocation Center" in portfolio
    assert "Risk Committee" in risk
    assert "Execution Committee" in trade
    assert "Strategy War Room" in learning
    assert "Opportunity Ranking" in market


def test_mc007a_offline_behavior_fails_closed_without_controls() -> None:
    state = build_mission_control_state(None, allow_mock=False)

    assert state["strategy_war_room"]["status"] == "FAIL_CLOSED"
    assert state["institutional_reporting"]["status"] == "FAIL_CLOSED"
    assert state["contract_validation"]["valid"] is False
    assert state["safety"]["execution_allowed"] is False
    assert state["safety"]["live_trading_blocked"] is True
    assert state["safety"]["broker_execution_armed"] is False


def test_mc007a_fail_closed_on_hash_mismatch_and_non_finite_metric() -> None:
    state = build_mission_control_state(_runtime_payload(), allow_mock=False)
    mismatch = dict(state)
    mismatch["source_consistency"] = {**state["source_consistency"], "status": "FAIL_CLOSED", "mismatches": ["strategy_war_room"]}
    non_finite = dict(state)
    non_finite["strategy_war_room"] = {**state["strategy_war_room"], "strategies": [{**state["strategy_war_room"]["strategies"][0], "confidence": inf}]}

    mismatch_validation = validate_mission_control_state(mismatch)
    non_finite_validation = validate_mission_control_state(non_finite)

    assert mismatch_validation["valid"] is False
    assert "source_consistency_failed" in mismatch_validation["reasons"]
    assert non_finite_validation["valid"] is False
    assert any(reason.startswith("non_finite_value:strategy_war_room.strategies[0].confidence") for reason in non_finite_validation["reasons"])


def test_mc007a_fastapi_state_endpoint_exposes_institutional_suite() -> None:
    client = TestClient(create_app(lambda: _runtime_payload()))

    response = client.get("/mission-control/api/state")

    assert response.status_code == 200
    payload = response.json()
    assert payload["strategy_war_room"]["strategies"][0]["strategy_id"] == "safe-momentum"
    assert payload["institutional_executive_dashboard"]["top_opportunities"][0]["symbol"] == "BTC-USD"

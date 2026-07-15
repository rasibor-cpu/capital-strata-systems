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
        "session_id": "mc006-session",
        "cycle_number": 66,
        "engine_mode": "SAFE",
        "resolved_mode": "paper",
        "mission_control_data_source": "RUNTIME",
        "session": {
            "session_id": "mc006-session",
            "user_id": "operator",
            "role": "TRADER",
            "cycle_number": 66,
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
                "buying_power": 1400.0,
                "last_heartbeat": now,
                "execution_scope": "READ_ONLY",
            },
            "runtime_certification_snapshot": {
                "certification": "GREEN",
                "operational_state": "READ_ONLY",
                "generated_at": now,
            },
            "analytics": {
                "expectancy": 0.2,
                "win_rate": 0.6,
                "profit_factor": 1.7,
                "strategy_rankings": ["safe-momentum"],
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
                "decision_trace": [
                    {"stage": "Market Regime", "status": "PASS", "score": 80, "reason": "risk_on", "evidence": {"market_regime": "RISK_ON"}},
                    {"stage": "Signal Engine", "status": "WARNING", "score": 62, "reason": "confidence_below_threshold", "evidence": {"confidence": 0.62}},
                    {"stage": "Portfolio Constraints", "status": "PASS", "score": 90, "reason": "cash_available", "evidence": {"buying_power": 1400.0}},
                    {"stage": "Risk Committee", "status": "PASS", "score": 92, "reason": "risk_green", "evidence": {"risk_state": "GREEN"}},
                    {"stage": "AntiBleedGuard", "status": "PASS", "score": 100, "reason": "no_loss_guard", "evidence": {"guard": "PASS"}},
                    {"stage": "Trade Gate", "status": "BLOCKED", "score": 0, "reason": "advisory_only", "evidence": {"execution_allowed": False}},
                    {"stage": "Final Decision", "status": "BLOCKED", "score": 62, "reason": "confidence_below_threshold", "evidence": {"threshold": 0.7}},
                ],
                "committees": {
                    "Investment Committee": {"outcome": "WARNING", "reason": "confidence near threshold"},
                    "Risk Committee": {"outcome": "PASS", "reason": "risk green"},
                    "Execution Committee": {"outcome": "FAIL", "reason": "advisory only"},
                    "Capital Committee": {"outcome": "PASS", "reason": "cash available"},
                    "Compliance": {"outcome": "PASS", "reason": "read only"},
                    "Broker Committee": {"outcome": "PASS", "reason": "broker ready"},
                },
                "decision_explanations": ["confidence below threshold"],
                "rules_evaluated": ["confidence_threshold", "advisory_only"],
                "supporting_metrics": {"confidence": 0.62, "threshold": 0.7},
            },
        },
    }


def test_mc006_decision_panel_trace_explanation_and_source_consistency() -> None:
    state = build_mission_control_state(_runtime_payload(), allow_mock=False)

    assert state["decision_panel"]["status"] == "BLOCKED"
    assert state["decision_panel"]["decisions"][0]["decision_id"] == "decision-btc-1"
    assert state["decision_trace"]["decision_id"] == "decision-btc-1"
    assert [stage["stage"] for stage in state["decision_trace"]["stages"]] == [
        "Market Regime",
        "Signal Engine",
        "Portfolio Constraints",
        "Risk Committee",
        "AntiBleedGuard",
        "Trade Gate",
        "Final Decision",
    ]
    assert state["decision_explanation"]["decision"] == "BLOCKED"
    assert state["decision_explanation"]["blocking_subsystem"] == "Trade Gate"
    assert state["decision_explanation"]["required_improvement"] == "confidence > 0.7"
    assert state["source_consistency"]["status"] == "PASS"
    assert "decision_panel" in state["source_consistency"]["checked_sections"]


def test_mc006_committee_counterfactual_recommendation_and_evidence_graph() -> None:
    state = build_mission_control_state(_runtime_payload(), allow_mock=False)

    committees = {row["committee"]: row["outcome"] for row in state["committee_view"]["committees"]}
    assert committees["Execution Committee"] == "FAIL"
    assert len(committees) == 6
    assert state["counterfactuals"]["counterfactuals"][0]["condition"] == "confidence > 0.7"
    assert state["recommendation_panel"]["forbidden_terms_absent"] is True
    assert state["recommendation_panel"]["recommendations"][0]["action"] == "Increase evidence"
    assert state["evidence_graph"]["status"] == "PASS"
    assert state["evidence_graph"]["source_consistency"]["decision_id"] == "decision-btc-1"
    assert {node["id"] for node in state["evidence_graph"]["nodes"]} >= {"market", "risk", "committee", "decision", "audit"}


def test_mc006_api_endpoints_are_get_only_and_share_state_contract() -> None:
    client = TestClient(create_app(lambda: _runtime_payload()))

    decision = client.get("/mission-control/api/decision")
    trace = client.get("/mission-control/api/decision-trace")
    explanation = client.get("/mission-control/api/explanation")
    recommendation = client.get("/mission-control/api/recommendation")
    evidence = client.get("/mission-control/api/evidence")

    assert decision.status_code == 200
    assert trace.status_code == 200
    assert explanation.status_code == 200
    assert recommendation.status_code == 200
    assert evidence.status_code == 200
    assert decision.json()["decisions"][0]["decision_id"] == "decision-btc-1"
    assert trace.json()["decision_id"] == "decision-btc-1"
    assert explanation.json()["decision_id"] == "decision-btc-1"
    assert recommendation.json()["decision_id"] == "decision-btc-1"
    assert evidence.json()["source_consistency"]["decision_id"] == "decision-btc-1"
    assert client.post("/mission-control/api/decision").status_code in {404, 405}


def test_mc006_desktop_and_mobile_render_decision_intelligence_sections() -> None:
    state = build_mission_control_state(_runtime_payload(), allow_mock=False)

    desktop = render_mission_control_shell(state, active_section="trade_operations")
    mobile = render_mission_control_shell(state, active_section="audit_explainability")

    assert "Decision Panel" in desktop
    assert "Decision Trace" in desktop
    assert "Decision Explanation" in mobile
    assert "Evidence Graph" in mobile
    assert "@media (max-width: 680px)" in desktop


def test_mc006_offline_state_fails_closed_without_synthetic_decision_authority() -> None:
    state = build_mission_control_state(None, allow_mock=False)

    assert state["decision_panel"]["status"] == "UNKNOWN"
    assert state["decision_panel"]["reason"] == "Runtime unavailable"
    assert state["decision_explanation"]["plain_language"] == "Runtime unavailable. No synthetic explanation was generated."
    assert state["recommendation_panel"]["recommendations"][0]["action"] == "No action"
    assert state["safety"]["execution_allowed"] is False
    assert state["safety"]["live_trading_blocked"] is True
    assert state["safety"]["broker_execution_armed"] is False


def test_mc006_fail_closed_on_malformed_committee_vote() -> None:
    payload = _runtime_payload()
    payload["sections"]["audit"]["committees"]["Risk Committee"] = {"outcome": "MAYBE", "reason": "malformed"}
    state = build_mission_control_state(payload, allow_mock=False)

    assert state["committee_view"]["status"] == "FAIL_CLOSED"
    assert state["contract_validation"]["valid"] is False
    assert "committee_outcomes_contradictory" in state["contract_validation"]["reasons"]
    assert state["safety"]["fail_closed"] is True


def test_mc006_fail_closed_on_evidence_graph_mismatch_and_execution_language() -> None:
    state = build_mission_control_state(_runtime_payload(), allow_mock=False)
    bad_graph = dict(state)
    bad_graph["evidence_graph"] = {**state["evidence_graph"], "status": "FAIL_CLOSED", "mismatches": ["decision"]}
    graph_validation = validate_mission_control_state(bad_graph)

    bad_recommendation = dict(state)
    bad_recommendation["recommendation_panel"] = {**state["recommendation_panel"], "forbidden_terms_absent": False}
    recommendation_validation = validate_mission_control_state(bad_recommendation)

    assert graph_validation["valid"] is False
    assert "evidence_graph_inconsistent" in graph_validation["reasons"]
    assert recommendation_validation["valid"] is False
    assert "recommendation_contains_execution_language" in recommendation_validation["reasons"]


def test_mc006_non_finite_decision_metric_is_rejected() -> None:
    state = build_mission_control_state(_runtime_payload(), allow_mock=False)
    bad = dict(state)
    bad["decision_panel"] = {
        **state["decision_panel"],
        "decisions": [{**state["decision_panel"]["decisions"][0], "confidence": inf}],
    }

    validation = validate_mission_control_state(bad)

    assert validation["valid"] is False
    assert any(reason.startswith("non_finite_value:decision_panel.decisions[0].confidence") for reason in validation["reasons"])

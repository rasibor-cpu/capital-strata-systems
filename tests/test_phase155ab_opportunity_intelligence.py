from __future__ import annotations

from fastapi.testclient import TestClient

from backend.analytics.opportunity_intelligence_engine import (
    ExpectedValueEngine,
    OpportunityIntelligenceEngine,
    RiskAdjustedOpportunityScoringEngine,
)
from dashboard.runtime.api_bridge import create_app
from dashboard.runtime.dashboard_hydration_coordinator import DashboardHydrationCoordinator


def _green_opportunity(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "opportunity_id": "opp-green",
        "symbol": "BTC-USD",
        "asset_class": "CRYPTO",
        "strategy": "breakout",
        "broker": "DEMO",
        "status": "MONITOR_ONLY",
        "regime": "RISK_ON",
        "signal_strength": 0.92,
        "confidence": 0.9,
        "historical_performance": 0.85,
        "execution_quality": 0.9,
        "broker_performance": 0.9,
        "liquidity": 0.9,
        "volatility": 0.18,
        "regime_alignment": 0.9,
        "expected_holding_period": "2h",
        "portfolio_diversification_benefit": 0.8,
        "current_exposure": 0.1,
        "capital_efficiency": 0.75,
        "expected_reward": 300.0,
        "expected_risk": 70.0,
        "downside_penalty": 10.0,
        "requested_capital": 1000.0,
    }
    payload.update(overrides)
    return payload


def _amber_opportunity(**overrides: object) -> dict[str, object]:
    payload = _green_opportunity(
        opportunity_id="opp-amber",
        symbol="EUR_USD",
        strategy="mean-reversion",
        confidence=0.65,
        historical_performance=0.55,
        execution_quality=0.6,
        broker_performance=0.65,
        liquidity=0.55,
        volatility=0.45,
        regime_alignment=0.55,
        portfolio_diversification_benefit=0.4,
        capital_efficiency=0.25,
        expected_reward=120.0,
        expected_risk=80.0,
        downside_penalty=20.0,
        probability=0.6,
    )
    payload.update(overrides)
    return payload


def _red_opportunity(**overrides: object) -> dict[str, object]:
    payload = _green_opportunity(
        opportunity_id="opp-red",
        symbol="CL",
        asset_class="FUTURES",
        strategy="countertrend",
        confidence=0.25,
        historical_performance=0.25,
        execution_quality=0.25,
        broker_performance=0.2,
        liquidity=0.2,
        volatility=0.9,
        regime_alignment=0.2,
        portfolio_diversification_benefit=0.1,
        capital_efficiency=0.1,
        expected_reward=80.0,
        expected_risk=160.0,
        downside_penalty=60.0,
        probability=0.3,
    )
    payload.update(overrides)
    return payload


def test_phase155ab_green_opportunity_scores_green() -> None:
    report = OpportunityIntelligenceEngine().evaluate([_green_opportunity()])

    item = report["opportunities"][0]
    assert item["status"] == "GREEN"
    assert item["opportunity_score"] >= 75.0
    assert item["rank"] == 1
    assert "Decision confidence" in item["strengths"]
    assert item["recommendation"] == "PAPER_PRIORITY_REVIEW"
    assert item["advisory_only"] is True
    assert item["execution_allowed"] is False


def test_phase155ab_amber_opportunity_scores_amber() -> None:
    item = OpportunityIntelligenceEngine().evaluate([_amber_opportunity()])["opportunities"][0]

    assert item["status"] == "AMBER"
    assert 45.0 <= item["opportunity_score"] < 75.0
    assert item["recommendation"] == "MONITOR"
    assert item["weaknesses"]


def test_phase155ab_red_opportunity_scores_red() -> None:
    item = OpportunityIntelligenceEngine().evaluate([_red_opportunity()])["opportunities"][0]

    assert item["status"] == "RED"
    assert item["opportunity_score"] < 45.0
    assert "Opportunity score is RED" in item["warnings"]
    assert item["recommendation"] == "DO_NOT_ALLOCATE"


def test_phase155ab_ranking_correctness_highest_score_first() -> None:
    report = OpportunityIntelligenceEngine().evaluate(
        [_amber_opportunity(), _green_opportunity(), _red_opportunity()]
    )

    leaderboard = report["leaderboard"]
    assert [row["rank"] for row in leaderboard] == [1, 2, 3]
    assert leaderboard[0]["asset"] == "BTC-USD"
    assert leaderboard[0]["score"] >= leaderboard[1]["score"] >= leaderboard[2]["score"]


def test_phase155ab_expected_value_and_confidence_adjustment() -> None:
    strong = ExpectedValueEngine().evaluate(_green_opportunity())
    weak_confidence = ExpectedValueEngine().evaluate(_green_opportunity(confidence=0.2))

    assert strong["expected_value"] > 0.0
    assert strong["risk_adjusted_return"] > 0.0
    assert 0.0 <= strong["expected_drawdown"] <= 1.0
    assert strong["confidence_adjusted_ev"] > weak_confidence["confidence_adjusted_ev"]


def test_phase155ab_broker_and_execution_quality_integration() -> None:
    good = RiskAdjustedOpportunityScoringEngine().score(
        _green_opportunity(broker_performance=0.95, execution_quality=0.95)
    )
    degraded = RiskAdjustedOpportunityScoringEngine().score(
        _green_opportunity(broker_performance=0.25, execution_quality=0.25)
    )

    assert good["overall_score"] > degraded["overall_score"]
    assert degraded["score_breakdown"]["broker_performance"] == 25.0
    assert degraded["score_breakdown"]["execution_quality"] == 25.0


def test_phase155ab_api_response_shape_and_explainability() -> None:
    state = DashboardHydrationCoordinator().hydrate(
        account_payload={"broker": "DEMO", "account_mode": "paper", "cash_balance": 10000.0},
        broker_payload={"selected_broker": "DEMO", "broker_mode": "paper"},
        execution_payload={"execution_state": "READY", "avg_slippage_bps": 1.0, "avg_spread_bps": 1.0},
        market_payload={
            "liquidity_state": "HEALTHY",
            "regime_state": "RISK_ON",
            "opportunities": [_green_opportunity(), _amber_opportunity()],
        },
        risk_payload={"risk_state": "NORMAL", "gate_status": "OPEN"},
    )

    response = TestClient(create_app(lambda: state)).get("/api/v1/opportunity-intelligence")

    assert response.status_code == 200
    payload = response.json()
    assert payload["section"] == "opportunity_intelligence"
    assert payload["advisory_only"] is True
    assert payload["execution_allowed"] is False
    assert len(payload["opportunities"]) == 2
    assert payload["leaderboard"][0]["rank"] == 1
    assert "does not authorize execution" in payload["opportunities"][0]["explanation"]


def test_phase155ab_safety_and_regression_contract() -> None:
    report = OpportunityIntelligenceEngine().evaluate(
        [_green_opportunity(live_trading_enabled=True, can_live_execute=True)]
    )

    item = report["opportunities"][0]
    assert report["advisory_only"] is True
    assert report["execution_allowed"] is False
    assert report["live_trading_enabled"] is False
    assert item["execution_allowed"] is False
    assert item["live_trading_enabled"] is False
    assert item["status"] == "RED"
    assert "Live trading authority is outside opportunity intelligence" in item["warnings"]

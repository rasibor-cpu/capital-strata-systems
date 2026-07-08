from __future__ import annotations

from fastapi.testclient import TestClient

from backend.analytics.capital_allocation_optimizer import (
    CapitalAllocationOptimizer,
    build_capital_allocation_intelligence_report,
)
from dashboard.runtime.api_bridge import create_app
from dashboard.runtime.dashboard_hydration_coordinator import DashboardHydrationCoordinator
from dashboard.runtime.frontend_contract import build_frontend_payload
from dashboard.web.web_app import _dashboard_page


def _opportunity(
    opportunity_id: str,
    *,
    rank: int,
    asset: str,
    asset_class: str,
    sector: str,
    broker: str,
    strategy: str,
    score: float,
    expected_value: float = 120.0,
    confidence: float = 0.8,
    capital_efficiency: float = 0.7,
    requested_capital: float = 2500.0,
    status: str = "GREEN",
) -> dict[str, object]:
    return {
        "opportunity_id": opportunity_id,
        "rank": rank,
        "asset": asset,
        "asset_class": asset_class,
        "sector": sector,
        "broker": broker,
        "strategy": strategy,
        "opportunity_score": score,
        "expected_value": expected_value,
        "confidence": confidence,
        "capital_efficiency": capital_efficiency,
        "requested_capital": requested_capital,
        "status": status,
    }


def test_phase155cd_capital_allocation_uses_ranked_opportunities() -> None:
    result = CapitalAllocationOptimizer().optimize(
        available_capital=10000.0,
        ranked_opportunities=[
            _opportunity("mid", rank=2, asset="EUR_USD", asset_class="FX", sector="FX", broker="OANDA", strategy="mean", score=70.0),
            _opportunity("top", rank=1, asset="BTC-USD", asset_class="CRYPTO", sector="CRYPTO", broker="COINBASE", strategy="breakout", score=90.0),
        ],
    )

    assert result["advisory_only"] is True
    assert result["execution_allowed"] is False
    assert result["allocation_plan"][0]["opportunity_id"] == "top"
    assert result["capital_used"] > 0.0
    assert result["capital_remaining"] >= result["policies"]["cash_reserve"]
    assert "fits portfolio governance constraints" in result["allocation_plan"][0]["rationale"]


def test_phase155cd_asset_sector_broker_and_strategy_limits_explain_skips() -> None:
    optimizer = CapitalAllocationOptimizer()

    asset_limited = optimizer.optimize(
        available_capital=10000.0,
        ranked_opportunities=[
            _opportunity("c1", rank=1, asset="BTC-USD", asset_class="CRYPTO", sector="CRYPTO", broker="COINBASE", strategy="breakout", score=90.0),
            _opportunity("c2", rank=2, asset="ETH-USD", asset_class="CRYPTO", sector="CRYPTO", broker="OANDA", strategy="mean", score=88.0),
        ],
        policies={"asset_class_limit_pct": 0.30},
    )
    sector_limited = optimizer.optimize(
        available_capital=10000.0,
        ranked_opportunities=[
            _opportunity("s1", rank=1, asset="BTC-USD", asset_class="CRYPTO", sector="DIGITAL", broker="COINBASE", strategy="breakout", score=90.0),
            _opportunity("s2", rank=2, asset="ETH-USD", asset_class="ALT", sector="DIGITAL", broker="OANDA", strategy="mean", score=88.0),
        ],
        policies={"sector_limit_pct": 0.30},
    )
    broker_limited = optimizer.optimize(
        available_capital=10000.0,
        ranked_opportunities=[
            _opportunity("b1", rank=1, asset="BTC-USD", asset_class="CRYPTO", sector="CRYPTO", broker="COINBASE", strategy="breakout", score=90.0),
            _opportunity("b2", rank=2, asset="EUR_USD", asset_class="FX", sector="FX", broker="COINBASE", strategy="mean", score=88.0),
        ],
        policies={"broker_limit_pct": 0.30},
    )
    strategy_limited = optimizer.optimize(
        available_capital=10000.0,
        ranked_opportunities=[
            _opportunity("t1", rank=1, asset="BTC-USD", asset_class="CRYPTO", sector="CRYPTO", broker="COINBASE", strategy="breakout", score=90.0),
            _opportunity("t2", rank=2, asset="EUR_USD", asset_class="FX", sector="FX", broker="OANDA", strategy="breakout", score=88.0),
        ],
        policies={"strategy_limit_pct": 0.30},
    )

    assert "Asset-class allocation limit prevents allocation" in asset_limited["warnings"]
    assert "Sector allocation limit prevents allocation" in sector_limited["warnings"]
    assert "Broker allocation limit prevents allocation" in broker_limited["warnings"]
    assert "Strategy allocation limit prevents allocation" in strategy_limited["warnings"]
    assert any(row["decision"] == "NO_SHADOW_ALLOCATION" for row in asset_limited["recommendations"])


def test_phase155cd_cash_reserve_and_single_position_limits_are_respected() -> None:
    result = CapitalAllocationOptimizer().optimize(
        available_capital=10000.0,
        ranked_opportunities=[
            _opportunity("p1", rank=1, asset="BTC-USD", asset_class="CRYPTO", sector="CRYPTO", broker="COINBASE", strategy="a", score=95.0, requested_capital=9000.0),
            _opportunity("p2", rank=2, asset="EUR_USD", asset_class="FX", sector="FX", broker="OANDA", strategy="b", score=92.0, requested_capital=9000.0),
            _opportunity("p3", rank=3, asset="CL", asset_class="FUTURES", sector="ENERGY", broker="OANDA", strategy="c", score=90.0, requested_capital=9000.0),
        ],
        policies={"cash_reserve_pct": 0.50, "max_single_position_pct": 0.20},
    )

    assert all(row["allocated_capital"] <= 2000.0 for row in result["allocation_plan"])
    assert result["capital_used"] <= 5000.0
    assert result["capital_remaining"] >= 5000.0


def test_phase155cd_diversification_and_portfolio_metrics() -> None:
    result = CapitalAllocationOptimizer().optimize(
        available_capital=12000.0,
        ranked_opportunities=[
            _opportunity("p1", rank=1, asset="BTC-USD", asset_class="CRYPTO", sector="CRYPTO", broker="COINBASE", strategy="a", score=90.0),
            _opportunity("p2", rank=2, asset="EUR_USD", asset_class="FX", sector="FX", broker="OANDA", strategy="b", score=86.0),
            _opportunity("p3", rank=3, asset="CL", asset_class="FUTURES", sector="ENERGY", broker="OANDA", strategy="c", score=82.0),
        ],
    )
    metrics = result["portfolio_metrics"]

    assert metrics["capital_efficiency_score"] > 0.0
    assert metrics["expected_portfolio_return"] > 0.0
    assert 0.0 <= metrics["expected_portfolio_risk"] <= 1.0
    assert 0.0 <= metrics["expected_drawdown"] <= 1.0
    assert metrics["portfolio_confidence"] > 0.0
    assert metrics["risk_adjusted_capital_score"] > 0.0
    assert metrics["diversification_score"] > 0.0


def test_phase155cd_runtime_shadow_report_consumes_opportunity_intelligence() -> None:
    dashboard_payload = {
        "account_summary": {"buying_power": 10000.0, "cash_balance": 10000.0, "broker": "DEMO"},
        "risk_summary": {"risk_state": "NORMAL", "gate_status": "OPEN", "cash_reserve_pct": 0.20},
        "execution_summary": {"execution_state": "READY", "avg_slippage_bps": 1.0, "avg_spread_bps": 1.0},
        "market_summary": {"liquidity_state": "HEALTHY", "regime_state": "RISK_ON"},
        "position_state": {"positions": []},
        "opportunities": [
            {
                "opportunity_id": "oi-1",
                "symbol": "BTC-USD",
                "asset_class": "CRYPTO",
                "sector": "CRYPTO",
                "strategy": "breakout",
                "broker": "DEMO",
                "confidence": 0.9,
                "historical_performance": 0.85,
                "execution_quality": 0.9,
                "broker_performance": 0.9,
                "liquidity": 0.9,
                "regime_alignment": 0.9,
                "expected_reward": 300.0,
                "expected_risk": 70.0,
                "requested_capital": 2500.0,
            }
        ],
    }

    report = build_capital_allocation_intelligence_report(dashboard_payload)

    assert report["allocation_summary"]["shadow_runtime_stage"] == "AFTER_OPPORTUNITY_INTELLIGENCE"
    assert report["allocation_plan"]
    assert report["allocation_plan"][0]["asset"] == "BTC-USD"
    assert report["execution_action"] == "NO_EXECUTION"


def test_phase155cd_api_and_dashboard_response_shape() -> None:
    state = DashboardHydrationCoordinator().hydrate(
        account_payload={"broker": "DEMO", "account_mode": "paper", "cash_balance": 10000.0, "buying_power": 10000.0},
        broker_payload={"selected_broker": "DEMO", "broker_mode": "paper"},
        execution_payload={"execution_state": "READY", "avg_slippage_bps": 1.0, "avg_spread_bps": 1.0},
        market_payload={
            "liquidity_state": "HEALTHY",
            "regime_state": "RISK_ON",
            "opportunities": [
                {
                    "opportunity_id": "api-1",
                    "symbol": "BTC-USD",
                    "asset_class": "CRYPTO",
                    "sector": "CRYPTO",
                    "strategy": "breakout",
                    "broker": "DEMO",
                    "confidence": 0.9,
                    "historical_performance": 0.85,
                    "execution_quality": 0.9,
                    "broker_performance": 0.9,
                    "liquidity": 0.9,
                    "regime_alignment": 0.9,
                    "expected_reward": 300.0,
                    "expected_risk": 70.0,
                    "requested_capital": 2500.0,
                }
            ],
        },
        risk_payload={"risk_state": "NORMAL", "gate_status": "OPEN"},
    )

    response = TestClient(create_app(lambda: state)).get("/api/v1/capital-allocation-intelligence")
    frontend = build_frontend_payload(state)
    html = _dashboard_page()

    assert response.status_code == 200
    payload = response.json()
    assert payload["section"] == "capital_allocation_intelligence"
    assert payload["advisory_only"] is True
    assert payload["execution_allowed"] is False
    assert set(payload) >= {"capital_plan", "allocation_summary", "portfolio_metrics", "recommendations", "warnings"}
    assert frontend["sections"]["capital_allocation_intelligence"]["execution_allowed"] is False
    assert "Capital Allocation Intelligence" in html
    assert "Unused Capital" in html


def test_phase155cd_advisory_only_and_no_live_execution_contract() -> None:
    result = CapitalAllocationOptimizer().optimize(
        available_capital=10000.0,
        ranked_opportunities=[
            _opportunity("safe", rank=1, asset="BTC-USD", asset_class="CRYPTO", sector="CRYPTO", broker="DEMO", strategy="breakout", score=90.0)
        ],
    )

    assert result["advisory_only"] is True
    assert result["shadow_mode"] is True
    assert result["execution_action"] == "NO_EXECUTION"
    assert result["execution_allowed"] is False
    assert result["live_trading_enabled"] is False
    assert all(row["execution_allowed"] is False for row in result["allocation_plan"])

from __future__ import annotations

from copy import deepcopy

from backend.allocation.caie_portfolio_optimizer import optimize_portfolio_shadow
from backend.allocation.caie_scoring_engine import score_validated_opportunity
from backend.allocation.opportunity_validator import validate_opportunity_proposal


def _proposal(
    proposal_id: str,
    *,
    symbol: str = "BTC-USD",
    asset_class: str = "CRYPTO",
    probability: float = 0.7,
    confidence: float = 0.8,
    expected_drawdown_pct: float = 0.2,
    risk_score: float = 35.0,
    requested_capital: float = 1000.0,
) -> dict:
    return {
        "proposal_id": proposal_id,
        "symbol": symbol,
        "asset_class": asset_class,
        "probability": probability,
        "confidence": confidence,
        "expected_drawdown_pct": expected_drawdown_pct,
        "risk_score": risk_score,
        "requested_capital": requested_capital,
    }


def _opportunity(
    proposal: dict,
    *,
    broker: str,
    liquidity_score: float = 1.0,
    regime_alignment: float = 1.0,
) -> dict:
    validated = validate_opportunity_proposal(proposal)
    assert validated["valid"] is True
    score = score_validated_opportunity(
        validated,
        context={
            "liquidity_score": liquidity_score,
            "regime_alignment": regime_alignment,
        },
    )
    assert score["valid"] is True
    return {
        "proposal": validated,
        "score": score,
        "broker": broker,
    }


def test_phase155c_single_opportunity() -> None:
    opportunities = [_opportunity(_proposal("p1"), broker="COINBASE")]

    result = optimize_portfolio_shadow(opportunities, available_capital=2000.0)

    assert result["valid"] is True
    assert len(result["ranked_opportunities"]) == 1
    assert len(result["selected_opportunities"]) == 1
    assert result["unused_capital"] == 1000.0


def test_phase155c_multiple_ranked_opportunities() -> None:
    opportunities = [
        _opportunity(_proposal("p-high", probability=0.85, expected_drawdown_pct=0.2), broker="COINBASE"),
        _opportunity(_proposal("p-mid", probability=0.7, expected_drawdown_pct=0.2), broker="OANDA"),
        _opportunity(_proposal("p-low", probability=0.55, expected_drawdown_pct=0.2), broker="OANDA"),
    ]

    result = optimize_portfolio_shadow(opportunities, available_capital=5000.0)

    assert result["ranked_opportunities"][0]["proposal_id"] == "p-high"
    assert result["ranked_opportunities"][1]["proposal_id"] == "p-mid"
    assert result["ranked_opportunities"][2]["proposal_id"] == "p-low"


def test_phase155c_insufficient_capital() -> None:
    opportunities = [
        _opportunity(_proposal("p1", requested_capital=1000.0), broker="COINBASE"),
        _opportunity(_proposal("p2", requested_capital=1000.0), broker="OANDA"),
    ]

    result = optimize_portfolio_shadow(opportunities, available_capital=1000.0)

    allocated_total = sum(x["allocated_capital"] for x in result["recommended_capital_allocations"])
    assert allocated_total <= 1000.0
    assert result["unused_capital"] >= 0.0


def test_phase155c_broker_cap_reached() -> None:
    opportunities = [
        _opportunity(_proposal("p1", requested_capital=1000.0), broker="COINBASE"),
        _opportunity(_proposal("p2", requested_capital=1000.0), broker="COINBASE"),
        _opportunity(_proposal("p3", requested_capital=1000.0), broker="OANDA"),
    ]

    result = optimize_portfolio_shadow(
        opportunities,
        available_capital=3000.0,
        broker_caps={"COINBASE": 1000.0, "OANDA": 3000.0},
    )

    broker_alloc = result["concentration_metrics"]["broker_weights"]
    coinbase_capital = sum(
        row["allocated_capital"]
        for row in result["recommended_capital_allocations"]
        if row["broker"] == "COINBASE"
    )
    assert coinbase_capital <= 1000.0
    assert "COINBASE" in broker_alloc


def test_phase155c_asset_class_cap_reached() -> None:
    opportunities = [
        _opportunity(_proposal("p1", asset_class="CRYPTO", requested_capital=1000.0), broker="COINBASE"),
        _opportunity(_proposal("p2", asset_class="CRYPTO", requested_capital=1000.0), broker="OANDA"),
        _opportunity(_proposal("p3", asset_class="FX", requested_capital=1000.0), broker="OANDA"),
    ]

    result = optimize_portfolio_shadow(
        opportunities,
        available_capital=3000.0,
        asset_class_caps={"CRYPTO": 1000.0, "FX": 3000.0},
    )

    crypto_capital = sum(
        row["allocated_capital"]
        for row in result["recommended_capital_allocations"]
        if row["asset_class"] == "CRYPTO"
    )
    assert crypto_capital <= 1000.0


def test_phase155c_concentration_penalty_applied() -> None:
    concentrated = [
        _opportunity(_proposal("p1", asset_class="CRYPTO", requested_capital=1000.0), broker="COINBASE"),
        _opportunity(_proposal("p2", asset_class="CRYPTO", requested_capital=1000.0), broker="COINBASE"),
    ]
    diversified = [
        _opportunity(_proposal("p1", asset_class="CRYPTO", requested_capital=1000.0), broker="COINBASE"),
        _opportunity(_proposal("p2", asset_class="FX", requested_capital=1000.0), broker="OANDA"),
    ]

    concentrated_result = optimize_portfolio_shadow(concentrated, available_capital=2000.0)
    diversified_result = optimize_portfolio_shadow(diversified, available_capital=2000.0)

    assert concentrated_result["concentration_metrics"]["concentration_penalty"] > diversified_result["concentration_metrics"]["concentration_penalty"]


def test_phase155c_hold_cash_scenario() -> None:
    low_quality = [
        _opportunity(
            _proposal("p1", probability=0.25, expected_drawdown_pct=0.8, requested_capital=1000.0),
            broker="COINBASE",
        ),
    ]

    result = optimize_portfolio_shadow(low_quality, available_capital=3000.0, min_quality_score=70.0)

    assert result["selected_opportunities"] == []
    assert result["unused_capital"] == 3000.0


def test_phase155c_deterministic_ordering() -> None:
    opportunities = [
        _opportunity(_proposal("p2", probability=0.7, expected_drawdown_pct=0.2), broker="OANDA"),
        _opportunity(_proposal("p1", probability=0.7, expected_drawdown_pct=0.2), broker="COINBASE"),
    ]

    first = optimize_portfolio_shadow(opportunities, available_capital=3000.0)
    second = optimize_portfolio_shadow(deepcopy(opportunities), available_capital=3000.0)

    assert first == second


def test_phase155c_invalid_input_fail_closed() -> None:
    invalid = optimize_portfolio_shadow(None, available_capital=1000.0)

    not_scored = optimize_portfolio_shadow(
        [
            {
                "proposal": validate_opportunity_proposal(_proposal("p1")),
                "score": {"valid": False, "score": None},
                "broker": "COINBASE",
            }
        ],
        available_capital=1000.0,
    )

    assert invalid["valid"] is False
    assert invalid["execution_action"] == "NO_EXECUTION"
    assert not_scored["valid"] is False
    assert not_scored["execution_action"] == "NO_EXECUTION"


def test_phase155c_advisory_shadow_only_output_contract() -> None:
    opportunities = [_opportunity(_proposal("p1"), broker="COINBASE")]
    result = optimize_portfolio_shadow(opportunities, available_capital=1000.0)

    assert result["advisory_only"] is True
    assert result["shadow_mode"] is True
    assert result["execution_action"] == "NO_EXECUTION"

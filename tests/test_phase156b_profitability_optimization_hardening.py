from __future__ import annotations

import time

from backend.analytics.capital_allocation_engine import CapitalAllocationEngine
from backend.analytics.profitability_optimization_score import (
    build_profitability_optimization_score,
    rank_profitability_opportunities,
)
from backend.analytics.profitability_optimizer import ProfitabilityOptimizer
from backend.governance.css_unified_trade_gate import CSSUnifiedTradeGate


def _high_quality() -> dict:
    return {
        "symbol": "HQ",
        "strategy_id": "alpha",
        "expected_edge": 72.0,
        "win_rate": 0.72,
        "drawdown": 0.08,
        "realized_pnl": 210.0,
        "average_pnl": 21.0,
        "trade_count": 18,
        "asset_class_concentration": 0.25,
        "confidence": 0.70,
        "capital_efficiency": 0.82,
    }


def _weak_quality() -> dict:
    return {
        "symbol": "WEAK",
        "strategy_id": "beta",
        "expected_edge": 12.0,
        "win_rate": 0.42,
        "drawdown": 0.45,
        "realized_pnl": 8.0,
        "average_pnl": 1.0,
        "trade_count": 4,
        "asset_class_concentration": 0.85,
        "confidence": 0.82,
        "capital_efficiency": 0.12,
    }


def test_phase156b_high_quality_opportunities_rank_above_weak() -> None:
    ranked = rank_profitability_opportunities([_weak_quality(), _high_quality()])

    assert [row["symbol"] for row in ranked] == ["HQ", "WEAK"]
    assert ranked[0]["profitability_optimization_score"] > ranked[1]["profitability_optimization_score"]
    assert ranked[0]["advisory_only"] is True
    assert ranked[0]["execution_allowed"] is False


def test_phase156b_drawdown_reduces_score() -> None:
    low_drawdown = build_profitability_optimization_score(_high_quality())
    high_drawdown = build_profitability_optimization_score({**_high_quality(), "drawdown": 0.80})

    assert high_drawdown["profitability_optimization_score"] < low_drawdown["profitability_optimization_score"]
    assert high_drawdown["score_components"]["drawdown_score"] < low_drawdown["score_components"]["drawdown_score"]


def test_phase156b_poor_reliability_reduces_allocation() -> None:
    allocations = CapitalAllocationEngine().allocate(
        [
            {
                "symbol": "PROVEN",
                "score": 100.0,
                "profitability_optimization_score": 86.0,
                "trade_count": 25,
                "realized_pnl": 250.0,
            },
            {
                "symbol": "UNPROVEN",
                "score": 100.0,
                "profitability_optimization_score": 28.0,
                "trade_count": 25,
                "realized_pnl": 250.0,
            },
        ],
        available_capital=1000.0,
        max_symbol_weight=0.9,
        min_trade_count=3,
        restricted_score_threshold=0.0,
    )

    proven = next(row for row in allocations if row["symbol"] == "PROVEN")
    unproven = next(row for row in allocations if row["symbol"] == "UNPROVEN")
    assert proven["allocation_amount"] > unproven["allocation_amount"]
    assert all(row["execution_allowed"] is False for row in allocations)


def test_phase156b_missing_data_is_conservative_not_aggressive() -> None:
    score = build_profitability_optimization_score({})

    assert score["profitability_quality_status"] == "RESTRICTED"
    assert score["profitability_optimization_score"] < 45.0
    assert score["missing_data_policy"] == "CONSERVATIVE"
    assert score["execution_allowed"] is False
    assert score["can_authorize_trade"] is False


def test_phase156b_optimizer_output_is_deterministic() -> None:
    opportunities = [_weak_quality(), _high_quality(), {**_high_quality(), "symbol": "HQ2"}]

    first = rank_profitability_opportunities(opportunities)
    second = rank_profitability_opportunities(opportunities)

    assert first == second


def test_phase156b_optimizer_does_not_authorize_trades_or_bypass_gate() -> None:
    ranked = rank_profitability_opportunities([_high_quality()])
    candidate = {
        "symbol": "HQ",
        "asset_class": "crypto",
        "expected_value": 10.0,
        "cost": 1.0,
        "probability": 0.95,
    }
    gate_decision = CSSUnifiedTradeGate().approve_trade(
        candidate,
        session={"role": "VIEWER", "created": time.time()},
        portfolio_state={"crypto": 0},
        engine_mode="SAFE",
    )

    assert ranked[0]["can_authorize_trade"] is False
    assert ranked[0]["execution_allowed"] is False
    assert gate_decision.approved is False
    assert "unauthorized role" in gate_decision.reason


def test_phase156b_profitability_optimizer_package_contains_advisory_rankings() -> None:
    package = ProfitabilityOptimizer().optimize(
        completed_trades=[
            {"strategy_id": "alpha", "asset_class": "CRYPTO", "confidence": 0.70, "realized_pnl": 10.0},
            {"strategy_id": "alpha", "asset_class": "CRYPTO", "confidence": 0.72, "realized_pnl": 8.0},
            {"strategy_id": "beta", "asset_class": "FX", "confidence": 0.90, "realized_pnl": -5.0},
        ],
        strategy_league_table=[
            {"strategy_id": "alpha", "sample_size": 12, "recent_trend": 0.30, "drawdown": 0.10},
            {"strategy_id": "beta", "sample_size": 8, "recent_trend": -0.20, "drawdown": 0.40},
        ],
        position_context=[],
    )

    rankings = package["profitability_optimization_rankings"]
    assert rankings[0]["strategy_id"] == "alpha"
    assert package["metadata"]["recommendation_only"] is True
    assert package["metadata"]["execution_allowed"] is False
    assert all(row["execution_allowed"] is False for row in rankings)

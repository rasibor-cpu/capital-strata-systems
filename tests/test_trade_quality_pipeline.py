from __future__ import annotations

from backend.analytics.dynamic_acceptance_engine import DynamicAcceptanceEngine
from backend.analytics.execution_selection_engine import ExecutionSelectionEngine
from backend.analytics.opportunity_ranking_engine import OpportunityRankingEngine
from backend.analytics.trade_quality_scoring_engine import TradeQualityScoringEngine


def _candidate(trade_id, symbol, regime, strategy, replay, concentration, alloc, rr):
    return {
        "trade_id": trade_id,
        "symbol": symbol,
        "asset_class": "EQUITY",
        "market_regime": regime,
        "strategy_score": strategy,
        "replay_confidence": replay,
        "concentration_risk": concentration,
        "allocation_weight": alloc,
        "allocation_amount": 2000.0,
        "available_capital": 10000.0,
        "recommended_position_size": 1500.0,
        "exit_action": "TRAIL",
        "exit_confidence": 0.8,
        "risk_reward": rr,
    }


def test_pipeline_selects_expected_top_candidate() -> None:
    scorer = TradeQualityScoringEngine()
    ranker = OpportunityRankingEngine()
    acceptance = DynamicAcceptanceEngine()
    selector = ExecutionSelectionEngine()

    scored = scorer.score_candidates(
        [
            _candidate("t1", "AAPL", "TRENDING", 0.9, 0.9, 0.1, 0.25, 2.2),
            _candidate("t2", "MSFT", "RANGING", 0.45, 0.4, 0.55, 0.1, 0.9),
            _candidate("t3", "TSLA", "UNKNOWN", 0.1, 0.1, 0.9, 0.02, 0.3),
        ]
    )
    ranked = ranker.rank(scored, top_n=3)

    threshold = acceptance.resolve_threshold(
        market_regime="TRENDING",
        volatility=0.2,
        drawdown=-0.05,
        recent_performance=0.2,
        concentration_risk=0.2,
    )["threshold"]

    selection = selector.select(ranked, acceptance_threshold=threshold, top_n=1)

    assert len(selection["selected"]) == 1
    assert selection["selected"][0]["trade_id"] == "t1"
    assert selection["rejected"]

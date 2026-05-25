from __future__ import annotations

from backend.intelligence.opportunity_scoring_engine import OpportunityScoringEngine


def main() -> None:
    engine = OpportunityScoringEngine()

    malformed = [None, {}, {"signal_strength": "bad", "execution_viable": "yes"}]
    for item in malformed:
        result = engine.score_opportunity(item)
        assert 0.0 <= result.total_score <= 1.0

    candidates = [
        {"symbol": "A", "signal_strength": 0.9, "confidence": 0.9, "expected_edge": 0.03, "liquidity_score": 0.8, "execution_viable": True},
        {"symbol": "B", "signal_strength": 0.2, "confidence": 0.4, "expected_edge": 0.005, "estimated_cost": 0.02, "estimated_slippage": 0.02, "execution_viable": True},
        {"symbol": "C", "signal_strength": 0.8, "confidence": 0.8, "expected_edge": 0.02, "execution_viable": False},
    ]
    ranked = engine.rank_opportunities(candidates)
    assert len(ranked) == 3
    assert ranked[0]["composite_score"] >= ranked[1]["composite_score"]
    assert ranked[1]["composite_score"] >= ranked[2]["composite_score"]
    assert "scoring_summary" in ranked[0]

    deterministic_a = engine.rank_opportunities(candidates)
    deterministic_b = engine.rank_opportunities(candidates)
    assert [r["symbol"] for r in deterministic_a] == [r["symbol"] for r in deterministic_b]

    print("Opportunity scoring test PASSED")


if __name__ == "__main__":
    main()

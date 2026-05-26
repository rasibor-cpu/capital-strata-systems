from __future__ import annotations

from backend.intelligence.allocation_intelligence_engine import AllocationIntelligenceEngine


def main() -> None:
    engine = AllocationIntelligenceEngine()

    malformed = [
        None,
        {},
        {"composite_score": "bad", "asset_class": None},
    ]

    for row in malformed:
        result = engine.analyze_candidate(row)
        assert 0.0 <= result.recommended_weight <= 1.0
        assert 0.0 <= result.diversification_score <= 1.0
        assert 0.0 <= result.concentration_risk <= 1.0

    candidates = [
        {
            "symbol": "A",
            "asset_class": "crypto",
            "composite_score": 0.8,
            "adjusted_edge": 0.02,
            "survivability_score": 0.7,
            "regime_confidence": 0.8,
        },
        {
            "symbol": "B",
            "asset_class": "fx",
            "composite_score": 0.6,
            "adjusted_edge": 0.01,
            "survivability_score": 0.6,
            "regime_confidence": 0.7,
        },
        {
            "symbol": "C",
            "asset_class": "crypto",
            "composite_score": 0.4,
            "adjusted_edge": -0.01,
            "survivability_score": 0.5,
            "regime_confidence": 0.4,
        },
    ]

    portfolio_state = engine.analyze_portfolio(candidates)
    batch = engine.analyze_batch(candidates)

    assert len(batch) == 3
    assert isinstance(portfolio_state, dict)

    deterministic_a = engine.analyze_batch(candidates)
    deterministic_b = engine.analyze_batch(candidates)

    assert deterministic_a == deterministic_b

    print("Allocation intelligence test PASSED")


if __name__ == "__main__":
    main()

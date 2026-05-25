from __future__ import annotations

from backend.intelligence.opportunity_scoring_engine import OpportunityScoringEngine


def main() -> None:
    engine = OpportunityScoringEngine()
    result = engine.score_opportunity({"signal_strength": 3.0, "confidence": -2.0, "spread_score": 999.0})
    assert 0.0 <= result.total_score <= 1.0
    assert 0.0 <= result.execution_quality <= 1.0
    assert 0.0 <= result.survivability_score <= 1.0
    print("Opportunity normalization test PASSED")


if __name__ == "__main__":
    main()

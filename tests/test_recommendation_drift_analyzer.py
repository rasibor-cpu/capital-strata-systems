from __future__ import annotations

from backend.portfolio.recommendation_drift_analyzer import RecommendationDriftAnalyzer


def test_recommendation_drift_analyzer_reports_stable_sequence() -> None:
    history = [
        {"recommendation": "MAINTAIN", "policy_profile": "balanced", "market_regime": "RANGING"},
        {"recommendation": "MAINTAIN", "policy_profile": "balanced", "market_regime": "RANGING"},
        {"recommendation": "MAINTAIN", "policy_profile": "balanced", "market_regime": "RANGING"},
    ]

    result = RecommendationDriftAnalyzer().analyze(history)

    assert result["status"] == "OK"
    assert result["drift_status"] == "GREEN"
    assert result["drift_score"] == 0.0
    assert result["recommendation_stability"] == 100.0
    assert result["excessive_oscillation"] is False


def test_recommendation_drift_analyzer_detects_oscillation_and_reversals() -> None:
    history = [
        {"recommendation": "PAUSE_NEW_TRADES", "policy_profile": "defensive", "market_regime": "HIGH_VOLATILITY"},
        {"recommendation": "INCREASE_RISK", "policy_profile": "growth", "market_regime": "TRENDING_UP"},
        {"recommendation": "PAUSE_NEW_TRADES", "policy_profile": "defensive", "market_regime": "HIGH_VOLATILITY"},
        {"recommendation": "INCREASE_RISK", "policy_profile": "growth", "market_regime": "TRENDING_UP"},
    ]

    result = RecommendationDriftAnalyzer().analyze(history)

    assert result["status"] == "OK"
    assert result["drift_status"] == "RED"
    assert result["drift_score"] == 100.0
    assert result["recommendation_reversals"] == 3
    assert result["excessive_oscillation"] is True
    assert result["policy_drift"] is True
    assert result["regime_drift"] is True


def test_recommendation_drift_analyzer_fails_closed_with_short_sequence() -> None:
    result = RecommendationDriftAnalyzer().analyze([{"recommendation": "MAINTAIN"}])

    assert result["status"] == "DATA UNAVAILABLE"
    assert result["drift_score"] is None
    assert result["drift_severity"] == "RED"

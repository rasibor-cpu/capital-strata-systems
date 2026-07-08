from __future__ import annotations

from backend.learning.adaptive_strategy_intelligence import AdaptiveStrategyIntelligenceEngine
from backend.learning.regime_strategy_mapper import RegimeStrategyMapper, normalize_regime
from backend.learning.strategy_effectiveness_tracker import StrategyEffectivenessTracker


def _row(
    strategy: str,
    realized_return: float | None,
    *,
    accepted: bool = True,
    regime: str = "TRENDING",
    asset_class: str = "CRYPTO",
    confidence: float = 0.82,
    holding: float = 30.0,
):
    payload = {
        "strategy_id": strategy,
        "accepted": accepted,
        "market_regime": regime,
        "asset_class": asset_class,
        "confidence": confidence,
        "holding_period_minutes": holding,
    }
    if realized_return is not None:
        payload["realized_return"] = realized_return
    return payload


def test_phase157a_profitable_strategy_recommends_confidence_weight_increase() -> None:
    history = [_row("breakout", value, regime="TRENDING") for value in [2.0, 1.5, 3.0, -0.3, 2.2, 1.1]]

    result = AdaptiveStrategyIntelligenceEngine(min_evidence=5).analyze(history)

    rec = result["adaptive_recommendations"][0]
    assert result["status"] == "OK"
    assert rec["strategy"] == "breakout"
    assert rec["recommendation"] == "Increase confidence weighting"
    assert result["strategy_effectiveness"]["strategy_metrics"]["breakout"]["win_rate"] > 60.0
    assert result["advisory_only"] is True
    assert result["execution_allowed"] is False
    assert result["broker_execution_armed"] is False


def test_phase157a_deteriorating_strategy_reduces_or_suppresses() -> None:
    history = [_row("mean_reversion", value, regime="RANGING") for value in [-2.0, -1.5, 0.2, -3.0, -1.2, -0.8]]

    metrics = StrategyEffectivenessTracker().analyze(history, min_evidence=5)

    recommendation = metrics["strategy_metrics"]["mean_reversion"]["recommendation"]
    assert recommendation in {"Reduce confidence weighting", "Temporarily suppress"}
    assert metrics["strategy_metrics"]["mean_reversion"]["average_return"] < 0.0


def test_phase157a_insufficient_evidence_requests_more_data() -> None:
    history = [_row("carry", 1.0), _row("carry", -0.2)]

    result = AdaptiveStrategyIntelligenceEngine(min_evidence=5).analyze(history)

    assert result["status"] == "PARTIAL"
    assert result["adaptive_recommendations"][0]["recommendation"] == "Needs additional evidence"
    assert result["adaptive_recommendations"][0]["confidence_level"] == "LOW"


def test_phase157a_conflicting_evidence_increases_monitoring() -> None:
    history = [_row("stat_arb", value) for value in [-1.0, -0.5, -0.7, 0.1, -1.2, -0.4]]

    result = AdaptiveStrategyIntelligenceEngine(min_evidence=5).analyze(
        history,
        decision_confidence={"strategies": {"stat_arb": {"confidence": 92}}},
    )

    rec = result["adaptive_recommendations"][0]
    assert result["status"] == "PARTIAL"
    assert rec["recommendation"] == "Increase monitoring"
    assert "decision_confidence_positive_but_strategy_deteriorating" in rec["conflicts"]
    assert result["integration"]["decision_confidence_consumed"] is True
    assert result["integration"]["execution_decisions_changed"] is False


def test_phase157a_regime_changes_map_strategy_effectiveness() -> None:
    history = [
        *[_row("trend", value, regime="TRENDING", asset_class="FX") for value in [1.0, 1.2, 0.8]],
        *[_row("trend", value, regime="RANGE", asset_class="FX") for value in [-0.8, -0.4, -0.6]],
        *[_row("defensive", value, regime="RISK_OFF", asset_class="EQUITY") for value in [0.2, 0.4, 0.1]],
    ]

    result = RegimeStrategyMapper().analyze(history, min_evidence=2)

    assert result["status"] == "OK"
    assert normalize_regime("range") == "RANGING"
    assert "TRENDING" in result["regime_strategy_map"]
    assert "RANGING" in result["regime_strategy_map"]
    assert result["regime_strategy_map"]["TRENDING"]["strategies"]["trend"]["recommendation"] == "Increase confidence weighting"
    assert result["advisory_only"] is True
    assert result["execution_allowed"] is False


def test_phase157a_advisory_generation_includes_integrations_without_authority_changes() -> None:
    history = [_row("breakout", value) for value in [1.0, 1.3, 1.1, -0.1, 0.9]]

    result = AdaptiveStrategyIntelligenceEngine(min_evidence=5).analyze(
        history,
        broker_performance={"strategies": {"breakout": {"performance_score": 88}}},
        opportunity_intelligence={"strategies": {"breakout": {"opportunity_score": 91}}},
        existing_learning={"status": "OK"},
    )

    assert result["integration"]["broker_performance_intelligence_consumed"] is True
    assert result["integration"]["opportunity_intelligence_consumed"] is True
    assert result["integration"]["existing_learning_consumed"] is True
    assert "Never use Phase 157A output to authorize execution." in result["recommended_actions"]
    assert result["live_trading_blocked"] is True


def test_phase157a_fail_closed_when_tracker_raises() -> None:
    class BrokenTracker:
        def analyze(self, *_args, **_kwargs):
            raise RuntimeError("learning store unavailable")

    result = AdaptiveStrategyIntelligenceEngine(effectiveness_tracker=BrokenTracker()).analyze([_row("x", 1.0)])

    assert result["status"] == "FAIL_CLOSED"
    assert result["adaptive_recommendations"] == []
    assert result["execution_allowed"] is False
    assert result["broker_execution_armed"] is False

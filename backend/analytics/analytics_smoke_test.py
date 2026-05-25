from __future__ import annotations

from backend.analytics.cost_reality_engine import CostRealityEngine
from backend.analytics.signal_quality_engine import SignalQualityEngine
from backend.analytics.trade_outcome_analytics_engine import (
    TradeOutcomeAnalyticsEngine,
)


def test_trade_outcome_analytics_engine_smoke() -> None:
    engine = TradeOutcomeAnalyticsEngine()
    payload = engine.summarize(
        [
            {"symbol": "BTC-USD", "realized_pnl": 10.0},
            {"symbol": "ETH-USD", "realized_pnl": -5.0},
        ]
    )

    assert payload["trade_count"] == 2
    assert payload["expectancy"] == 2.5
    assert payload["profit_factor"] == 2.0
    assert payload["mode"] == "safe_read_only"


def test_cost_reality_engine_smoke() -> None:
    engine = CostRealityEngine()
    payload = engine.evaluate(asset_class="crypto", expected_move_bps=50.0)

    assert payload["asset_class"] == "crypto"
    assert payload["total_cost_bps"] > 0
    assert payload["net_edge_bps"] == 20.0
    assert payload["mode"] == "safe_read_only"


def test_signal_quality_engine_smoke() -> None:
    engine = SignalQualityEngine()
    payload = engine.evaluate(
        signal_strength=0.8,
        regime_alignment=0.7,
        persistence_score=0.6,
        false_positive_rate=0.1,
    )

    assert payload["confidence_score"] > 0
    assert payload["quality_label"] in {
        "institutional_grade",
        "high_quality",
        "moderate_quality",
        "weak_quality",
        "poor_quality",
    }
    assert payload["mode"] == "safe_read_only"
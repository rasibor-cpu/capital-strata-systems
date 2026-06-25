from __future__ import annotations

from backend.trading.autonomous_opportunity_intelligence_engine import (
    AutonomousOpportunityIntelligenceEngine,
)


def _candles() -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    base = 100.0
    for idx in range(20):
        close = base + (idx * 0.6)
        rows.append(
            {
                "open": close - 0.2,
                "high": close + 0.4,
                "low": close - 0.4,
                "close": close,
                "volume": 1000.0 + (idx * 20.0),
            }
        )
    return rows


def test_engine_outputs_all_m5_sections() -> None:
    engine = AutonomousOpportunityIntelligenceEngine()

    result = engine.analyze(
        instrument={
            "symbol": "BTC-USD",
            "asset_class": "CRYPTO",
            "tick_size": 0.01,
            "min_order_size": 0.001,
            "max_order_size": 1000.0,
        },
        candidate={
            "symbol": "BTC-USD",
            "current_price": 68000.0,
            "market_snapshot": {"candles": _candles()},
        },
        decision={
            "selected_strategy": "momentum_breakout",
            "confidence": 0.74,
            "concentration_score": 0.2,
        },
        historical_records=[
            {"symbol": "BTC-USD", "strategy_id": "momentum_breakout", "market_regime": "TRENDING", "realized_pnl": 120.0},
            {"symbol": "BTC-USD", "strategy_id": "momentum_breakout", "market_regime": "TRENDING", "realized_pnl": -30.0},
        ],
    )

    assert "multi_timeframe" in result
    assert "regime_confirmation" in result
    assert "cross_asset" in result
    assert "liquidity" in result
    assert "session_awareness" in result
    assert "confidence_calibration" in result
    assert "ranking_v2" in result
    assert "explainability" in result

    assert 0.0 <= result["multi_timeframe"]["normalized_score"] <= 1.0
    assert 0.0 <= result["regime_confirmation"]["confidence"] <= 1.0
    assert 0.0 <= result["cross_asset"]["confirmation_score"] <= 1.0
    assert 0.0 <= result["liquidity"]["liquidity_score"] <= 1.0
    assert 0.0 <= result["confidence_calibration"]["calibrated_confidence"] <= 1.0
    assert 0.0 <= result["ranking_v2"]["weighted_score"] <= 1.0


def test_adaptive_improvement_report() -> None:
    engine = AutonomousOpportunityIntelligenceEngine()

    report = engine.generate_adaptive_improvement_report(
        trade_outcomes=[
            {"symbol": "BTC-USD", "market_regime": "TRENDING", "strategy_id": "s1", "realized_pnl": 20.0},
            {"symbol": "ETH-USD", "market_regime": "RANGE", "strategy_id": "s2", "realized_pnl": -10.0},
            {"symbol": "BTC-USD", "market_regime": "TRENDING", "strategy_id": "s1", "realized_pnl": 5.0},
        ],
        strategy_records=[
            {"strategy_id": "s1", "realized_pnl": 25.0},
            {"strategy_id": "s2", "realized_pnl": -10.0},
        ],
    )

    assert "best_symbols" in report
    assert "worst_symbols" in report
    assert "best_strategies" in report
    assert "worst_strategies" in report
    assert "best_regimes" in report
    assert "worst_regimes" in report
    assert report["suggested_parameter_improvements"]

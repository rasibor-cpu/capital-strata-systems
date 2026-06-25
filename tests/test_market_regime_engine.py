from __future__ import annotations

from backend.analytics.market_regime_engine import MarketRegimeEngine


def _candles(*, count: int, start: float, step: float, volume: float = 1000.0) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    for index in range(count):
        close = start + (index * step)
        rows.append(
            {
                "open": close - 0.2,
                "high": close + 0.4,
                "low": close - 0.4,
                "close": close,
                "volume": volume + (index * 5.0),
            }
        )
    return rows


def test_feature_extraction() -> None:
    engine = MarketRegimeEngine()
    features = engine.extract_features(_candles(count=30, start=100.0, step=0.6))

    assert set(features.keys()) == {
        "ATR",
        "volatility",
        "trend_strength",
        "momentum",
        "volume_state",
        "price_acceleration",
        "direction",
        "confidence",
    }
    assert features["ATR"] > 0
    assert features["direction"] in {"UP", "DOWN", "FLAT"}


def test_regime_classification_trending() -> None:
    engine = MarketRegimeEngine()
    analysis = engine.analyze_market(_candles(count=40, start=100.0, step=1.0))

    assert analysis["market_regime"] in {
        "TRENDING",
        "BREAKOUT",
        "HIGH_VOLATILITY",
    }
    assert 0.0 <= analysis["confidence"] <= 1.0


def test_unknown_regime() -> None:
    engine = MarketRegimeEngine()
    analysis = engine.analyze_market(_candles(count=2, start=100.0, step=0.1))

    assert analysis["market_regime"] == "UNKNOWN"
    assert analysis["confidence"] == 0.0

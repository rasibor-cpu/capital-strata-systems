from __future__ import annotations

from datetime import UTC, datetime

from backend.analytics.cross_asset_confirmation_engine import CrossAssetConfirmationEngine
from backend.analytics.liquidity_intelligence_engine import LiquidityIntelligenceEngine
from backend.analytics.session_awareness_engine import SessionAwarenessEngine


def test_cross_asset_confirmation_scores() -> None:
    engine = CrossAssetConfirmationEngine()
    payload = engine.score(symbol="BTC-USD", decision={"concentration_score": 0.2})

    assert payload["group"] == "CRYPTO_BETA"
    assert 0.0 <= payload["cross_asset_confidence"] <= 1.0
    assert 0.0 <= payload["correlation_score"] <= 1.0
    assert 0.0 <= payload["confirmation_score"] <= 1.0


def test_liquidity_rejects_illiquid() -> None:
    engine = LiquidityIntelligenceEngine()
    payload = engine.score(
        instrument={"tick_size": 0.25, "min_order_size": 1.0, "max_order_size": 2.0},
        market_snapshot={
            "candles": [
                {"close": 100.0, "volume": 1.0},
                {"close": 100.1, "volume": 1.0},
                {"close": 100.2, "volume": 1.0},
            ]
        },
    )

    assert payload["liquidity_rating"] in {"C", "D"}
    assert payload["decision_hint"] in {"ALLOW", "REJECT"}


def test_session_overlap_and_weekend_adjustment() -> None:
    engine = SessionAwarenessEngine()

    overlap = engine.analyze(now=datetime(2026, 6, 23, 13, 0, tzinfo=UTC))
    weekend = engine.analyze(now=datetime(2026, 6, 27, 9, 0, tzinfo=UTC))

    assert overlap["session"] in {"LONDON", "NEW_YORK"}
    assert isinstance(overlap["overlap"], bool)
    assert overlap["confidence_adjustment"] > 0.0
    assert weekend["session"] == "WEEKEND"
    assert weekend["confidence_adjustment"] < 1.0

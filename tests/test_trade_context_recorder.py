from __future__ import annotations

import pytest

from backend.analytics.trade_context_recorder import (
    TradeContextRecorder,
    TradeContextRecorderError,
)


def _payload() -> dict[str, object]:
    return {
        "trade_id": "t-001",
        "symbol": "eur/usd",
        "asset_class": "fx",
        "strategy": "momentum_v2",
        "entry_time": "2026-06-24T10:00:00+00:00",
        "exit_time": "2026-06-24T10:05:00+00:00",
        "market_regime": "trending",
        "volatility": 0.012,
        "trend_strength": 0.043,
        "confidence": 0.81,
        "broker": "sim",
        "session": "s-123",
    }


def test_trade_context_creation() -> None:
    recorder = TradeContextRecorder()
    context = recorder.record_context(_payload())

    assert context["trade_id"] == "t-001"
    assert context["symbol"] == "EUR/USD"
    assert context["asset_class"] == "FX"
    assert context["market_regime"] == "TRENDING"
    assert context["confidence"] == 0.81


def test_trade_context_validation_fail_closed() -> None:
    recorder = TradeContextRecorder()
    payload = _payload()
    payload.pop("trade_id")

    with pytest.raises(TradeContextRecorderError):
        recorder.record_context(payload)

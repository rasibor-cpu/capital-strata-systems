from __future__ import annotations

import pytest

from backend.analytics.adaptive_exit_engine import AdaptiveExitEngine, AdaptiveExitEngineError


def _open_trade() -> dict[str, object]:
    return {
        "trade_id": "trade-1",
        "symbol": "EUR/USD",
        "entry_price": 1.1000,
    }


def _memory(max_hold_seconds: int = 3600) -> dict[str, object]:
    return {
        "record_count": 12,
        "max_hold_seconds": max_hold_seconds,
    }


def test_hold_in_strong_trend() -> None:
    engine = AdaptiveExitEngine()
    result = engine.recommend_exit(
        open_trade_context=_open_trade(),
        market_regime="TRENDING",
        strategy_memory_summary=_memory(),
        current_unrealized_pnl=0.0,
        holding_duration=1200,
        volatility=0.01,
        trend_strength=0.8,
    )

    assert result["action"] == "HOLD"


def test_take_profit_when_positive_pnl_and_regime_weakens() -> None:
    engine = AdaptiveExitEngine()
    result = engine.recommend_exit(
        open_trade_context=_open_trade(),
        market_regime="RANGING",
        strategy_memory_summary=_memory(),
        current_unrealized_pnl=0.02,
        holding_duration=800,
        volatility=0.015,
        trend_strength=0.2,
    )

    assert result["action"] == "TAKE_PROFIT"


def test_stop_loss_when_drawdown_threshold_breached() -> None:
    engine = AdaptiveExitEngine(drawdown_threshold=-0.015)
    result = engine.recommend_exit(
        open_trade_context=_open_trade(),
        market_regime="TRENDING",
        strategy_memory_summary=_memory(),
        current_unrealized_pnl=-0.03,
        holding_duration=200,
        volatility=0.02,
        trend_strength=0.7,
    )

    assert result["action"] == "STOP_LOSS"


def test_trailing_recommendation_in_strong_trend() -> None:
    engine = AdaptiveExitEngine()
    result = engine.recommend_exit(
        open_trade_context=_open_trade(),
        market_regime="BREAKOUT",
        strategy_memory_summary=_memory(),
        current_unrealized_pnl=0.03,
        holding_duration=300,
        volatility=0.012,
        trend_strength=0.9,
    )

    assert result["action"] == "TRAIL"


def test_time_exit_after_max_hold() -> None:
    engine = AdaptiveExitEngine()
    result = engine.recommend_exit(
        open_trade_context=_open_trade(),
        market_regime="TRENDING",
        strategy_memory_summary=_memory(max_hold_seconds=600),
        current_unrealized_pnl=0.01,
        holding_duration=1200,
        volatility=0.011,
        trend_strength=0.7,
    )

    assert result["action"] == "TIME_EXIT"


def test_invalid_input_fail_closed() -> None:
    engine = AdaptiveExitEngine()

    with pytest.raises(AdaptiveExitEngineError):
        engine.recommend_exit(
            open_trade_context={"trade_id": "", "symbol": "EUR/USD"},
            market_regime="TRENDING",
            strategy_memory_summary=_memory(),
            current_unrealized_pnl=0.0,
            holding_duration=100,
            volatility=0.01,
            trend_strength=0.4,
        )


def test_deterministic_output() -> None:
    engine = AdaptiveExitEngine()
    kwargs = {
        "open_trade_context": _open_trade(),
        "market_regime": "TRENDING",
        "strategy_memory_summary": _memory(max_hold_seconds=1500),
        "current_unrealized_pnl": 0.012,
        "holding_duration": 600,
        "volatility": 0.01,
        "trend_strength": 0.8,
    }

    first = engine.recommend_exit(**kwargs)
    second = engine.recommend_exit(**kwargs)

    assert first == second

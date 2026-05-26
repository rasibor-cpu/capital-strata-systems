
from backend.governance.prop_trading_governor import (
    PropTradingGovernor,
    PropTradingEvaluationState,
)


def test_governor_allows_clean_state():
    governor = PropTradingGovernor()

    state = PropTradingEvaluationState(
        trading_day="2026-05-26",
        daily_loss_limit=2500.0,
        max_drawdown_limit=5000.0,
        realized_pnl=500.0,
        unrealized_pnl=100.0,
        peak_equity=100000.0,
        current_equity=100200.0,
        open_positions=2,
        violations=[],
    )

    result = governor.evaluate(state)

    assert result["allowed"] is True
    assert result["blocked"] is False
    assert result["reasons"] == []


def test_governor_blocks_daily_loss():
    governor = PropTradingGovernor()

    state = PropTradingEvaluationState(
        trading_day="2026-05-26",
        daily_loss_limit=2500.0,
        max_drawdown_limit=5000.0,
        realized_pnl=-3000.0,
        unrealized_pnl=0.0,
        peak_equity=100000.0,
        current_equity=97000.0,
        open_positions=1,
        violations=[],
    )

    result = governor.evaluate(state)

    assert result["blocked"] is True
    assert "daily_loss_limit_breached" in result["reasons"]


def test_governor_blocks_drawdown():
    governor = PropTradingGovernor()

    state = PropTradingEvaluationState(
        trading_day="2026-05-26",
        daily_loss_limit=2500.0,
        max_drawdown_limit=5000.0,
        realized_pnl=-1000.0,
        unrealized_pnl=-1000.0,
        peak_equity=100000.0,
        current_equity=94000.0,
        open_positions=1,
        violations=[],
    )

    result = governor.evaluate(state)

    assert result["blocked"] is True
    assert "max_drawdown_limit_breached" in result["reasons"]


def test_governor_blocks_position_limit():
    governor = PropTradingGovernor(
        max_open_positions=3
    )

    state = PropTradingEvaluationState(
        trading_day="2026-05-26",
        daily_loss_limit=2500.0,
        max_drawdown_limit=5000.0,
        realized_pnl=0.0,
        unrealized_pnl=0.0,
        peak_equity=100000.0,
        current_equity=100000.0,
        open_positions=5,
        violations=[],
    )

    result = governor.evaluate(state)

    assert result["blocked"] is True
    assert "max_open_positions_exceeded" in result["reasons"]


def test_governor_blocks_manual_violations():
    governor = PropTradingGovernor()

    state = PropTradingEvaluationState(
        trading_day="2026-05-26",
        daily_loss_limit=2500.0,
        max_drawdown_limit=5000.0,
        realized_pnl=0.0,
        unrealized_pnl=0.0,
        peak_equity=100000.0,
        current_equity=100000.0,
        open_positions=1,
        violations=[
            "news_blackout_violation",
            "weekend_hold_violation",
        ],
    )

    result = governor.evaluate(state)

    assert result["blocked"] is True
    assert "news_blackout_violation" in result["reasons"]
    assert "weekend_hold_violation" in result["reasons"]

"""
Headless Guarded Execution Entry – Phase 1 Complete
"""

from dataclasses import dataclass
from datetime import datetime, timezone

from backend.app.risk.daily_trade_guard import evaluate_daily_trade_guard
from backend.app.risk.loss_streak_guard import evaluate_loss_streak
from backend.app.risk.concurrency_guard import evaluate_concurrency
from backend.app.risk.equity_drawdown_guard import (
    evaluate_equity_drawdown,
    EquityDrawdownPolicy,
)


@dataclass
class HeadlessConfig:
    max_trades_per_day: int = 15
    max_consecutive_losses: int = 5
    cooldown_seconds: int = 3600
    max_positions: int = 20
    execution_locked: bool = True


def run_headless(
    steps: int,
    symbol: str,
    execution_mode: str,
    current_open_positions: int = 0,
    trades_today: int = 0,
    consecutive_losses: int = 0,
    current_equity: float | None = None,
    peak_equity: float | None = None,
    cfg: HeadlessConfig | None = None,
):

    if cfg is None:
        cfg = HeadlessConfig()

    timestamp = datetime.now(timezone.utc).isoformat()

    daily = evaluate_daily_trade_guard(
        trades_today=trades_today,
        max_trades=cfg.max_trades_per_day,
    )

    loss = evaluate_loss_streak(
        consecutive_losses=consecutive_losses,
        max_consecutive_losses=cfg.max_consecutive_losses,
        cooldown_seconds=cfg.cooldown_seconds,
    )

    concurrency = evaluate_concurrency(
        open_positions=current_open_positions,
        max_positions=cfg.max_positions,
    )

    equity = evaluate_equity_drawdown(
        current_equity=current_equity,
        peak_equity=peak_equity,
        policy=EquityDrawdownPolicy(max_drawdown_pct=25.0),
    )

    guards = {
        "daily_trade_guard": daily,
        "loss_streak_guard": loss,
        "concurrency_guard": concurrency,
        "equity_drawdown_guard": equity,
    }

    blocked_reasons = []
    blocked_breakdown = {}

    for name, result in guards.items():
        if not result.get("allowed", False):
            blocked_reasons.append(result.get("reason"))
            blocked_breakdown[f"{name}_blocked"] = 1
        else:
            blocked_breakdown[f"{name}_blocked"] = 0

    if cfg.execution_locked:
        blocked_reasons.append("Execution layer locked (no live trades).")
        blocked_breakdown["locked_execution_blocked"] = 1
    else:
        blocked_breakdown["locked_execution_blocked"] = 0

    blocked_breakdown["other_blocked"] = 0

    blocked = len(blocked_reasons) > 0

    return {
        "ok": True,
        "mode": execution_mode,
        "live_execution": False,
        "locked": cfg.execution_locked,
        "steps_requested": steps,
        "symbol": symbol,
        "simulated_trades": 0,
        "blocked_trades": steps if blocked else 0,
        "blocked_breakdown": blocked_breakdown,
        **guards,
        "trade_preview": {
            "symbol": symbol,
            "side": "buy",
            "units": 1,
            "order_type": "MARKET",
        },
        "blocked_reason": " | ".join(blocked_reasons) if blocked else None,
        "timestamp_utc": timestamp,
    }

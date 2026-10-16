"""Personality-specific exit management for copied (paper) positions.

Exits are evaluated for every open position regardless of mandate state: an
expired or revoked mandate stops NEW copies, but existing positions keep their
stop, take-profit, trailing and time-stop protection until a safe exit.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from backend.trading_profiles.risk_personalities import PersonalityPolicy


@dataclass(frozen=True)
class CopiedPosition:
    position_id: str
    follower_user_id: str
    symbol: str
    asset_class: str
    side: str
    notional: float
    entry_price: float
    stop_distance_pct: float
    opened_at: datetime
    best_price: float
    signal_id: str = ""
    mandate_id: str | None = None
    trader_id: str = ""


@dataclass(frozen=True)
class ExitDecision:
    action: str  # HOLD | EXIT
    reason: str
    best_price: float
    stop_price: float
    take_profit_price: float


def _direction(side: str) -> int:
    return 1 if str(side).upper() == "BUY" else -1


def evaluate_exit(
    position: CopiedPosition,
    policy: PersonalityPolicy,
    *,
    mark_price: float,
    now: datetime,
    source_exited: bool = False,
) -> ExitDecision:
    d = _direction(position.side)
    stop_frac = position.stop_distance_pct / 100.0
    stop_price = position.entry_price * (1 - d * stop_frac)
    take_profit_price = position.entry_price * (1 + d * stop_frac * policy.take_profit_r_multiple)
    best = max(position.best_price, mark_price) if d > 0 else min(position.best_price, mark_price)

    def decision(action: str, reason: str) -> ExitDecision:
        return ExitDecision(action, reason, best, stop_price, take_profit_price)

    if (mark_price - stop_price) * d <= 0:
        return decision("EXIT", "STOP_LOSS")
    if (mark_price - take_profit_price) * d >= 0:
        return decision("EXIT", "TAKE_PROFIT")
    risk_per_unit = position.entry_price * stop_frac
    best_gain = (best - position.entry_price) * d
    if best_gain >= policy.trailing_activation_r * risk_per_unit:
        giveback = best_gain - (mark_price - position.entry_price) * d
        if giveback >= policy.trailing_giveback_fraction * best_gain:
            return decision("EXIT", "TRAILING_STOP")
    if now - position.opened_at >= timedelta(hours=policy.time_stop_hours):
        return decision("EXIT", "TIME_STOP")
    if source_exited:
        return decision("EXIT", "SOURCE_TRADER_EXITED")
    return decision("HOLD", "within_limits")


def realized_pnl(position: CopiedPosition, exit_price: float, fee_bps: float) -> float:
    gross = (exit_price - position.entry_price) / position.entry_price * position.notional * _direction(position.side)
    exit_fee = position.notional * fee_bps / 10_000.0
    return round(gross - exit_fee, 2)

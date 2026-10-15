"""CSS customer trading-mode and trader-profile contracts (paper-only foundation).

No broker adapters, order submission, authorization renewal, or execution enablement.
Risk caps are policy inputs, never permission to bypass platform-wide limits.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum


class TradingMode(str, Enum):
    SIMULATED = "simulated"
    COPY = "copy"
    AUTONOMOUS = "autonomous"


class Trader(str, Enum):
    SAFE = "css_safe"
    CONSERVATIVE = "css_conservative"
    BALANCED = "css_balanced"
    AGGRESSIVE = "css_aggressive"
    ULTRA_AGGRESSIVE = "css_ultra_aggressive"


@dataclass(frozen=True)
class StrategyProfile:
    trader: Trader
    strategy_id: str
    instrument_scope: tuple[str, ...]
    entry_family: str
    exit_family: str
    max_authorization: timedelta
    leverage_permitted: bool = False


PROFILES: dict[Trader, StrategyProfile] = {
    Trader.SAFE: StrategyProfile(Trader.SAFE, "CSS-SAFE-V1", ("cash", "equity"), "quality_selective", "capital_defensive", timedelta(days=30)),
    Trader.CONSERVATIVE: StrategyProfile(Trader.CONSERVATIVE, "CSS-CONS-V1", ("equity", "etf"), "trend_confirmed", "trailing_defensive", timedelta(days=14)),
    Trader.BALANCED: StrategyProfile(Trader.BALANCED, "CSS-BAL-V1", ("equity", "etf", "fx"), "diversified_multisignal", "risk_reward", timedelta(days=7)),
    Trader.AGGRESSIVE: StrategyProfile(Trader.AGGRESSIVE, "CSS-AGG-V1", ("equity", "fx", "crypto"), "momentum_volatility", "volatility_trailing", timedelta(hours=24)),
    Trader.ULTRA_AGGRESSIVE: StrategyProfile(Trader.ULTRA_AGGRESSIVE, "CSS-ULTRA-V1", ("equity", "fx", "crypto", "options"), "high_conviction_breakout", "hard_stop_and_time", timedelta(hours=8), True),
}


@dataclass(frozen=True)
class CopyMandate:
    customer_id: str
    brokerage_account_id: str
    trader: Trader
    strategy_id: str
    authorized_at: datetime
    expires_at: datetime
    allocated_capital: float
    max_loss_fraction: float
    allowed_instruments: tuple[str, ...]
    mfa_verified: bool
    revoked: bool = False

    def permits_new_trade(self, now: datetime, *, instrument: str) -> bool:
        """Fail closed; this is a prerequisite, never a complete trade authorization."""
        profile = PROFILES.get(self.trader)
        if profile is None or self.strategy_id != profile.strategy_id:
            return False
        if now.tzinfo is None or self.authorized_at.tzinfo is None or self.expires_at.tzinfo is None:
            return False
        if self.revoked or not self.mfa_verified or not self.customer_id or not self.brokerage_account_id:
            return False
        if not (0 < self.allocated_capital < float("inf")) or not (0 < self.max_loss_fraction <= 1):
            return False
        if not (self.authorized_at <= now < self.expires_at <= self.authorized_at + profile.max_authorization):
            return False
        return instrument in self.allowed_instruments and instrument in profile.instrument_scope


@dataclass(frozen=True)
class CustomerPreference:
    mode: TradingMode
    selected_trader: Trader | None = None

    def __post_init__(self) -> None:
        if self.mode is TradingMode.COPY and self.selected_trader is None:
            raise ValueError("Copy mode requires an explicit trader selection")


def may_submit_live_order(*_args: object, **_kwargs: object) -> bool:
    """Foundation is paper-only. Live execution is intentionally unavailable."""
    return False

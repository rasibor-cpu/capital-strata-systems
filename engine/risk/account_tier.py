"""
engine.risk.account_tier — REA Capital Trading Engine (Governance)

Purpose:
- Provide account-tier aware risk limits (V1 Micro Mode).
- Micro Mode auto-activates when equity <= 500 (USD-equivalent).
- Standard Mode returns "no overrides" so existing parameters remain unchanged.

Micro Mode Overrides (equity <= 500):
- max_risk_per_trade_pct: 5%
- max_daily_drawdown_pct: 20%
- max_trades_per_day: 10
- max_concurrent_positions: 5
- max_concurrent_losses: 3
- loss_streak_cooldown_trigger: 3 losses
- cooldown_minutes: 30
All other parameters remain whatever the engine already uses.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict, Any


class AccountTier(str, Enum):
    MICRO = "MICRO"
    STANDARD = "STANDARD"


@dataclass(frozen=True)
class TierOverrides:
    """
    Only fields that are not None are meant to override existing engine settings.
    """
    max_risk_per_trade_pct: Optional[float] = None
    max_daily_drawdown_pct: Optional[float] = None
    max_trades_per_day: Optional[int] = None
    max_concurrent_positions: Optional[int] = None
    max_concurrent_losses: Optional[int] = None
    loss_streak_cooldown_trigger: Optional[int] = None
    cooldown_minutes: Optional[int] = None


MICRO_EQUITY_THRESHOLD: float = 500.0


def detect_tier(equity: float) -> AccountTier:
    """
    Safe tier detection. Fail-closed: invalid equity => STANDARD (no overrides).
    """
    try:
        eq = float(equity)
    except Exception:
        return AccountTier.STANDARD

    if eq <= MICRO_EQUITY_THRESHOLD:
        return AccountTier.MICRO
    return AccountTier.STANDARD


def get_overrides_for_tier(tier: AccountTier) -> TierOverrides:
    if tier == AccountTier.MICRO:
        return TierOverrides(
            max_risk_per_trade_pct=0.05,      # 5%
            max_daily_drawdown_pct=0.20,      # 20%
            max_trades_per_day=10,
            max_concurrent_positions=1,       # keep suggested
            max_concurrent_losses=3,
            loss_streak_cooldown_trigger=3,
            cooldown_minutes=30,
        )
    # STANDARD: no overrides (engine keeps its existing parameters)
    return TierOverrides()


def apply_tier_overrides(base: Dict[str, Any], equity: float) -> Dict[str, Any]:
    """
    Apply MICRO overrides to an existing risk config dict.
    - Only overwrites keys for overrides that are not None.
    - Returns a NEW dict (does not mutate caller).
    """
    cfg = dict(base or {})
    tier = detect_tier(equity)
    ov = get_overrides_for_tier(tier)

    if ov.max_risk_per_trade_pct is not None:
        cfg["max_risk_per_trade_pct"] = ov.max_risk_per_trade_pct
    if ov.max_daily_drawdown_pct is not None:
        cfg["max_daily_drawdown_pct"] = ov.max_daily_drawdown_pct
    if ov.max_trades_per_day is not None:
        cfg["max_trades_per_day"] = ov.max_trades_per_day
    if ov.max_concurrent_positions is not None:
        cfg["max_concurrent_positions"] = ov.max_concurrent_positions
    if ov.max_concurrent_losses is not None:
        cfg["max_concurrent_losses"] = ov.max_concurrent_losses
    if ov.loss_streak_cooldown_trigger is not None:
        cfg["loss_streak_cooldown_trigger"] = ov.loss_streak_cooldown_trigger
    if ov.cooldown_minutes is not None:
        cfg["cooldown_minutes"] = ov.cooldown_minutes

    cfg["account_tier"] = tier.value
    cfg["account_tier_threshold"] = MICRO_EQUITY_THRESHOLD
    return cfg

"""
Capital Strata Systems (CSS)
Session Risk Policy Definitions
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class SessionRiskPolicy:

    policy_name: str
    starting_capital: float

    max_capital_deployed_pct: float
    max_asset_pct: float
    max_concurrent_trades: int

    max_daily_loss_usd: float
    max_weekly_drawdown_usd: float

    allowed_asset_classes: List[str]

    broker_mode: str
    strategy_mode: str

    session_expiry_time: str

    allow_live_trading: bool


# ---------------------------------------------------
# Conservative Policy
# ---------------------------------------------------


def conservative_policy(starting_capital: float) -> SessionRiskPolicy:

    return SessionRiskPolicy(
        policy_name="Conservative",

        starting_capital=starting_capital,

        max_capital_deployed_pct=0.50,
        max_asset_pct=0.20,
        max_concurrent_trades=2,

        max_daily_loss_usd=starting_capital * 0.02,
        max_weekly_drawdown_usd=starting_capital * 0.04,

        allowed_asset_classes=["CRYPTO"],

        broker_mode="paper",
        strategy_mode="mean_reversion",

        session_expiry_time="17:00",

        allow_live_trading=False,
    )


# ---------------------------------------------------
# Balanced Policy
# ---------------------------------------------------


def balanced_policy(starting_capital: float) -> SessionRiskPolicy:

    # --- SMALL ACCOUNT OVERRIDE ---
    if starting_capital <= 1000:

        max_asset_pct = 0.40
        max_capital_deployed_pct = 0.90

    else:

        max_asset_pct = 0.25
        max_capital_deployed_pct = 0.75

    return SessionRiskPolicy(
        policy_name="Balanced",

        starting_capital=starting_capital,

        max_capital_deployed_pct=max_capital_deployed_pct,
        max_asset_pct=max_asset_pct,
        max_concurrent_trades=3,

        max_daily_loss_usd=starting_capital * 0.03,
        max_weekly_drawdown_usd=starting_capital * 0.06,

        allowed_asset_classes=["CRYPTO"],

        broker_mode="paper",
        strategy_mode="mean_reversion",

        session_expiry_time="17:00",

        allow_live_trading=False,
    )


# ---------------------------------------------------
# Aggressive Test Policy
# ---------------------------------------------------


def aggressive_test_policy(starting_capital: float) -> SessionRiskPolicy:

    return SessionRiskPolicy(
        policy_name="Aggressive Test",

        starting_capital=starting_capital,

        max_capital_deployed_pct=1.00,
        max_asset_pct=0.60,
        max_concurrent_trades=5,

        max_daily_loss_usd=starting_capital * 0.10,
        max_weekly_drawdown_usd=starting_capital * 0.20,

        allowed_asset_classes=["CRYPTO"],

        broker_mode="paper",
        strategy_mode="mean_reversion",

        session_expiry_time="23:59",

        allow_live_trading=True,
    )


# ---------------------------------------------------
# Custom Policy
# ---------------------------------------------------


def custom_policy(
    policy_name: str,
    starting_capital: float,
    max_capital_deployed_pct: float,
    max_asset_pct: float,
    max_concurrent_trades: int,
    max_daily_loss_usd: float,
    max_weekly_drawdown_usd: float,
    allowed_asset_classes: List[str],
    broker_mode: str,
    strategy_mode: str,
    session_expiry_time: str,
    allow_live_trading: bool,
) -> SessionRiskPolicy:

    return SessionRiskPolicy(
        policy_name=policy_name,
        starting_capital=starting_capital,

        max_capital_deployed_pct=max_capital_deployed_pct,
        max_asset_pct=max_asset_pct,
        max_concurrent_trades=max_concurrent_trades,

        max_daily_loss_usd=max_daily_loss_usd,
        max_weekly_drawdown_usd=max_weekly_drawdown_usd,

        allowed_asset_classes=allowed_asset_classes,

        broker_mode=broker_mode,
        strategy_mode=strategy_mode,

        session_expiry_time=session_expiry_time,

        allow_live_trading=allow_live_trading,
    )
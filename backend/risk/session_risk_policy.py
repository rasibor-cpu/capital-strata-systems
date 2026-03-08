"""
Capital Strata Systems (CSS)
Session Risk Policy

Defines the risk policy selected at session startup.
The active policy is locked for the duration of the session
and is intended to be passed into the Portfolio Risk Governor.

Controlled Risk Governance. Controlled Compounding.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, List


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
    allow_live_trading: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _validate_pct(name: str, value: float) -> None:
    if not 0.0 < value <= 1.0:
        raise ValueError(f"{name} must be > 0.0 and <= 1.0")


def _validate_positive(name: str, value: float) -> None:
    if value <= 0:
        raise ValueError(f"{name} must be greater than 0")


def _validate_nonempty_list(name: str, value: List[str]) -> None:
    if not value:
        raise ValueError(f"{name} must not be empty")


def validate_policy(policy: SessionRiskPolicy) -> SessionRiskPolicy:
    if not policy.policy_name.strip():
        raise ValueError("policy_name must not be blank")

    _validate_positive("starting_capital", policy.starting_capital)
    _validate_pct("max_capital_deployed_pct", policy.max_capital_deployed_pct)
    _validate_pct("max_asset_pct", policy.max_asset_pct)

    if policy.max_asset_pct > policy.max_capital_deployed_pct:
        raise ValueError("max_asset_pct cannot exceed max_capital_deployed_pct")

    if policy.max_concurrent_trades <= 0:
        raise ValueError("max_concurrent_trades must be greater than 0")

    _validate_positive("max_daily_loss_usd", policy.max_daily_loss_usd)
    _validate_positive("max_weekly_drawdown_usd", policy.max_weekly_drawdown_usd)
    _validate_nonempty_list("allowed_asset_classes", policy.allowed_asset_classes)

    if policy.broker_mode not in {"paper", "live"}:
        raise ValueError("broker_mode must be 'paper' or 'live'")

    if not policy.strategy_mode.strip():
        raise ValueError("strategy_mode must not be blank")

    if not policy.session_expiry_time.strip():
        raise ValueError("session_expiry_time must not be blank")

    if policy.broker_mode == "live" and not policy.allow_live_trading:
        raise ValueError(
            "broker_mode cannot be 'live' when allow_live_trading is False"
        )

    return policy


def conservative_policy(starting_capital: float) -> SessionRiskPolicy:
    return validate_policy(
        SessionRiskPolicy(
            policy_name="Conservative",
            starting_capital=starting_capital,
            max_capital_deployed_pct=0.50,
            max_asset_pct=0.10,
            max_concurrent_trades=4,
            max_daily_loss_usd=10.0,
            max_weekly_drawdown_usd=30.0,
            allowed_asset_classes=["crypto_spot"],
            broker_mode="paper",
            strategy_mode="vwap_mean_reversion",
            session_expiry_time="17:00",
            allow_live_trading=False,
        )
    )


def balanced_policy(starting_capital: float) -> SessionRiskPolicy:
    return validate_policy(
        SessionRiskPolicy(
            policy_name="Balanced",
            starting_capital=starting_capital,
            max_capital_deployed_pct=0.60,
            max_asset_pct=0.15,
            max_concurrent_trades=6,
            max_daily_loss_usd=15.0,
            max_weekly_drawdown_usd=50.0,
            allowed_asset_classes=["crypto_spot"],
            broker_mode="paper",
            strategy_mode="vwap_mean_reversion",
            session_expiry_time="17:00",
            allow_live_trading=False,
        )
    )


def aggressive_test_policy(starting_capital: float) -> SessionRiskPolicy:
    return validate_policy(
        SessionRiskPolicy(
            policy_name="Aggressive Test",
            starting_capital=starting_capital,
            max_capital_deployed_pct=0.70,
            max_asset_pct=0.20,
            max_concurrent_trades=8,
            max_daily_loss_usd=20.0,
            max_weekly_drawdown_usd=75.0,
            allowed_asset_classes=["crypto_spot"],
            broker_mode="paper",
            strategy_mode="vwap_mean_reversion",
            session_expiry_time="17:00",
            allow_live_trading=False,
        )
    )


def custom_policy(
    *,
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
    allow_live_trading: bool = False,
) -> SessionRiskPolicy:
    return validate_policy(
        SessionRiskPolicy(
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
    )
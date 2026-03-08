"""
Capital Strata Systems (CSS)
Portfolio Risk Governor

Portfolio-level risk controls driven by a locked session policy.
The governor is initialized once at session startup and must not
be mutated during runtime except through position state changes.

Controlled Risk Governance. Controlled Compounding.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple

from backend.risk.session_risk_policy import SessionRiskPolicy


@dataclass
class TradeApproval:
    approved: bool
    reason: str


class PortfolioRiskGovernor:
    def __init__(self, policy: SessionRiskPolicy):
        self.policy = policy
        self.starting_capital = policy.starting_capital
        self.positions: Dict[str, float] = {}

    def current_deployed_capital(self) -> float:
        return sum(self.positions.values())

    def deployed_pct(self) -> float:
        if self.starting_capital <= 0:
            return 0.0
        return self.current_deployed_capital() / self.starting_capital

    def concurrent_trades(self) -> int:
        return len(self.positions)

    def asset_exposure_usd(self, asset: str) -> float:
        return self.positions.get(asset, 0.0)

    def asset_exposure_pct(self, asset: str) -> float:
        if self.starting_capital <= 0:
            return 0.0
        return self.asset_exposure_usd(asset) / self.starting_capital

    def remaining_capacity_usd(self) -> float:
        max_deployable = self.starting_capital * self.policy.max_capital_deployed_pct
        remaining = max_deployable - self.current_deployed_capital()
        return max(0.0, remaining)

    def can_open_new_asset(self, asset: str) -> bool:
        if asset in self.positions:
            return True
        return self.concurrent_trades() < self.policy.max_concurrent_trades

    def approve_trade(self, asset: str, size_usd: float) -> Tuple[bool, str]:
        if not asset or not asset.strip():
            return False, "Blocked: asset must not be blank"

        if size_usd <= 0:
            return False, "Blocked: trade size must be greater than zero"

        if not self.can_open_new_asset(asset):
            return False, "Blocked: max concurrent trades reached"

        new_total_capital = self.current_deployed_capital() + size_usd
        new_deployed_pct = new_total_capital / self.starting_capital

        if new_deployed_pct > self.policy.max_capital_deployed_pct:
            return (
                False,
                "Blocked: portfolio capital deployment exceeded",
            )

        asset_total = self.positions.get(asset, 0.0) + size_usd
        asset_pct = asset_total / self.starting_capital

        if asset_pct > self.policy.max_asset_pct:
            return False, "Blocked: asset exposure limit exceeded"

        return True, "Approved"

    def approve_trade_result(self, asset: str, size_usd: float) -> TradeApproval:
        approved, reason = self.approve_trade(asset, size_usd)
        return TradeApproval(approved=approved, reason=reason)

    def register_trade(self, asset: str, size_usd: float) -> None:
        approved, reason = self.approve_trade(asset, size_usd)
        if not approved:
            raise ValueError(reason)

        self.positions[asset] = self.positions.get(asset, 0.0) + size_usd

    def reduce_trade(self, asset: str, size_usd: float) -> None:
        if size_usd <= 0:
            raise ValueError("Reduction size must be greater than zero")

        if asset not in self.positions:
            raise ValueError(f"Asset not found in open positions: {asset}")

        new_size = self.positions[asset] - size_usd

        if new_size > 0:
            self.positions[asset] = new_size
        else:
            del self.positions[asset]

    def close_trade(self, asset: str) -> None:
        if asset in self.positions:
            del self.positions[asset]

    def clear_all_positions(self) -> None:
        self.positions.clear()

    def snapshot(self) -> dict:
        return {
            "policy_name": self.policy.policy_name,
            "starting_capital": self.starting_capital,
            "deployed_capital": self.current_deployed_capital(),
            "deployment_pct": self.deployed_pct(),
            "remaining_capacity_usd": self.remaining_capacity_usd(),
            "positions": dict(self.positions),
            "limits": {
                "max_capital_deployed_pct": self.policy.max_capital_deployed_pct,
                "max_asset_pct": self.policy.max_asset_pct,
                "max_concurrent_trades": self.policy.max_concurrent_trades,
                "max_daily_loss_usd": self.policy.max_daily_loss_usd,
                "max_weekly_drawdown_usd": self.policy.max_weekly_drawdown_usd,
                "allowed_asset_classes": list(self.policy.allowed_asset_classes),
                "broker_mode": self.policy.broker_mode,
                "strategy_mode": self.policy.strategy_mode,
                "session_expiry_time": self.policy.session_expiry_time,
                "allow_live_trading": self.policy.allow_live_trading,
            },
        }
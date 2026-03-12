from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List
import hashlib
import json


# ============================================================
# GOVERNANCE POLICY
# ============================================================

@dataclass(frozen=True)
class ProfitTakingPolicy:
    profit_tiers: List[float]
    max_reentry_fraction_of_realized_profit: float
    principal_protection: bool
    lifecycle_reset_on_reentry: bool
    martingale_allowed: bool
    use_unrealized_gains_for_reentry: bool

    def as_dict(self) -> Dict[str, Any]:
        return {
            "profit_tiers": list(self.profit_tiers),
            "max_reentry_fraction_of_realized_profit": self.max_reentry_fraction_of_realized_profit,
            "principal_protection": self.principal_protection,
            "lifecycle_reset_on_reentry": self.lifecycle_reset_on_reentry,
            "martingale_allowed": self.martingale_allowed,
            "use_unrealized_gains_for_reentry": self.use_unrealized_gains_for_reentry,
        }

    def determinism_hash(self) -> str:
        payload = json.dumps(self.as_dict(), sort_keys=True).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()


DEFAULT_PROFIT_TAKING_POLICY = ProfitTakingPolicy(
    profit_tiers=[0.10, 0.20, 0.35, 0.50],
    max_reentry_fraction_of_realized_profit=0.50,
    principal_protection=True,
    lifecycle_reset_on_reentry=True,
    martingale_allowed=False,
    use_unrealized_gains_for_reentry=False,
)


def get_locked_profit_taking_policy() -> ProfitTakingPolicy:
    return DEFAULT_PROFIT_TAKING_POLICY


def get_policy_snapshot() -> Dict[str, Any]:
    policy = get_locked_profit_taking_policy()
    snap = policy.as_dict()
    snap["determinism_hash"] = policy.determinism_hash()
    snap["governance_locked"] = True
    return snap


# ============================================================
# LIVE POSITION STATE
# ============================================================

@dataclass
class ManagedPosition:
    symbol: str
    entry_price: float
    initial_size: float
    remaining_size: float
    stop_loss_price: float
    take_profit_price: float
    realized_profit: float = 0.0

    tier_10_hit: bool = False
    tier_20_hit: bool = False
    tier_35_hit: bool = False
    tier_50_hit: bool = False

    runner_mode: bool = False
    trailing_stop_price: float = 0.0

    def current_return_pct(self, current_price: float) -> float:
        if self.entry_price <= 0:
            return 0.0
        return (current_price - self.entry_price) / self.entry_price


# ============================================================
# UNIFIED PROFIT MANAGER
# ============================================================

class ProfitManager:
    """
    Unified live CSS profit manager.

    Merges:
    - governance profit-taking policy
    - tiered profit ladder logic
    - hard stop / take profit logic
    - redeployable realized profit logic
    - runner mode with trailing stop
    """

    def __init__(
        self,
        take_profit_bps: float = 10000.0,
        stop_loss_bps: float = 100.0,
        trail_trigger_bps: float = 40.0,
        locked_profit_bps: float = 15.0,
        runner_fraction_at_final_tier: float = 0.25,
        runner_trailing_distance_pct: float = 0.08,
    ) -> None:
        self.policy = get_locked_profit_taking_policy()
        self.take_profit = take_profit_bps / 10000.0
        self.stop_loss = stop_loss_bps / 10000.0
        self.trail_trigger = trail_trigger_bps / 10000.0
        self.locked_profit = locked_profit_bps / 10000.0

        self.runner_fraction_at_final_tier = float(runner_fraction_at_final_tier)
        self.runner_trailing_distance_pct = float(runner_trailing_distance_pct)

    def create_position(
        self,
        symbol: str,
        entry_price: float,
        size: float,
    ) -> ManagedPosition:
        return ManagedPosition(
            symbol=symbol,
            entry_price=entry_price,
            initial_size=size,
            remaining_size=size,
            stop_loss_price=entry_price * (1.0 - self.stop_loss),
            take_profit_price=entry_price * (1.0 + self.take_profit),
        )

    def evaluate(
        self,
        position: ManagedPosition,
        current_price: float,
    ) -> Dict[str, Any]:
        if position.entry_price <= 0:
            return self._result(
                action="HOLD",
                reason="invalid entry",
                pnl_pct=0.0,
            )

        change = position.current_return_pct(current_price)

        # 1) Hard stop
        active_stop = self._get_active_stop(position)
        if active_stop > 0 and current_price <= active_stop:
            return self._result(
                action="STOP_LOSS",
                reason="active stop hit",
                pnl_pct=change,
            )

        # 2) Tier ladder before any absolute TP
        tier_action = self._evaluate_profit_tiers(position, current_price, change)
        if tier_action["action"] != "HOLD":
            return tier_action

        # 3) Runner-mode trailing logic
        if position.runner_mode:
            new_runner_stop = current_price * (1.0 - self.runner_trailing_distance_pct)
            if new_runner_stop > position.trailing_stop_price:
                position.trailing_stop_price = new_runner_stop

            if position.trailing_stop_price > 0 and current_price <= position.trailing_stop_price:
                return self._result(
                    action="CLOSE_FULL",
                    reason="runner trailing stop hit",
                    pnl_pct=change,
                    partial_size=position.remaining_size,
                )

        # 4) Profit lock
        if change >= self.trail_trigger and change <= self.locked_profit:
            return self._result(
                action="TAKE_PROFIT",
                reason="profit lock triggered",
                pnl_pct=change,
            )

        # 5) Absolute TP only before runner mode starts
        if (not position.runner_mode) and current_price >= position.take_profit_price:
            return self._result(
                action="TAKE_PROFIT",
                reason="full take profit hit",
                pnl_pct=change,
            )

        return self._result(
            action="HOLD",
            reason="position within active range",
            pnl_pct=change,
        )

    def _evaluate_profit_tiers(
        self,
        position: ManagedPosition,
        current_price: float,
        return_pct: float,
    ) -> Dict[str, Any]:
        tiers = self.policy.profit_tiers

        # Tier 10%: take 25%
        if len(tiers) > 0 and return_pct >= tiers[0] and not position.tier_10_hit:
            take = position.remaining_size * 0.25
            profit = take * (current_price - position.entry_price)
            position.realized_profit += profit
            position.remaining_size -= take
            position.tier_10_hit = True

            return self._result(
                action="PARTIAL_TAKE_PROFIT",
                reason="tier 10% hit",
                pnl_pct=return_pct,
                partial_size=take,
                new_stop=position.entry_price,
            )

        # Tier 20%: take 50% of remainder
        if len(tiers) > 1 and return_pct >= tiers[1] and not position.tier_20_hit:
            take = position.remaining_size * 0.50
            profit = take * (current_price - position.entry_price)
            position.realized_profit += profit
            position.remaining_size -= take
            position.tier_20_hit = True

            return self._result(
                action="PARTIAL_TAKE_PROFIT",
                reason="tier 20% hit",
                pnl_pct=return_pct,
                partial_size=take,
                new_stop=position.entry_price,
            )

        # Tier 35%: take 50% of remainder and tighten stop
        if len(tiers) > 2 and return_pct >= tiers[2] and not position.tier_35_hit:
            take = position.remaining_size * 0.50
            profit = take * (current_price - position.entry_price)
            position.realized_profit += profit
            position.remaining_size -= take
            position.tier_35_hit = True

            return self._result(
                action="PARTIAL_TAKE_PROFIT",
                reason="tier 35% hit",
                pnl_pct=return_pct,
                partial_size=take,
                new_stop=max(position.entry_price, current_price * 0.97),
            )

        # Tier 50%: keep a runner instead of closing everything
        if len(tiers) > 3 and return_pct >= tiers[3] and not position.tier_50_hit:
            keep_runner = position.initial_size * self.runner_fraction_at_final_tier
            keep_runner = min(keep_runner, position.remaining_size)
            take = max(position.remaining_size - keep_runner, 0.0)

            if take > 0:
                profit = take * (current_price - position.entry_price)
                position.realized_profit += profit
                position.remaining_size -= take

            position.tier_50_hit = True
            position.runner_mode = True
            position.trailing_stop_price = current_price * (1.0 - self.runner_trailing_distance_pct)

            return self._result(
                action="RUNNER_MODE",
                reason="tier 50% hit - runner activated",
                pnl_pct=return_pct,
                partial_size=take,
                new_stop=position.trailing_stop_price,
            )

        return self._result(
            action="HOLD",
            reason="no tier triggered",
            pnl_pct=return_pct,
        )

    def apply_stop_update(
        self,
        position: ManagedPosition,
        new_stop: float | None,
    ) -> None:
        if new_stop is None:
            return

        if new_stop > position.stop_loss_price:
            position.stop_loss_price = new_stop

        if position.runner_mode and new_stop > position.trailing_stop_price:
            position.trailing_stop_price = new_stop

    def _get_active_stop(self, position: ManagedPosition) -> float:
        if position.runner_mode and position.trailing_stop_price > 0:
            return max(position.stop_loss_price, position.trailing_stop_price)
        return position.stop_loss_price

    def calculate_redeployable_capital(self, position: ManagedPosition) -> float:
        return position.realized_profit * self.policy.max_reentry_fraction_of_realized_profit

    @staticmethod
    def _result(
        action: str,
        reason: str,
        pnl_pct: float,
        partial_size: float = 0.0,
        new_stop: float | None = None,
    ) -> Dict[str, Any]:
        return {
            "action": action,
            "reason": reason,
            "pnl_pct": pnl_pct,
            "partial_size": partial_size,
            "new_stop": new_stop,
        }


if __name__ == "__main__":
    pm = ProfitManager()
    pos = pm.create_position(symbol="TEST-USD", entry_price=100.0, size=10.0)

    prices = [102.0, 110.0, 121.0, 136.0, 151.0, 165.0, 155.0]

    print("\n=== UNIFIED PROFIT MANAGER TEST ===\n")
    print(get_policy_snapshot())

    for px in prices:
        result = pm.evaluate(pos, px)
        pm.apply_stop_update(pos, result.get("new_stop"))
        print(
            f"Price={px:.2f} | "
            f"Action={result['action']} | "
            f"Reason={result['reason']} | "
            f"Remaining={pos.remaining_size:.4f} | "
            f"Realized={pos.realized_profit:.2f} | "
            f"Stop={pos.stop_loss_price:.2f} | "
            f"RunnerStop={pos.trailing_stop_price:.2f}"
        )

    print(f"\nRedeployable capital = {pm.calculate_redeployable_capital(pos):.2f}")
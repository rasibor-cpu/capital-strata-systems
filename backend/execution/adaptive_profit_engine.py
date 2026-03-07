from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass
class ProfitSignal:
    asset: str
    strategy: str
    previous_price: float
    next_price: float
    action_note: str


class AdaptiveProfitEngine:
    """
    Phase 2 Adaptive Profit Engine

    Simulates strategy-aware price progression so open positions
    can be managed across engine cycles.
    """

    def __init__(self, seed: int | None = None) -> None:
        self.rng = random.Random(seed)

    def _trend_following_move(self, current_price: float) -> float:
        move_pct = self.rng.uniform(-0.004, 0.022)
        return round(current_price * (1.0 + move_pct), 4)

    def _mean_reversion_move(self, current_price: float, anchor_price: float = 100.0) -> float:
        gap = anchor_price - current_price
        bias_pct = gap / anchor_price * 0.35
        noise_pct = self.rng.uniform(-0.008, 0.008)
        move_pct = bias_pct + noise_pct
        return round(current_price * (1.0 + move_pct), 4)

    def _breakout_move(self, current_price: float) -> float:
        move_pct = self.rng.uniform(-0.03, 0.03)
        return round(current_price * (1.0 + move_pct), 4)

    def simulate_next_price(
        self,
        asset: str,
        strategy: str,
        current_price: float,
        anchor_price: float = 100.0,
    ) -> ProfitSignal:
        previous_price = round(current_price, 4)

        if strategy == "trend_following":
            next_price = self._trend_following_move(current_price)
            note = "trend continuation / shallow pullback"
        elif strategy == "vwap_mean_reversion":
            next_price = self._mean_reversion_move(current_price, anchor_price=anchor_price)
            note = "reversion toward fair value"
        elif strategy == "volatility_breakout":
            next_price = self._breakout_move(current_price)
            note = "wide breakout volatility"
        else:
            next_price = round(current_price, 4)
            note = "no strategy mapping"

        if next_price <= 0:
            next_price = round(max(1.0, current_price), 4)

        return ProfitSignal(
            asset=asset,
            strategy=strategy,
            previous_price=previous_price,
            next_price=next_price,
            action_note=note,
        )


def demo() -> None:
    engine = AdaptiveProfitEngine(seed=42)

    tests = [
        ("BTC-USD", "trend_following", 100.0),
        ("ETH-USD", "vwap_mean_reversion", 103.0),
        ("SOL-USD", "volatility_breakout", 100.0),
    ]

    print("\nCSS Adaptive Profit Engine Demo\n")

    for asset, strategy, price in tests:
        signal = engine.simulate_next_price(
            asset=asset,
            strategy=strategy,
            current_price=price,
            anchor_price=100.0,
        )
        print(
            f"{signal.asset:10} "
            f"strategy={signal.strategy:20} "
            f"prev={signal.previous_price:8.4f} "
            f"next={signal.next_price:8.4f} "
            f"note={signal.action_note}"
        )


if __name__ == "__main__":
    demo()
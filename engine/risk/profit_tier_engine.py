"""
Profit Tier Engine
REA Capital Trading Engine

Implements:
- 20% gain → take 50%
- 35% gain → take 50% of remainder
- 50% gain → close full position
- Banking logic: reinvest max 50% of realized profits
"""

from dataclasses import dataclass


@dataclass
class Position:
    initial_size: float
    remaining_size: float
    realized_profit: float = 0.0
    tier_20_hit: bool = False
    tier_35_hit: bool = False
    tier_50_hit: bool = False


def evaluate_profit_tiers(position: Position, return_pct: float) -> None:
    """
    return_pct is expressed as decimal (e.g., 0.20 = 20%)
    """

    unrealized = position.initial_size * return_pct

    # Tier 20%
    if return_pct >= 0.20 and not position.tier_20_hit:
        take = position.remaining_size * 0.50
        profit = take * return_pct
        position.realized_profit += profit
        position.remaining_size -= take
        position.tier_20_hit = True
        print(f"TIER 20% HIT | Took 50% | Realized {profit:.2f}")

    # Tier 35%
    if return_pct >= 0.35 and not position.tier_35_hit:
        take = position.remaining_size * 0.50
        profit = take * return_pct
        position.realized_profit += profit
        position.remaining_size -= take
        position.tier_35_hit = True
        print(f"TIER 35% HIT | Took 50% of remainder | Realized {profit:.2f}")

    # Tier 50%
    if return_pct >= 0.50 and not position.tier_50_hit:
        profit = position.remaining_size * return_pct
        position.realized_profit += profit
        position.remaining_size = 0
        position.tier_50_hit = True
        print(f"TIER 50% HIT | Closed full position | Realized {profit:.2f}")


def calculate_redeployable_capital(position: Position) -> float:
    """
    Only 50% of realized profit can be redeployed.
    """
    return position.realized_profit * 0.50

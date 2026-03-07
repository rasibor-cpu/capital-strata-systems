from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict


@dataclass
class Allocation:
    asset: str
    allocation_usd: float
    weight: float


class CapitalAllocator:
    """
    Phase 2 Capital Allocation Engine

    Allocates portfolio capital across assets
    based on ranking weights.
    """

    def __init__(self, total_capital: float = 200):

        self.total_capital = total_capital

    def allocate(self, ranked_assets: List[str]) -> List[Allocation]:

        allocations: List[Allocation] = []

        n = len(ranked_assets)

        if n == 0:
            return allocations

        # decreasing weights for higher ranked assets
        weights = [n - i for i in range(n)]

        total_weight = sum(weights)

        for i, asset in enumerate(ranked_assets):

            weight = weights[i] / total_weight

            capital = self.total_capital * weight

            allocations.append(
                Allocation(
                    asset=asset,
                    allocation_usd=round(capital, 2),
                    weight=round(weight, 3)
                )
            )

        return allocations


def demo():

    ranked_assets = [
        "BTC-USD",
        "ETH-USD",
        "SOL-USD",
        "EUR-USD",
        "GBP-USD"
    ]

    allocator = CapitalAllocator(total_capital=200)

    allocations = allocator.allocate(ranked_assets)

    print("\nCSS Capital Allocation\n")

    for a in allocations:

        print(
            f"{a.asset:10} "
            f"Capital:${a.allocation_usd:7} "
            f"Weight:{a.weight}"
        )


if __name__ == "__main__":

    demo()
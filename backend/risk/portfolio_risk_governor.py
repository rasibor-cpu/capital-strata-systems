from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Tuple


@dataclass
class RiskDecision:
    allowed: bool
    reason: str


class PortfolioRiskGovernor:
    """
    Phase 2 Portfolio Risk Governor

    Controls portfolio-level exposure before new positions are opened.
    """

    def __init__(
        self,
        max_open_positions: int = 5,
        max_asset_allocation_pct: float = 0.40,
        max_total_deployed_pct: float = 1.00,
        total_capital: float = 200.0,
    ) -> None:
        self.max_open_positions = max_open_positions
        self.max_asset_allocation_pct = max_asset_allocation_pct
        self.max_total_deployed_pct = max_total_deployed_pct
        self.total_capital = total_capital

    def current_open_count(self, open_positions: Dict[str, object]) -> int:
        return len(open_positions)

    def current_deployed_capital(
        self,
        open_positions: Dict[str, object],
    ) -> float:
        deployed = 0.0
        for pos in open_positions.values():
            entry_price = float(getattr(pos, "entry_price", 0.0))
            size = float(getattr(pos, "size", 0.0))
            deployed += entry_price * size
        return round(deployed, 2)

    def can_open_position(
        self,
        asset: str,
        proposed_allocation_usd: float,
        open_positions: Dict[str, object],
    ) -> RiskDecision:
        if asset in open_positions:
            return RiskDecision(
                allowed=False,
                reason=f"{asset}: blocked - position already open",
            )

        open_count = self.current_open_count(open_positions)
        if open_count >= self.max_open_positions:
            return RiskDecision(
                allowed=False,
                reason=(
                    f"{asset}: blocked - max open positions reached "
                    f"({self.max_open_positions})"
                ),
            )

        max_asset_usd = self.total_capital * self.max_asset_allocation_pct
        if proposed_allocation_usd > max_asset_usd:
            return RiskDecision(
                allowed=False,
                reason=(
                    f"{asset}: blocked - allocation ${proposed_allocation_usd:.2f} "
                    f"exceeds per-asset limit ${max_asset_usd:.2f}"
                ),
            )

        currently_deployed = self.current_deployed_capital(open_positions)
        max_total_deployed = self.total_capital * self.max_total_deployed_pct
        projected_total = currently_deployed + proposed_allocation_usd

        if projected_total > max_total_deployed:
            return RiskDecision(
                allowed=False,
                reason=(
                    f"{asset}: blocked - projected deployed capital "
                    f"${projected_total:.2f} exceeds portfolio cap "
                    f"${max_total_deployed:.2f}"
                ),
            )

        return RiskDecision(
            allowed=True,
            reason=f"{asset}: approved",
        )

    def review_batch(
        self,
        proposed_allocations: Iterable[Tuple[str, float]],
        open_positions: Dict[str, object],
    ) -> Dict[str, RiskDecision]:
        decisions: Dict[str, RiskDecision] = {}
        simulated_positions = dict(open_positions)

        for asset, allocation_usd in proposed_allocations:
            decision = self.can_open_position(
                asset=asset,
                proposed_allocation_usd=allocation_usd,
                open_positions=simulated_positions,
            )
            decisions[asset] = decision

            if decision.allowed:
                # reserve a placeholder so the next asset sees updated portfolio state
                simulated_positions[asset] = object()

        return decisions


def demo() -> None:
    governor = PortfolioRiskGovernor(
        max_open_positions=5,
        max_asset_allocation_pct=0.40,
        max_total_deployed_pct=1.00,
        total_capital=200.0,
    )

    open_positions: Dict[str, object] = {}

    proposed = [
        ("BTC-USD", 66.67),
        ("ETH-USD", 53.33),
        ("SOL-USD", 40.00),
        ("EUR-USD", 26.67),
        ("GBP-USD", 13.33),
        ("USD-JPY", 12.00),
    ]

    results = governor.review_batch(proposed, open_positions)

    print("\nCSS Portfolio Risk Governor Demo\n")
    for asset, decision in results.items():
        print(f"{asset:10} allowed={decision.allowed} reason={decision.reason}")


if __name__ == "__main__":
    demo()
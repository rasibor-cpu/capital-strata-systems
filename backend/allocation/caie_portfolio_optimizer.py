from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable, Mapping

from .caie_scoring_engine import CAIEScoringEngine
from .opportunity_proposal import OpportunityProposal


@dataclass(frozen=True)
class CAIEAllocation:
    proposal_id: str
    broker: str
    asset_class: str
    symbol: str
    score: Decimal
    requested_capital: Decimal
    allocated_capital: Decimal
    concentration_limited: bool


@dataclass(frozen=True)
class CAIEPortfolioPlan:
    allocations: tuple[CAIEAllocation, ...]
    deployed_capital: Decimal
    remaining_cash: Decimal
    status: str


class CAIEPortfolioOptimizer:
    """Shadow-only portfolio ranking and capital allocation planner."""

    @staticmethod
    def optimize(
        proposals: Iterable[OpportunityProposal],
        *,
        available_capital: Decimal,
        asset_class_caps: Mapping[str, Decimal],
        broker_caps: Mapping[str, Decimal],
        concentration_cap: Decimal = Decimal("0.25"),
    ) -> CAIEPortfolioPlan:
        if available_capital < 0:
            raise ValueError("available_capital must be non-negative")
        if not (Decimal("0") < concentration_cap <= Decimal("1")):
            raise ValueError("concentration_cap must be in (0, 1]")

        for name, caps in (("asset_class_caps", asset_class_caps), ("broker_caps", broker_caps)):
            for key, value in caps.items():
                if not key or not (Decimal("0") <= value <= Decimal("1")):
                    raise ValueError(f"{name} values must be in [0, 1]")

        scored: list[tuple[OpportunityProposal, Decimal]] = []
        for proposal in proposals:
            score = CAIEScoringEngine.score(proposal)
            scored.append((proposal, score.total_score))

        scored.sort(key=lambda item: item[1], reverse=True)

        remaining = available_capital
        deployed_by_asset: dict[str, Decimal] = {}
        deployed_by_broker: dict[str, Decimal] = {}
        allocations: list[CAIEAllocation] = []
        concentration_limit = available_capital * concentration_cap

        for proposal, score in scored:
            # Holding cash is explicitly permitted when no opportunity clears
            # a positive shadow score.
            if score <= 0 or remaining <= 0:
                continue

            asset_cap_fraction = asset_class_caps.get(proposal.asset_class, Decimal("0"))
            broker_cap_fraction = broker_caps.get(proposal.broker, Decimal("0"))

            asset_limit = available_capital * asset_cap_fraction
            broker_limit = available_capital * broker_cap_fraction

            asset_used = deployed_by_asset.get(proposal.asset_class, Decimal("0"))
            broker_used = deployed_by_broker.get(proposal.broker, Decimal("0"))

            asset_room = max(Decimal("0"), asset_limit - asset_used)
            broker_room = max(Decimal("0"), broker_limit - broker_used)

            requested = proposal.capital_required
            allocated = min(
                requested,
                remaining,
                concentration_limit,
                asset_room,
                broker_room,
            )
            if allocated <= 0:
                continue

            concentration_limited = allocated < requested and allocated == concentration_limit

            allocations.append(
                CAIEAllocation(
                    proposal_id=proposal.proposal_id,
                    broker=proposal.broker,
                    asset_class=proposal.asset_class,
                    symbol=proposal.symbol,
                    score=score,
                    requested_capital=requested,
                    allocated_capital=allocated,
                    concentration_limited=concentration_limited,
                )
            )

            deployed_by_asset[proposal.asset_class] = asset_used + allocated
            deployed_by_broker[proposal.broker] = broker_used + allocated
            remaining -= allocated

        deployed = available_capital - remaining
        return CAIEPortfolioPlan(
            allocations=tuple(allocations),
            deployed_capital=deployed,
            remaining_cash=remaining,
            status="SHADOW_ONLY",
        )

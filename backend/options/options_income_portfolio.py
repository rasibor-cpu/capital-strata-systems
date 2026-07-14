from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from backend.options.options_income_allocator import OptionsIncomeAllocator
from backend.options.options_income_constraints import OptionsIncomeConstraintConfig, OptionsIncomeConstraintEngine
from backend.options.options_income_diversification import OptionsIncomeDiversificationAnalyzer
from backend.options.options_income_laddering import OptionsIncomeLadderBuilder
from backend.options.options_income_rebalancer import OptionsIncomeRebalancer
from backend.options.options_income_targets import OptionsIncomeTargetCalculator
from backend.options.paper_position_repository import PaperIncomePosition, SAFE_FLAGS


class OptionsIncomePortfolioError(ValueError):
    """Raised when paper options income portfolio construction fails closed."""


@dataclass(frozen=True)
class OptionsIncomePortfolio:
    portfolio_id: str
    allocations: list[dict[str, Any]]
    capital: dict[str, Any]
    diversification: dict[str, Any]
    ladder: dict[str, Any]
    income_targets: dict[str, Any]
    rebalance: dict[str, Any]
    blockers: list[str]
    advisory_only: bool = True
    execution_allowed: bool = False
    live_trading_blocked: bool = True
    broker_execution_armed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "portfolio_id": self.portfolio_id,
            "allocations": self.allocations,
            "capital": self.capital,
            "diversification": self.diversification,
            "ladder": self.ladder,
            "income_targets": self.income_targets,
            "rebalance": self.rebalance,
            "blockers": self.blockers,
            **SAFE_FLAGS,
        }


class OptionsIncomePortfolioConstructor:
    def __init__(
        self,
        *,
        constraint_config: OptionsIncomeConstraintConfig | None = None,
        allocator: OptionsIncomeAllocator | None = None,
        diversification: OptionsIncomeDiversificationAnalyzer | None = None,
        laddering: OptionsIncomeLadderBuilder | None = None,
        targets: OptionsIncomeTargetCalculator | None = None,
        rebalancer: OptionsIncomeRebalancer | None = None,
    ) -> None:
        constraints = OptionsIncomeConstraintEngine(constraint_config)
        self.allocator = allocator or OptionsIncomeAllocator(constraints)
        self.diversification = diversification or OptionsIncomeDiversificationAnalyzer()
        self.laddering = laddering or OptionsIncomeLadderBuilder()
        self.targets = targets or OptionsIncomeTargetCalculator()
        self.rebalancer = rebalancer or OptionsIncomeRebalancer()

    def construct(
        self,
        *,
        portfolio_id: str,
        total_capital: float,
        opportunities: Sequence[Any] | None = None,
        existing_positions: Sequence[PaperIncomePosition] | None = None,
        sector_by_underlying: Mapping[str, str] | None = None,
        annual_target_yield: float = 0.12,
    ) -> OptionsIncomePortfolio:
        name = str(portfolio_id or "").strip()
        if not name:
            raise OptionsIncomePortfolioError("portfolio_id is required")
        allocation = self.allocator.allocate(
            total_capital=total_capital,
            opportunities=opportunities,
            existing_positions=existing_positions,
            sector_by_underlying=sector_by_underlying,
        )
        allocation_payload = allocation.to_dict()
        allocations = list(allocation_payload["allocations"])
        diversification = self.diversification.analyze(allocations, sector_by_underlying=sector_by_underlying).to_dict()
        ladder = self.laddering.build(allocations).to_dict()
        targets = self.targets.calculate(allocations, total_capital=total_capital, annual_target_yield=annual_target_yield).to_dict()
        rebalance = self.rebalancer.recommend(
            allocation=allocation_payload,
            diversification=diversification,
            ladder=ladder,
            targets=targets,
        ).to_dict()
        capital = {
            "allocated_capital": allocation.allocated_capital,
            "available_capital": allocation.available_capital,
            "reserved_collateral": allocation.reserved_collateral,
            "utilized_collateral": allocation.utilized_collateral,
            "unused_collateral": allocation.unused_collateral,
            "portfolio_utilization": allocation.portfolio_utilization,
            **SAFE_FLAGS,
        }
        return OptionsIncomePortfolio(
            portfolio_id=name,
            allocations=allocations,
            capital=capital,
            diversification=diversification,
            ladder=ladder,
            income_targets=targets,
            rebalance=rebalance,
            blockers=allocation.blockers,
        )


__all__ = ["OptionsIncomePortfolio", "OptionsIncomePortfolioConstructor", "OptionsIncomePortfolioError"]

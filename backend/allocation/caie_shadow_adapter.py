from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable, Mapping

from .caie_portfolio_optimizer import CAIEPortfolioOptimizer, CAIEPortfolioPlan
from .opportunity_proposal import OpportunityProposal


@dataclass(frozen=True)
class CAIEShadowResult:
    status: str
    reason: str
    plan: CAIEPortfolioPlan | None
    execution_allowed: bool = False
    broker_execution_armed: bool = False


class CAIEShadowAdapter:
    """Fail-safe advisory adapter invoked only after existing eligibility checks."""

    @staticmethod
    def evaluate(
        proposals: Iterable[OpportunityProposal],
        *,
        trade_eligible: bool,
        available_capital: Decimal,
        asset_class_caps: Mapping[str, Decimal],
        broker_caps: Mapping[str, Decimal],
        concentration_cap: Decimal = Decimal("0.25"),
    ) -> CAIEShadowResult:
        if not trade_eligible:
            return CAIEShadowResult(
                status="NOT_ELIGIBLE",
                reason="CANONICAL_ELIGIBILITY_NOT_MET",
                plan=None,
            )

        proposals = tuple(proposals)
        if not proposals:
            return CAIEShadowResult(
                status="NO_OPPORTUNITIES",
                reason="NO_CAIE_OPPORTUNITIES",
                plan=CAIEPortfolioOptimizer.optimize(
                    (),
                    available_capital=available_capital,
                    asset_class_caps=asset_class_caps,
                    broker_caps=broker_caps,
                    concentration_cap=concentration_cap,
                ),
            )

        try:
            plan = CAIEPortfolioOptimizer.optimize(
                proposals,
                available_capital=available_capital,
                asset_class_caps=asset_class_caps,
                broker_caps=broker_caps,
                concentration_cap=concentration_cap,
            )
        except Exception as exc:
            return CAIEShadowResult(
                status="UNAVAILABLE",
                reason=f"CAIE_SHADOW_ERROR:{type(exc).__name__}",
                plan=None,
            )

        return CAIEShadowResult(
            status="AVAILABLE",
            reason="CAIE_SHADOW_PLAN_READY",
            plan=plan,
        )

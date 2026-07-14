from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from backend.options.paper_position_repository import SAFE_FLAGS


@dataclass(frozen=True)
class PortfolioRebalanceRecommendation:
    action: str
    reason: str
    confidence: float
    advisory_only: bool = True
    execution_allowed: bool = False
    live_trading_blocked: bool = True
    broker_execution_armed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "reason": self.reason,
            "confidence": self.confidence,
            **SAFE_FLAGS,
        }


class OptionsIncomeRebalancer:
    def recommend(
        self,
        *,
        allocation: Mapping[str, Any],
        diversification: Mapping[str, Any],
        ladder: Mapping[str, Any],
        targets: Mapping[str, Any],
    ) -> PortfolioRebalanceRecommendation:
        utilization = float(allocation.get("portfolio_utilization", 0.0) or 0.0)
        expected = float(targets.get("expected_premium", 0.0) or 0.0)
        monthly_target = float(targets.get("monthly_premium_target", 0.0) or 0.0)
        diversification_score = float(diversification.get("diversification_score", 0.0) or 0.0)
        ladder_score = float(ladder.get("ladder_quality_score", 0.0) or 0.0)
        blockers = list(allocation.get("blockers", []) or [])
        if blockers:
            return PortfolioRebalanceRecommendation("Replace Opportunity", "Allocation blockers require replacing rejected opportunities.", 0.82)
        if utilization < 0.35 and expected < monthly_target:
            return PortfolioRebalanceRecommendation("Increase Allocation", "Portfolio utilization and expected premium are below target.", 0.78)
        if utilization > 0.85 or diversification_score < 55.0:
            return PortfolioRebalanceRecommendation("Reduce Allocation", "Portfolio utilization or concentration is above advisory comfort range.", 0.76)
        if ladder_score < 50.0:
            return PortfolioRebalanceRecommendation("Roll Portfolio", "Expiry ladder quality is weak and should be refreshed.", 0.70)
        return PortfolioRebalanceRecommendation("Maintain Portfolio", "Portfolio is within paper allocation, diversification, and income target ranges.", 0.88)


__all__ = ["OptionsIncomeRebalancer", "PortfolioRebalanceRecommendation"]

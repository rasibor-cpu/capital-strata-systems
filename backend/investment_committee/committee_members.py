from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.investment_committee.committee_models import (
    ABSTAIN,
    APPROVE,
    APPROVE_WITH_CAUTION,
    CommitteeOpportunity,
    CommitteeVote,
    LIQUIDITY_VETO,
    OPERATIONAL_VETO,
    PORTFOLIO_VETO,
    REJECT,
    RISK_VETO,
    WAIT,
)


class AdvisoryCommitteeMember:
    name = "Committee"
    veto = ""

    def evaluate(self, opportunity: CommitteeOpportunity, *, context: Mapping[str, Any] | None = None) -> CommitteeVote:
        score, factors = self._score(opportunity, dict(context or {}))
        vote = self._vote(score)
        veto = self.veto if vote == REJECT and self.veto else ""
        return CommitteeVote(
            committee=self.name,
            vote=vote,
            confidence=round(score / 100.0, 6),
            committee_score=round(score, 6),
            reason=self._reason(opportunity, vote, score, factors),
            strengths=[key for key, value in factors.items() if value >= 75.0],
            weaknesses=[key for key, value in factors.items() if value < 45.0],
            veto=veto,
        )

    def _score(self, opportunity: CommitteeOpportunity, context: Mapping[str, Any]) -> tuple[float, dict[str, float]]:
        return 0.0, {}

    def _vote(self, score: float) -> str:
        if score >= 75.0:
            return APPROVE
        if score >= 62.0:
            return APPROVE_WITH_CAUTION
        if score >= 45.0:
            return WAIT
        return REJECT

    def _reason(
        self,
        opportunity: CommitteeOpportunity,
        vote: str,
        score: float,
        factors: Mapping[str, float],
    ) -> str:
        weak = ", ".join(key for key, value in factors.items() if value < 45.0) or "none"
        strong = ", ".join(key for key, value in factors.items() if value >= 75.0) or "none"
        return f"{self.name} voted {vote} for {opportunity.symbol}; score={score:.1f}; strengths={strong}; weaknesses={weak}."


class MarketCommittee(AdvisoryCommitteeMember):
    name = "Market Committee"

    def _score(self, opportunity: CommitteeOpportunity, context: Mapping[str, Any]) -> tuple[float, dict[str, float]]:
        factors = {
            "trend": _score(opportunity.regime_suitability),
            "momentum": _score(_first_ratio(opportunity.raw, "momentum", "momentum_score", default=opportunity.signal_quality)),
            "volatility": _inverse_score(opportunity.volatility),
            "market_structure": _score(opportunity.market_health),
        }
        return _weighted_average(factors), factors


class RiskCommittee(AdvisoryCommitteeMember):
    name = "Risk Committee"
    veto = RISK_VETO

    def _score(self, opportunity: CommitteeOpportunity, context: Mapping[str, Any]) -> tuple[float, dict[str, float]]:
        max_drawdown = float(context.get("max_expected_drawdown", 0.08) or 0.08)
        max_budget = float(context.get("max_risk_budget_consumption", 0.35) or 0.35)
        drawdown = max(0.0, 1.0 - min(1.0, opportunity.expected_drawdown / max(max_drawdown, 0.0001)))
        budget = max(0.0, 1.0 - min(1.0, opportunity.risk_budget_consumption / max(max_budget, 0.0001)))
        factors = {
            "expected_drawdown": _score(drawdown),
            "probability": _score(opportunity.probability_of_success),
            "stop_distance": _inverse_score(_first_ratio(opportunity.raw, "stop_distance", "stop_distance_pct", default=0.20)),
            "portfolio_risk": _score(budget),
            "regime_risk": _score(opportunity.regime_suitability),
        }
        return _weighted_average(factors), factors


class CapitalCommittee(AdvisoryCommitteeMember):
    name = "Capital Committee"

    def _score(self, opportunity: CommitteeOpportunity, context: Mapping[str, Any]) -> tuple[float, dict[str, float]]:
        deployable = float(context.get("deployable_capital", 0.0) or 0.0)
        request_fit = 1.0 if deployable <= 0.0 else max(0.0, 1.0 - min(1.0, opportunity.requested_capital / max(deployable, 1.0)))
        factors = {
            "capital_efficiency": _score(opportunity.capital_efficiency),
            "opportunity_cost": _score(max(opportunity.expected_return, 0.0) / 0.04),
            "capital_allocation": _score(request_fit),
            "replacement_opportunities": _score(_first_ratio(opportunity.raw, "replacement_score", default=opportunity.capital_efficiency)),
        }
        return _weighted_average(factors), factors


class PortfolioCommittee(AdvisoryCommitteeMember):
    name = "Portfolio Committee"
    veto = PORTFOLIO_VETO

    def _score(self, opportunity: CommitteeOpportunity, context: Mapping[str, Any]) -> tuple[float, dict[str, float]]:
        max_sector = float(context.get("max_sector_concentration", 0.40) or 0.40)
        max_corr = float(context.get("max_portfolio_correlation", 0.75) or 0.75)
        concentration = max(0.0, 1.0 - min(1.0, opportunity.sector_concentration / max(max_sector, 0.0001)))
        correlation = max(0.0, 1.0 - min(1.0, opportunity.portfolio_correlation / max(max_corr, 0.0001)))
        factors = {
            "diversification": _score(opportunity.asset_allocation_impact),
            "concentration": _score(concentration),
            "correlation": _score(correlation),
            "sector_exposure": _score(concentration),
            "asset_allocation": _score(opportunity.asset_allocation_impact),
        }
        return _weighted_average(factors), factors


class LiquidityCommittee(AdvisoryCommitteeMember):
    name = "Liquidity Committee"
    veto = LIQUIDITY_VETO

    def _score(self, opportunity: CommitteeOpportunity, context: Mapping[str, Any]) -> tuple[float, dict[str, float]]:
        factors = {
            "spread": _score(opportunity.spread_quality),
            "liquidity": _score(opportunity.liquidity),
            "execution_quality": _inverse_score(opportunity.execution_cost),
            "slippage_risk": _inverse_score(_first_ratio(opportunity.raw, "slippage_risk", "slippage_bps", default=opportunity.execution_cost)),
        }
        return _weighted_average(factors), factors


class OperationalCommittee(AdvisoryCommitteeMember):
    name = "Operational Committee"
    veto = OPERATIONAL_VETO

    def _score(self, opportunity: CommitteeOpportunity, context: Mapping[str, Any]) -> tuple[float, dict[str, float]]:
        freshness = _first_ratio(opportunity.raw, "market_data_freshness", "market_data_freshness_score", default=opportunity.market_health)
        certification = _first_ratio(opportunity.raw, "operational_certification", "broker_certification", default=opportunity.operational_readiness)
        factors = {
            "runtime_health": _score(_first_ratio(opportunity.raw, "runtime_health", default=opportunity.operational_readiness)),
            "broker_readiness": _score(opportunity.operational_readiness),
            "market_data_freshness": _score(freshness),
            "operational_certification": _score(certification),
        }
        return _weighted_average(factors), factors


def default_committee_members() -> list[AdvisoryCommitteeMember]:
    return [
        MarketCommittee(),
        RiskCommittee(),
        CapitalCommittee(),
        PortfolioCommittee(),
        LiquidityCommittee(),
        OperationalCommittee(),
    ]


def _weighted_average(factors: Mapping[str, float]) -> float:
    return round(sum(float(value) for value in factors.values()) / max(len(factors), 1), 6)


def _score(value: float) -> float:
    return max(0.0, min(100.0, float(value) * 100.0))


def _inverse_score(value: float) -> float:
    return _score(1.0 - max(0.0, min(1.0, float(value))))


def _first_ratio(source: Mapping[str, Any], *keys: str, default: Any = 0.5) -> float:
    for key in keys:
        if key in source and source[key] not in (None, ""):
            return _ratio(source[key])
    return _ratio(default)


def _ratio(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    if abs(number) > 1.0:
        number /= 100.0
    return max(0.0, min(1.0, number))


__all__ = [
    "AdvisoryCommitteeMember",
    "CapitalCommittee",
    "LiquidityCommittee",
    "MarketCommittee",
    "OperationalCommittee",
    "PortfolioCommittee",
    "RiskCommittee",
    "default_committee_members",
]

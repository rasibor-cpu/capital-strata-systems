from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.investment_committee.committee_models import (
    CommitteeOpportunity,
    CommitteeScorecard,
    INSUFFICIENT_EDGE,
    PORTFOLIO_CONFLICT,
    RISK_LIMIT_EXCEEDED,
)


DIMENSION_WEIGHTS = {
    "expected_return": 0.10,
    "probability_of_success": 0.08,
    "expected_drawdown": 0.07,
    "expected_holding_period": 0.03,
    "capital_efficiency": 0.08,
    "portfolio_correlation": 0.06,
    "sector_concentration": 0.05,
    "asset_allocation_impact": 0.04,
    "regime_suitability": 0.06,
    "liquidity": 0.05,
    "spread_quality": 0.04,
    "execution_cost": 0.04,
    "volatility": 0.04,
    "risk_budget_consumption": 0.06,
    "strategy_confidence": 0.06,
    "signal_quality": 0.05,
    "historical_similarity": 0.04,
    "decision_confidence": 0.06,
    "operational_readiness": 0.05,
    "market_health": 0.04,
}


class CommitteeScorecardEngine:
    """Institutional advisory scorecard for one candidate trade."""

    def score(
        self,
        opportunity: CommitteeOpportunity,
        *,
        portfolio_context: Mapping[str, Any] | None = None,
    ) -> CommitteeScorecard:
        ctx = dict(portfolio_context or {})
        dimensions = {
            "expected_return": _return_score(opportunity.expected_return),
            "probability_of_success": _ratio_score(opportunity.probability_of_success),
            "expected_drawdown": _inverse_ratio_score(opportunity.expected_drawdown),
            "expected_holding_period": _holding_period_score(opportunity.expected_holding_period),
            "capital_efficiency": _ratio_score(opportunity.capital_efficiency),
            "portfolio_correlation": _inverse_ratio_score(opportunity.portfolio_correlation),
            "sector_concentration": _inverse_ratio_score(opportunity.sector_concentration),
            "asset_allocation_impact": _ratio_score(opportunity.asset_allocation_impact),
            "regime_suitability": _ratio_score(opportunity.regime_suitability),
            "liquidity": _ratio_score(opportunity.liquidity),
            "spread_quality": _ratio_score(opportunity.spread_quality),
            "execution_cost": _inverse_ratio_score(opportunity.execution_cost),
            "volatility": _volatility_score(opportunity.volatility),
            "risk_budget_consumption": _inverse_ratio_score(opportunity.risk_budget_consumption),
            "strategy_confidence": _ratio_score(opportunity.strategy_confidence),
            "signal_quality": _ratio_score(opportunity.signal_quality),
            "historical_similarity": _ratio_score(opportunity.historical_similarity),
            "decision_confidence": _ratio_score(opportunity.decision_confidence),
            "operational_readiness": _ratio_score(opportunity.operational_readiness),
            "market_health": _ratio_score(opportunity.market_health),
        }
        score = round(sum(dimensions[key] * DIMENSION_WEIGHTS[key] for key in DIMENSION_WEIGHTS), 6)
        blockers = self._blockers(opportunity, dimensions, ctx)
        if blockers:
            score = min(score, 55.0)
        strengths = _labels(dimensions, minimum=78.0)
        weaknesses = _labels(dimensions, maximum=45.0)
        return CommitteeScorecard(
            committee_score=round(score, 6),
            dimensions={key: round(value, 6) for key, value in dimensions.items()},
            blockers=blockers,
            strengths=strengths,
            weaknesses=weaknesses,
        )

    @staticmethod
    def _blockers(
        opportunity: CommitteeOpportunity,
        dimensions: Mapping[str, float],
        context: Mapping[str, Any],
    ) -> list[str]:
        blockers: list[str] = []
        if opportunity.expected_return <= 0.0 or dimensions["expected_return"] < 35.0:
            blockers.append(INSUFFICIENT_EDGE)
        if opportunity.expected_drawdown > float(context.get("max_expected_drawdown", 0.08)):
            blockers.append(RISK_LIMIT_EXCEEDED)
        if opportunity.risk_budget_consumption > float(context.get("max_risk_budget_consumption", 0.35)):
            blockers.append(RISK_LIMIT_EXCEEDED)
        if opportunity.portfolio_correlation > float(context.get("max_portfolio_correlation", 0.75)):
            blockers.append(PORTFOLIO_CONFLICT)
        if opportunity.sector_concentration > float(context.get("max_sector_concentration", 0.40)):
            blockers.append(PORTFOLIO_CONFLICT)
        if opportunity.operational_readiness <= 0.0:
            blockers.append("OPERATIONAL_READINESS_BLOCKED")
        return sorted(dict.fromkeys(blockers))


def normalize_opportunity(
    row: Mapping[str, Any],
    *,
    index: int,
    portfolio_context: Mapping[str, Any] | None = None,
) -> CommitteeOpportunity:
    if not isinstance(row, Mapping):
        raise ValueError("committee opportunity rows must be mappings")
    ctx = dict(portfolio_context or {})
    symbol = str(_first(row, "symbol", "asset", default="UNKNOWN")).upper()
    asset_class = str(_first(row, "asset_class", default="UNKNOWN")).upper()
    sector = str(_first(row, "sector", default=asset_class)).upper()
    expected_return = _number(_first(row, "expected_return", "expected_reward", "expected_value", "edge", default=0.0))
    requested_capital = max(0.0, _number(_first(row, "requested_capital", "capital_request", "capital_at_risk", default=0.0)))
    capital_efficiency = _ratio(_first(row, "capital_efficiency", default=None))
    if capital_efficiency == 0.0 and requested_capital > 0.0:
        capital_efficiency = _clamp01(max(expected_return, 0.0) / requested_capital)
    return CommitteeOpportunity(
        opportunity_id=str(_first(row, "opportunity_id", "proposal_id", "trade_id", default=f"{symbol}:{index}")),
        symbol=symbol,
        asset_class=asset_class,
        sector=sector,
        strategy=str(_first(row, "strategy", "strategy_id", default="UNKNOWN")),
        broker=str(_first(row, "broker", "broker_name", default="UNKNOWN")).upper(),
        requested_capital=requested_capital,
        expected_return=expected_return,
        probability_of_success=_ratio(_first(row, "probability_of_success", "probability", "prob", default=0.5)),
        expected_drawdown=_ratio(_first(row, "expected_drawdown", "drawdown", "expected_risk", default=0.02)),
        expected_holding_period=max(0.0, _number(_first(row, "expected_holding_period", "holding_period", default=1.0))),
        capital_efficiency=capital_efficiency,
        portfolio_correlation=_ratio(_first(row, "portfolio_correlation", "correlation", default=0.35)),
        sector_concentration=_ratio(_first(row, "sector_concentration", default=_sector_concentration(ctx, sector, requested_capital))),
        asset_allocation_impact=_ratio(_first(row, "asset_allocation_impact", "diversification_benefit", "portfolio_diversification_benefit", default=0.55)),
        regime_suitability=_ratio(_first(row, "regime_suitability", "regime_alignment", "regime_match", default=0.60)),
        liquidity=_ratio(_first(row, "liquidity", "liquidity_score", default=0.60)),
        spread_quality=_ratio(_first(row, "spread_quality", "spread_score", default=0.70)),
        execution_cost=_ratio(_first(row, "execution_cost", "cost", "slippage_bps", default=0.05)),
        volatility=_ratio(_first(row, "volatility", "volatility_score", default=0.30)),
        risk_budget_consumption=_ratio(_first(row, "risk_budget_consumption", "risk_budget", default=0.15)),
        strategy_confidence=_ratio(_first(row, "strategy_confidence", "confidence", default=0.55)),
        signal_quality=_ratio(_first(row, "signal_quality", default=0.55)),
        historical_similarity=_ratio(_first(row, "historical_similarity", "historical_performance", "historical_reliability", default=0.55)),
        decision_confidence=_ratio(_first(row, "decision_confidence", "confidence", default=0.55)),
        operational_readiness=_ratio(_first(row, "operational_readiness", default=ctx.get("operational_readiness", 0.65))),
        market_health=_ratio(_first(row, "market_health", default=ctx.get("market_health", 0.60))),
        raw=dict(row),
    )


def _sector_concentration(context: Mapping[str, Any], sector: str, requested_capital: float) -> float:
    equity = max(_number(context.get("equity")), 1.0)
    exposure = _number(dict(context.get("exposure_by_sector", {})).get(sector, 0.0))
    return _clamp01((exposure + requested_capital) / equity)


def _return_score(value: float) -> float:
    return _clamp01(value / 0.04) * 100.0


def _holding_period_score(value: float) -> float:
    if value <= 0:
        return 40.0
    if value <= 5:
        return 100.0
    if value <= 20:
        return 80.0
    return 60.0


def _volatility_score(value: float) -> float:
    if value <= 0.0:
        return 50.0
    if value <= 0.35:
        return 100.0
    if value <= 0.70:
        return 70.0
    return 40.0


def _ratio_score(value: float) -> float:
    return _clamp01(value) * 100.0


def _inverse_ratio_score(value: float) -> float:
    return (1.0 - _clamp01(value)) * 100.0


def _labels(dimensions: Mapping[str, float], *, minimum: float | None = None, maximum: float | None = None) -> list[str]:
    rows = []
    for key, value in dimensions.items():
        if minimum is not None and value >= minimum:
            rows.append(key)
        elif maximum is not None and value <= maximum:
            rows.append(key)
    return rows


def _first(source: Mapping[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        value = source.get(key)
        if value not in (None, ""):
            return value
    return default


def _number(value: Any, *, default: float = 0.0) -> float:
    try:
        if value is None or isinstance(value, bool):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _ratio(value: Any) -> float:
    numeric = _number(value)
    if abs(numeric) > 1.0:
        numeric /= 100.0
    return _clamp01(numeric)


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))

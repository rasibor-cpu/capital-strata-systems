from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping


class OpportunityIntelligenceEngineError(ValueError):
    """Fail-closed exception for opportunity intelligence inputs."""


class ExpectedValueEngine:
    """Deterministic advisory expected-value model for validated opportunities."""

    def evaluate(
        self,
        opportunity: Mapping[str, Any],
        *,
        context: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not isinstance(opportunity, Mapping):
            raise OpportunityIntelligenceEngineError("opportunity must be a Mapping")
        ctx = _mapping(context)

        probability = _ratio(_first(opportunity, "probability", "prob", default=0.5))
        confidence = _ratio(_first(opportunity, "confidence", default=probability))
        historical = _ratio(_first(opportunity, "historical_performance", "historical_reliability", "win_rate", default=0.5))
        confidence_calibration = _ratio(_first(opportunity, "confidence_calibration", default=1.0 - abs(confidence - historical)))
        execution_quality = _ratio(_first(opportunity, "execution_quality", default=ctx.get("execution_quality", 0.7)))
        broker_intelligence = _ratio(_first(opportunity, "broker_performance", "broker_score", default=ctx.get("broker_performance", 0.7)))
        regime_alignment = _ratio(_first(opportunity, "regime_alignment", "regime_match", default=ctx.get("regime_alignment", 0.6)))
        liquidity = _ratio(_first(opportunity, "liquidity", "liquidity_score", default=ctx.get("liquidity_score", 0.6)))
        slippage = _ratio(_first(opportunity, "slippage_adjustment", "slippage_bps", default=ctx.get("slippage_bps", 0.0)), scale=25.0)
        volatility = _ratio(_first(opportunity, "volatility", "volatility_score", default=0.25))

        expected_reward = _number(_first(opportunity, "expected_reward", "reward", "expected_upside", default=0.0))
        expected_risk = abs(_number(_first(opportunity, "expected_risk", "risk", "expected_downside", default=0.0)))
        if expected_reward == 0.0 and "expected_value" in opportunity:
            expected_reward = max(0.0, _number(opportunity.get("expected_value")))
        if expected_risk == 0.0:
            expected_risk = max(1.0, abs(expected_reward) * 0.35)

        downside_penalty = abs(_number(_first(opportunity, "downside_penalty", default=expected_risk * volatility)))
        quality_multiplier = _clamp01(
            (
                historical
                + confidence_calibration
                + execution_quality
                + broker_intelligence
                + regime_alignment
                + liquidity
            )
            / 6.0
        )
        slippage_penalty = expected_reward * min(0.5, slippage * 0.2)
        expected_value = (
            (expected_reward * probability * quality_multiplier)
            - (expected_risk * (1.0 - probability))
            - downside_penalty
            - slippage_penalty
        )
        expected_drawdown = _clamp01((expected_risk + downside_penalty) / max(expected_reward + expected_risk, 1.0))
        risk_adjusted_return = expected_value / max(expected_risk + downside_penalty, 1.0)
        confidence_adjusted_ev = expected_value * confidence * confidence_calibration

        return {
            "expected_value": round(expected_value, 6),
            "risk_adjusted_return": round(risk_adjusted_return, 6),
            "expected_drawdown": round(expected_drawdown, 6),
            "confidence_adjusted_ev": round(confidence_adjusted_ev, 6),
            "inputs": {
                "probability": round(probability, 6),
                "confidence": round(confidence, 6),
                "historical_performance": round(historical, 6),
                "confidence_calibration": round(confidence_calibration, 6),
                "execution_quality": round(execution_quality, 6),
                "broker_intelligence": round(broker_intelligence, 6),
                "regime_alignment": round(regime_alignment, 6),
                "liquidity_adjustment": round(liquidity, 6),
                "slippage_adjustment": round(slippage, 6),
                "downside_penalty": round(downside_penalty, 6),
            },
            "advisory_only": True,
            "execution_allowed": False,
        }


class RiskAdjustedOpportunityScoringEngine:
    """Unified advisory score combining EV, confidence, broker and capital signals."""

    def __init__(self, expected_value_engine: ExpectedValueEngine | None = None) -> None:
        self.expected_value_engine = expected_value_engine or ExpectedValueEngine()

    def score(
        self,
        opportunity: Mapping[str, Any],
        *,
        context: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        ev = self.expected_value_engine.evaluate(opportunity, context=context)
        ctx = _mapping(context)
        expected_reward = abs(_number(_first(opportunity, "expected_reward", "reward", "expected_upside", "requested_capital", default=100.0)))
        ev_score = _score_signed(ev["confidence_adjusted_ev"], scale=max(expected_reward, 1.0))
        confidence_score = _ratio(_first(opportunity, "confidence", default=0.5)) * 100.0
        broker_score = _ratio(_first(opportunity, "broker_performance", "broker_score", default=ctx.get("broker_performance", 0.7))) * 100.0
        execution_score = _ratio(_first(opportunity, "execution_quality", default=ctx.get("execution_quality", 0.7))) * 100.0
        regime_score = _ratio(_first(opportunity, "regime_alignment", "regime_match", default=ctx.get("regime_alignment", 0.6))) * 100.0
        liquidity_score = _ratio(_first(opportunity, "liquidity", "liquidity_score", default=ctx.get("liquidity_score", 0.6))) * 100.0
        diversification_score = _ratio(_first(opportunity, "portfolio_diversification_benefit", "diversification_benefit", default=0.5)) * 100.0
        capital_efficiency_score = _capital_efficiency(opportunity)
        historical_score = _ratio(_first(opportunity, "historical_performance", "historical_reliability", "win_rate", default=0.5)) * 100.0

        breakdown = {
            "expected_value": ev_score,
            "decision_confidence": confidence_score,
            "broker_performance": broker_score,
            "execution_quality": execution_score,
            "regime_match": regime_score,
            "liquidity": liquidity_score,
            "diversification": diversification_score,
            "capital_efficiency": capital_efficiency_score,
            "historical_reliability": historical_score,
        }
        weights = {
            "expected_value": 0.22,
            "decision_confidence": 0.12,
            "broker_performance": 0.10,
            "execution_quality": 0.10,
            "regime_match": 0.10,
            "liquidity": 0.09,
            "diversification": 0.08,
            "capital_efficiency": 0.10,
            "historical_reliability": 0.09,
        }
        overall = round(sum(breakdown[key] * weights[key] for key in weights), 6)
        blockers = _safety_blockers(opportunity)
        if blockers:
            overall = min(overall, 35.0)
        status = _status(overall)
        recommendation = _recommendation(status, blockers)

        return {
            "overall_score": overall,
            "score_breakdown": {key: round(value, 6) for key, value in sorted(breakdown.items())},
            "expected_value": ev,
            "status": status,
            "recommendation": recommendation,
            "warnings": blockers,
            "explanation": _score_explanation(opportunity, overall, status, recommendation),
            "advisory_only": True,
            "execution_allowed": False,
            "live_trading_enabled": False,
        }


class OpportunityIntelligenceEngine:
    """Advisory-only opportunity intelligence and leaderboard generation."""

    def __init__(
        self,
        scoring_engine: RiskAdjustedOpportunityScoringEngine | None = None,
    ) -> None:
        self.scoring_engine = scoring_engine or RiskAdjustedOpportunityScoringEngine()

    def evaluate(
        self,
        opportunities: list[Mapping[str, Any]] | None,
        *,
        context: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        if opportunities is None:
            rows: list[Mapping[str, Any]] = []
        elif isinstance(opportunities, list):
            rows = opportunities
        else:
            raise OpportunityIntelligenceEngineError("opportunities must be a list")

        evaluated: list[dict[str, Any]] = []
        for index, row in enumerate(rows):
            if not isinstance(row, Mapping):
                raise OpportunityIntelligenceEngineError("opportunity rows must be mappings")
            if not _eligible(row):
                continue
            scored = self._evaluate_one(row, rank=0, input_order=index, context=context)
            evaluated.append(scored)

        evaluated.sort(
            key=lambda item: (
                -float(item["opportunity_score"]),
                str(item["asset"]),
                str(item["strategy"]),
                int(item["_input_order"]),
            )
        )
        for rank, item in enumerate(evaluated, start=1):
            item["rank"] = rank
            item.pop("_input_order", None)

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "advisory_only": True,
            "execution_allowed": False,
            "live_trading_enabled": False,
            "opportunities": evaluated,
            "leaderboard": [_leaderboard_row(item) for item in evaluated],
        }

    def _evaluate_one(
        self,
        opportunity: Mapping[str, Any],
        *,
        rank: int,
        input_order: int,
        context: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        score = self.scoring_engine.score(opportunity, context=context)
        asset = str(_first(opportunity, "asset", "symbol", default="UNKNOWN")).upper()
        asset_class = str(_first(opportunity, "asset_class", default="UNKNOWN")).upper()
        strategy = str(_first(opportunity, "strategy", "strategy_id", default="UNKNOWN"))
        broker = str(_first(opportunity, "broker", "broker_name", default=_mapping(context).get("broker", "UNKNOWN"))).upper()
        strengths, weaknesses, supporting = _explain_factors(score["score_breakdown"])
        warnings = sorted(dict.fromkeys(list(score["warnings"]) + _opportunity_warnings(opportunity, score)))
        return {
            "opportunity_id": str(_first(opportunity, "opportunity_id", "proposal_id", "trade_id", default=f"{asset}:{strategy}:{broker}")),
            "asset": asset,
            "asset_class": asset_class,
            "broker": broker,
            "strategy": strategy,
            "regime": str(_first(opportunity, "regime", "market_regime", default="UNKNOWN")),
            "opportunity_score": score["overall_score"],
            "rank": rank,
            "status": score["status"],
            "strengths": strengths,
            "weaknesses": weaknesses,
            "supporting_factors": supporting,
            "warnings": warnings,
            "explanation": score["explanation"],
            "expected_value": score["expected_value"]["expected_value"],
            "risk_adjusted_return": score["expected_value"]["risk_adjusted_return"],
            "expected_drawdown": score["expected_value"]["expected_drawdown"],
            "confidence_adjusted_ev": score["expected_value"]["confidence_adjusted_ev"],
            "confidence": round(_ratio(_first(opportunity, "confidence", default=0.5)), 6),
            "capital_efficiency": round(score["score_breakdown"]["capital_efficiency"] / 100.0, 6),
            "score_breakdown": score["score_breakdown"],
            "recommendation": score["recommendation"],
            "advisory_only": True,
            "execution_allowed": False,
            "live_trading_enabled": False,
            "_input_order": input_order,
        }


def build_opportunity_intelligence_report(dashboard_payload: Mapping[str, Any] | None) -> dict[str, Any]:
    payload = _mapping(dashboard_payload)
    broker_summary = _mapping(payload.get("broker_summary"))
    execution = _mapping(payload.get("execution_summary"))
    broker_performance = _mapping(_mapping(payload.get("broker_performance_intelligence")).get("broker_performance_intelligence"))
    broker_score = _number(broker_performance.get("overall_score", 70.0))
    context = {
        "broker": broker_summary.get("selected_broker", _mapping(payload.get("account_summary")).get("broker", "UNKNOWN")),
        "broker_performance": broker_score / 100.0,
        "execution_quality": _execution_quality(execution),
        "slippage_bps": execution.get("avg_slippage_bps", 0.0),
        "liquidity_score": _market_liquidity(_mapping(payload.get("market_summary"))),
        "regime_alignment": _market_regime_alignment(_mapping(payload.get("market_summary"))),
    }
    return OpportunityIntelligenceEngine().evaluate(_list(payload.get("opportunities")), context=context)


def _leaderboard_row(item: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "rank": item["rank"],
        "asset": item["asset"],
        "strategy": item["strategy"],
        "broker": item["broker"],
        "score": item["opportunity_score"],
        "expected_value": item["expected_value"],
        "confidence": item["confidence"],
        "capital_efficiency": item["capital_efficiency"],
        "status": item["status"],
        "summary": item["explanation"],
    }


def _eligible(row: Mapping[str, Any]) -> bool:
    if "valid" in row and bool(row.get("valid")) is False:
        return False
    status = {
        str(row.get("status", "")),
        str(row.get("approval_state", "")),
        str(row.get("risk_state", "")),
    }
    normalized = {value.strip().upper() for value in status if value}
    return not bool(normalized & {"REJECTED", "BLOCKED", "DENIED", "NOT_APPROVED"})


def _explain_factors(breakdown: Mapping[str, float]) -> tuple[list[str], list[str], list[str]]:
    labels = {
        "expected_value": "Expected value",
        "decision_confidence": "Decision confidence",
        "broker_performance": "Broker performance",
        "execution_quality": "Execution quality",
        "regime_match": "Regime match",
        "liquidity": "Liquidity",
        "diversification": "Portfolio diversification",
        "capital_efficiency": "Capital efficiency",
        "historical_reliability": "Historical reliability",
    }
    strengths = [labels[key] for key, value in breakdown.items() if value >= 75.0]
    weaknesses = [labels[key] for key, value in breakdown.items() if value < 45.0]
    supporting = [f"{labels[key]}={value:.1f}" for key, value in sorted(breakdown.items())]
    return strengths, weaknesses, supporting


def _opportunity_warnings(opportunity: Mapping[str, Any], score: Mapping[str, Any]) -> list[str]:
    warnings: list[str] = []
    if score["status"] == "RED":
        warnings.append("Opportunity score is RED")
    if _ratio(_first(opportunity, "liquidity", "liquidity_score", default=0.6)) < 0.35:
        warnings.append("Liquidity is weak")
    if _ratio(_first(opportunity, "broker_performance", "broker_score", default=0.7)) < 0.45:
        warnings.append("Broker performance is weak")
    return warnings


def _safety_blockers(opportunity: Mapping[str, Any]) -> list[str]:
    blockers: list[str] = []
    if _truthy(opportunity.get("live_trading_enabled")) or _truthy(opportunity.get("can_live_execute")):
        blockers.append("Live trading authority is outside opportunity intelligence")
    if str(opportunity.get("go_no_go", "")).upper() == "NO GO":
        blockers.append("NO-GO protection is active")
    return sorted(dict.fromkeys(blockers))


def _score_explanation(opportunity: Mapping[str, Any], score: float, status: str, recommendation: str) -> str:
    asset = str(_first(opportunity, "asset", "symbol", default="UNKNOWN")).upper()
    strategy = str(_first(opportunity, "strategy", "strategy_id", default="UNKNOWN"))
    return (
        f"{asset} via {strategy} scored {score:.1f} ({status}); recommendation is {recommendation}. "
        "This is advisory-only opportunity intelligence and does not authorize execution."
    )


def _recommendation(status: str, blockers: list[str]) -> str:
    if blockers:
        return "DO_NOT_ALLOCATE"
    if status == "GREEN":
        return "PAPER_PRIORITY_REVIEW"
    if status == "AMBER":
        return "MONITOR"
    return "DO_NOT_ALLOCATE"


def _status(score: float) -> str:
    if score >= 75.0:
        return "GREEN"
    if score >= 45.0:
        return "AMBER"
    return "RED"


def _capital_efficiency(opportunity: Mapping[str, Any]) -> float:
    explicit = _first(opportunity, "capital_efficiency", "capital_efficiency_score", default=None)
    if explicit is not None:
        return _ratio(explicit) * 100.0
    requested = abs(_number(_first(opportunity, "requested_capital", "capital_at_risk", "allocation_amount", default=1000.0)))
    reward = max(0.0, _number(_first(opportunity, "expected_reward", "expected_value", "reward", default=0.0)))
    if requested <= 0.0:
        return 0.0
    return _clamp01(reward / requested) * 100.0


def _execution_quality(execution: Mapping[str, Any]) -> float:
    state = str(execution.get("execution_state", "IDLE")).upper()
    slippage = _ratio(execution.get("avg_slippage_bps", 0.0), scale=25.0)
    spread = _ratio(execution.get("avg_spread_bps", 0.0), scale=25.0)
    base = 0.85 if state in {"READY", "OK"} else 0.55
    return _clamp01(base - (slippage * 0.2) - (spread * 0.15))


def _market_liquidity(market: Mapping[str, Any]) -> float:
    state = str(market.get("liquidity_state", "")).upper()
    if state in {"HEALTHY", "HIGH", "GREEN"}:
        return 0.9
    if state in {"LOW", "WEAK", "RED"}:
        return 0.25
    return 0.6


def _market_regime_alignment(market: Mapping[str, Any]) -> float:
    state = str(market.get("regime_state", market.get("trend_state", ""))).upper()
    if state in {"RISK_ON", "UPTREND", "TRENDING", "FAVORABLE"}:
        return 0.85
    if state in {"RISK_OFF", "STRESSED", "UNFAVORABLE"}:
        return 0.25
    return 0.6


def _score_signed(value: Any, *, scale: float) -> float:
    numeric = _number(value)
    if numeric >= 0:
        return _clamp01(0.5 + (numeric / max(scale, 1.0))) * 100.0
    return _clamp01(0.5 + (numeric / max(scale, 1.0))) * 100.0


def _first(source: Mapping[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        value = source.get(key)
        if value not in (None, ""):
            return value
    return default


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _number(value: Any) -> float:
    try:
        if value is None or isinstance(value, bool):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _ratio(value: Any, *, scale: float = 1.0) -> float:
    numeric = _number(value)
    if scale != 1.0:
        return _clamp01(numeric / scale)
    if abs(numeric) > 1.0:
        return _clamp01(numeric / 100.0)
    return _clamp01(numeric)


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on", "enabled", "ready", "go"}


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


__all__ = [
    "ExpectedValueEngine",
    "OpportunityIntelligenceEngine",
    "OpportunityIntelligenceEngineError",
    "RiskAdjustedOpportunityScoringEngine",
    "build_opportunity_intelligence_report",
]

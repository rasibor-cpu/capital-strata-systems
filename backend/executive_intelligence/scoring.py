"""Executive KPI scoring engine (Architecture Freeze v1.0)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.executive_intelligence.constants import KPI_NAMES
from backend.executive_intelligence.utils import (
    as_mapping,
    clamp01,
    normalize_freshness,
    posture_from_runtime,
    worst_freshness,
)


def build_kpi(
    *,
    name: str,
    value: float | None,
    confidence: float | None,
    freshness: str,
    producer: str,
    validation: str,
    detail: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "name": name,
        "value": value if value is None else round(float(value), 6),
        "confidence": confidence if confidence is None else round(float(confidence), 6),
        "freshness": normalize_freshness(freshness),
        "producer": producer,
        "validation": validation,
        "detail": dict(detail or {}),
    }


def score_all_kpis(evidence: Mapping[str, Any], panels: Mapping[str, Any]) -> dict[str, Any]:
    """Calculate all frozen KPIs. Missing inputs → value null + UNAVAILABLE freshness."""
    runtime = as_mapping(evidence.get("runtime_health"))
    broker = as_mapping(evidence.get("broker_health"))
    market = as_mapping(panels.get("market_intelligence"))
    trading = as_mapping(panels.get("trading_intelligence"))
    learning = as_mapping(panels.get("learning"))
    decision = as_mapping(panels.get("executive_decision"))
    portfolio = as_mapping(evidence.get("portfolio"))
    opportunities = evidence.get("opportunities")
    if not isinstance(opportunities, list):
        opportunities = trading.get("ranked_opportunities") if isinstance(trading.get("ranked_opportunities"), list) else []

    runtime_fresh = normalize_freshness(runtime.get("freshness", panels.get("operational_health", {}).get("freshness")))
    broker_fresh = normalize_freshness(broker.get("freshness", "UNAVAILABLE"))
    market_fresh = normalize_freshness(market.get("freshness", "UNAVAILABLE"))
    portfolio_fresh = normalize_freshness(portfolio.get("freshness", trading.get("freshness", "UNAVAILABLE")))

    runtime_score = _runtime_score(runtime)
    broker_score = _broker_score(broker)
    market_score = _market_score(market)
    opp_score = _opportunity_density(opportunities)
    decision_score = _decision_quality(decision)
    learning_score = _learning_velocity(learning)
    capital_score = _capital_efficiency(portfolio, trading)
    risk_score = _risk_stability(decision, evidence)
    strategy_score = _strategy_strength(learning, opportunities)
    rec_score = _recommendation_quality(decision)

    board = {
        "runtime_health": build_kpi(
            name="runtime_health",
            value=runtime_score,
            confidence=clamp01(runtime.get("confidence", runtime_score)),
            freshness=runtime_fresh,
            producer="runtime_health_aggregator|supervisor",
            validation="PASS" if runtime_score is not None else "UNAVAILABLE",
        ),
        "market_readiness": build_kpi(
            name="market_readiness",
            value=market_score,
            confidence=clamp01(market.get("confidence")),
            freshness=market_fresh,
            producer="market_intelligence_panel",
            validation="PASS" if market_score is not None else "UNAVAILABLE",
        ),
        "opportunity_density": build_kpi(
            name="opportunity_density",
            value=opp_score,
            confidence=clamp01(decision.get("confidence")),
            freshness=normalize_freshness(trading.get("freshness", "UNAVAILABLE")),
            producer="opportunity_ranking",
            validation="PASS" if opp_score is not None else "UNAVAILABLE",
        ),
        "decision_quality": build_kpi(
            name="decision_quality",
            value=decision_score,
            confidence=clamp01(decision.get("confidence")),
            freshness=normalize_freshness(decision.get("freshness", "UNAVAILABLE")),
            producer="executive_decision_panel",
            validation="PASS" if decision_score is not None else "UNAVAILABLE",
        ),
        "learning_velocity": build_kpi(
            name="learning_velocity",
            value=learning_score,
            confidence=clamp01(learning.get("confidence")),
            freshness=normalize_freshness(learning.get("freshness", "UNAVAILABLE")),
            producer="learning_panel",
            validation="PASS" if learning_score is not None else "UNAVAILABLE",
        ),
        "capital_efficiency": build_kpi(
            name="capital_efficiency",
            value=capital_score,
            confidence=clamp01(portfolio.get("confidence", capital_score)),
            freshness=portfolio_fresh,
            producer="portfolio|trading_intelligence",
            validation="PASS" if capital_score is not None else "UNAVAILABLE",
        ),
        "risk_stability": build_kpi(
            name="risk_stability",
            value=risk_score,
            confidence=clamp01(decision.get("confidence")),
            freshness=normalize_freshness(decision.get("freshness", "UNAVAILABLE")),
            producer="risk_committee|executive_decision",
            validation="PASS" if risk_score is not None else "UNAVAILABLE",
        ),
        "broker_reliability": build_kpi(
            name="broker_reliability",
            value=broker_score,
            confidence=clamp01(broker.get("confidence", broker_score)),
            freshness=broker_fresh,
            producer="broker_operational_status",
            validation="PASS" if broker_score is not None else "UNAVAILABLE",
        ),
        "strategy_strength": build_kpi(
            name="strategy_strength",
            value=strategy_score,
            confidence=clamp01(learning.get("confidence", strategy_score)),
            freshness=worst_freshness(
                normalize_freshness(learning.get("freshness", "UNAVAILABLE")),
                normalize_freshness(trading.get("freshness", "UNAVAILABLE")),
            ),
            producer="learning|opportunity_ranking",
            validation="PASS" if strategy_score is not None else "UNAVAILABLE",
        ),
        "market_confidence": build_kpi(
            name="market_confidence",
            value=clamp01(market.get("confidence", market_score)),
            confidence=clamp01(market.get("confidence", market_score)),
            freshness=market_fresh,
            producer="market_intelligence_panel",
            validation="PASS" if market.get("confidence") is not None or market_score is not None else "UNAVAILABLE",
        ),
        "recommendation_quality": build_kpi(
            name="recommendation_quality",
            value=rec_score,
            confidence=clamp01(decision.get("confidence", rec_score)),
            freshness=normalize_freshness(decision.get("freshness", "UNAVAILABLE")),
            producer="executive_actions",
            validation="PASS" if rec_score is not None else "UNAVAILABLE",
        ),
    }

    # Ensure all frozen names present
    for name in KPI_NAMES:
        board.setdefault(
            name,
            build_kpi(
                name=name,
                value=None,
                confidence=None,
                freshness="UNAVAILABLE",
                producer="executive_scoring_engine",
                validation="UNAVAILABLE",
            ),
        )

    # Legacy MC aliases (compatible fields)
    board["aliases"] = {
        "uptime": board["runtime_health"].get("value"),
        "portfolio_health": capital_score,
        "risk_health": risk_score,
        "market_health": market_score,
        "broker_health": broker_score,
        "system_readiness": _mean_available(
            [runtime_score, broker_score, market_score, capital_score]
        ),
    }
    return board


def _runtime_score(runtime: Mapping[str, Any]) -> float | None:
    if not runtime:
        return None
    if "score" in runtime:
        return clamp01(runtime.get("score"))
    posture = posture_from_runtime(str(runtime.get("status", runtime.get("runtime_health", ""))))
    mapping = {"GREEN": 0.95, "AMBER": 0.65, "RED": 0.25, "UNAVAILABLE": None}
    return mapping.get(posture)


def _broker_score(broker: Mapping[str, Any]) -> float | None:
    if not broker:
        return None
    if "score" in broker:
        return clamp01(broker.get("score"))
    details = as_mapping(broker.get("brokers") or broker.get("venues") or broker.get("broker_health_details"))
    if details:
        scores = []
        for meta in details.values():
            if isinstance(meta, Mapping):
                status = str(meta.get("health", meta.get("status", "UNAVAILABLE"))).upper()
            else:
                status = str(meta).upper()
            scores.append({"GREEN": 1.0, "HEALTHY": 1.0, "AMBER": 0.6, "LATENT": 0.55, "DEGRADED": 0.4, "RED": 0.2, "OFFLINE": 0.0}.get(status, 0.3))
        if scores:
            return sum(scores) / len(scores)
    status = str(broker.get("health", broker.get("status", ""))).upper()
    return {"GREEN": 0.95, "HEALTHY": 0.95, "AMBER": 0.6, "RED": 0.2, "OFFLINE": 0.0}.get(status)


def _market_score(market: Mapping[str, Any]) -> float | None:
    if not market:
        return None
    if str(market.get("panel_status", "")).upper() == "UNAVAILABLE":
        return None
    mc = as_mapping(market.get("market_confidence"))
    if "value" in mc and mc.get("value") is not None:
        return clamp01(mc.get("value"))
    if "score" in market:
        return clamp01(market.get("score"))
    regime = market.get("regime_current") or market.get("regime")
    if regime and str(regime).upper() not in {"UNAVAILABLE", "UNKNOWN", ""}:
        conf = clamp01(market.get("confidence"))
        return conf if conf is not None else 0.7
    return None


def _opportunity_density(opportunities: list[Any]) -> float | None:
    if not opportunities:
        return 0.0
    confidences = []
    for item in opportunities[:10]:
        if isinstance(item, Mapping):
            c = clamp01(item.get("confidence", item.get("score", item.get("expected_return"))))
            if c is not None:
                confidences.append(c)
    mean_c = sum(confidences) / len(confidences) if confidences else 0.5
    density = min(1.0, (len(opportunities) / 10.0) * mean_c)
    return round(density, 6)


def _decision_quality(decision: Mapping[str, Any]) -> float | None:
    if not decision:
        return None
    conf = clamp01(decision.get("confidence") or decision.get("decision_confidence"))
    vetoes = decision.get("committee_vetoes") or []
    warnings = decision.get("operational_warnings") or []
    if conf is None:
        return None
    penalty = min(0.5, 0.1 * len(vetoes) + 0.05 * len(warnings))
    return max(0.0, conf - penalty)


def _learning_velocity(learning: Mapping[str, Any]) -> float | None:
    summary = as_mapping(learning.get("learning_summary"))
    if not summary and not learning:
        return None
    if "velocity" in summary:
        return clamp01(summary.get("velocity"))
    optimality = clamp01(summary.get("optimality_rate"))
    if optimality is not None:
        return optimality
    trade_count = summary.get("trade_count")
    try:
        tc = float(trade_count)
        return clamp01(min(1.0, tc / 50.0))
    except (TypeError, ValueError):
        if learning.get("panel_status") and str(learning.get("panel_status")).upper() != "UNAVAILABLE":
            return 0.5
        return None


def _capital_efficiency(portfolio: Mapping[str, Any], trading: Mapping[str, Any]) -> float | None:
    for source in (portfolio, trading.get("portfolio_summary") if isinstance(trading.get("portfolio_summary"), Mapping) else {}):
        src = as_mapping(source)
        for key in ("capital_efficiency", "portfolio_health", "efficiency"):
            if key in src:
                return clamp01(src.get(key))
        health = str(src.get("portfolio_status", src.get("status", ""))).upper()
        if health in {"GREEN", "OK", "HEALTHY"}:
            return 0.85
        if health in {"AMBER", "PARTIAL"}:
            return 0.55
        if health in {"RED"}:
            return 0.25
    return None


def _risk_stability(decision: Mapping[str, Any], evidence: Mapping[str, Any]) -> float | None:
    risk = as_mapping(evidence.get("risk"))
    if "stability" in risk:
        return clamp01(risk.get("stability"))
    vetoes = decision.get("committee_vetoes") or risk.get("vetoes") or []
    level = str(risk.get("risk_level", decision.get("overall_decision_status", ""))).upper()
    base = {"GREEN": 0.9, "LOW": 0.85, "MEDIUM": 0.65, "HIGH": 0.35, "CRITICAL": 0.1, "AMBER": 0.55, "RED": 0.2}.get(level)
    if base is None and not decision:
        return None
    if base is None:
        base = 0.6
    return max(0.0, base - 0.1 * len(list(vetoes)))


def _strategy_strength(learning: Mapping[str, Any], opportunities: list[Any]) -> float | None:
    summary = as_mapping(learning.get("learning_summary"))
    if "top_strategy_score" in summary:
        return clamp01(summary.get("top_strategy_score"))
    if summary.get("top_strategy"):
        return 0.7
    if opportunities:
        return _opportunity_density(opportunities)
    if learning.get("panel_status") and str(learning.get("panel_status")).upper() != "UNAVAILABLE":
        return 0.5
    return None


def _recommendation_quality(decision: Mapping[str, Any]) -> float | None:
    actions = decision.get("recommended_actions") or decision.get("executive_actions") or []
    if not isinstance(actions, list):
        return None
    if not actions:
        return 0.4
    cited = 0
    for action in actions:
        if isinstance(action, Mapping) and (action.get("provenance") or action.get("type")):
            cited += 1
        elif isinstance(action, str) and action.strip():
            cited += 1
    conf = clamp01(decision.get("confidence") or decision.get("decision_confidence")) or 0.5
    return clamp01((cited / max(len(actions), 1)) * 0.6 + conf * 0.4)


def _mean_available(values: list[float | None]) -> float | None:
    present = [v for v in values if v is not None]
    if not present:
        return None
    return round(sum(present) / len(present), 6)

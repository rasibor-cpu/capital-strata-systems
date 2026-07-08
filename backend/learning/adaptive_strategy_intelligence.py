from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from backend.learning.regime_strategy_mapper import RegimeStrategyMapper
from backend.learning.strategy_effectiveness_tracker import StrategyEffectivenessTracker
from backend.portfolio.utils import advisory_response, safe_float


PAYLOAD_VERSION = "css.phase157a.adaptive_strategy_intelligence.v1"


class AdaptiveStrategyIntelligenceEngine:
    """Generate advisory adaptive strategy recommendations from learning evidence."""

    def __init__(
        self,
        *,
        effectiveness_tracker: StrategyEffectivenessTracker | None = None,
        regime_mapper: RegimeStrategyMapper | None = None,
        min_evidence: int = 5,
    ) -> None:
        self.effectiveness_tracker = effectiveness_tracker or StrategyEffectivenessTracker()
        self.regime_mapper = regime_mapper or RegimeStrategyMapper()
        self.min_evidence = max(1, int(min_evidence or 5))

    def analyze(
        self,
        history: Iterable[Mapping[str, Any]] | None,
        *,
        decision_confidence: Mapping[str, Any] | None = None,
        broker_performance: Mapping[str, Any] | None = None,
        opportunity_intelligence: Mapping[str, Any] | None = None,
        existing_learning: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            effectiveness = self.effectiveness_tracker.analyze(history, min_evidence=self.min_evidence)
            regime_map = self.regime_mapper.analyze(history, min_evidence=max(2, self.min_evidence // 2))
            recommendations = _strategy_recommendations(
                effectiveness.get("strategy_metrics", {}),
                regime_map.get("regime_strategy_map", {}),
                decision_confidence=decision_confidence,
                broker_performance=broker_performance,
                opportunity_intelligence=opportunity_intelligence,
            )
            status = _overall_status(effectiveness, regime_map, recommendations)
            return advisory_response(
                status,
                payload_version=PAYLOAD_VERSION,
                strategy_effectiveness=effectiveness,
                regime_strategy_mapping=regime_map,
                adaptive_recommendations=recommendations,
                integration=_integration_payload(
                    decision_confidence=decision_confidence,
                    broker_performance=broker_performance,
                    opportunity_intelligence=opportunity_intelligence,
                    existing_learning=existing_learning,
                ),
                reasons=_reasons(effectiveness, regime_map, recommendations),
                recommended_actions=_actions(recommendations),
                **_safety_flags(),
            )
        except Exception as exc:  # noqa: BLE001 - learning failures must fail closed into advisory output.
            return advisory_response(
                "FAIL_CLOSED",
                payload_version=PAYLOAD_VERSION,
                strategy_effectiveness={},
                regime_strategy_mapping={},
                adaptive_recommendations=[],
                reasons=[f"adaptive_strategy_intelligence_failed:{exc.__class__.__name__}"],
                recommended_actions=["Do not change advisory weights until Phase 157A learning recovers."],
                **_safety_flags(),
            )


def analyze_adaptive_strategy_intelligence(
    history: Iterable[Mapping[str, Any]] | None,
    *,
    decision_confidence: Mapping[str, Any] | None = None,
    broker_performance: Mapping[str, Any] | None = None,
    opportunity_intelligence: Mapping[str, Any] | None = None,
    existing_learning: Mapping[str, Any] | None = None,
    min_evidence: int = 5,
) -> dict[str, Any]:
    return AdaptiveStrategyIntelligenceEngine(min_evidence=min_evidence).analyze(
        history,
        decision_confidence=decision_confidence,
        broker_performance=broker_performance,
        opportunity_intelligence=opportunity_intelligence,
        existing_learning=existing_learning,
    )


def _strategy_recommendations(
    metrics: Any,
    regime_map: Any,
    *,
    decision_confidence: Mapping[str, Any] | None,
    broker_performance: Mapping[str, Any] | None,
    opportunity_intelligence: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    if not isinstance(metrics, Mapping):
        return []
    recommendations: list[dict[str, Any]] = []
    for strategy, payload in sorted(metrics.items()):
        if not isinstance(payload, Mapping):
            continue
        base = str(payload.get("recommendation", "Needs additional evidence"))
        conflicts = _conflicts(strategy, payload, regime_map, decision_confidence, broker_performance, opportunity_intelligence)
        action = "Increase monitoring" if conflicts and base in {"Increase confidence weighting", "Reduce confidence weighting"} else base
        recommendations.append(
            {
                "strategy": strategy,
                "recommendation": action,
                "base_recommendation": base,
                "confidence_level": _confidence_level(payload),
                "evidence_state": payload.get("evidence_state", "UNKNOWN"),
                "win_rate": payload.get("win_rate", 0.0),
                "profit_factor": payload.get("profit_factor", 0.0),
                "expectancy": payload.get("expectancy", 0.0),
                "regime_notes": _regime_notes(strategy, regime_map),
                "conflicts": conflicts,
                "advisory_only": True,
                "execution_allowed": False,
            }
        )
    return recommendations


def _conflicts(
    strategy: str,
    metrics: Mapping[str, Any],
    regime_map: Any,
    decision_confidence: Mapping[str, Any] | None,
    broker_performance: Mapping[str, Any] | None,
    opportunity_intelligence: Mapping[str, Any] | None,
) -> list[str]:
    conflicts: list[str] = []
    confidence_score = _strategy_external_score(decision_confidence, strategy, ("strategy_confidence", "confidence", "score"))
    if confidence_score >= 80.0 and str(metrics.get("recommendation")) in {"Reduce confidence weighting", "Temporarily suppress"}:
        conflicts.append("decision_confidence_positive_but_strategy_deteriorating")
    broker_score = _strategy_external_score(broker_performance, strategy, ("broker_score", "performance_score", "score"))
    if broker_score and broker_score < 50.0 and str(metrics.get("recommendation")) == "Increase confidence weighting":
        conflicts.append("broker_performance_weak_for_positive_strategy")
    opportunity_score = _strategy_external_score(opportunity_intelligence, strategy, ("opportunity_score", "score", "confidence"))
    if opportunity_score >= 80.0 and str(metrics.get("evidence_state")) == "INSUFFICIENT":
        conflicts.append("opportunity_intelligence_positive_but_learning_evidence_insufficient")
    if isinstance(regime_map, Mapping):
        weak_regimes = [
            regime
            for regime, payload in regime_map.items()
            if isinstance(payload, Mapping)
            and isinstance(payload.get("strategies"), Mapping)
            and isinstance(payload["strategies"].get(strategy), Mapping)
            and payload["strategies"][strategy].get("recommendation") in {"Reduce confidence weighting", "Temporarily suppress"}
        ]
        if weak_regimes and str(metrics.get("recommendation")) == "Increase confidence weighting":
            conflicts.append("regime_specific_deterioration")
    return conflicts


def _regime_notes(strategy: str, regime_map: Any) -> list[str]:
    notes: list[str] = []
    if not isinstance(regime_map, Mapping):
        return notes
    for regime, payload in sorted(regime_map.items()):
        strategies = payload.get("strategies") if isinstance(payload, Mapping) else None
        strategy_payload = strategies.get(strategy) if isinstance(strategies, Mapping) else None
        if isinstance(strategy_payload, Mapping):
            notes.append(f"{regime}:{strategy_payload.get('recommendation', 'No advisory weighting change')}")
    return notes


def _strategy_external_score(source: Mapping[str, Any] | None, strategy: str, keys: tuple[str, ...]) -> float:
    if not isinstance(source, Mapping):
        return 0.0
    candidates = [
        source.get(strategy),
        (source.get("strategies") or {}).get(strategy) if isinstance(source.get("strategies"), Mapping) else None,
        (source.get("strategy_scores") or {}).get(strategy) if isinstance(source.get("strategy_scores"), Mapping) else None,
    ]
    for candidate in candidates:
        if isinstance(candidate, Mapping):
            for key in keys:
                if candidate.get(key) is not None:
                    return safe_float(candidate.get(key))
        elif candidate is not None:
            return safe_float(candidate)
    return 0.0


def _confidence_level(metrics: Mapping[str, Any]) -> str:
    if metrics.get("evidence_state") != "SUFFICIENT":
        return "LOW"
    score = safe_float(metrics.get("win_rate")) * 0.4 + min(100.0, safe_float(metrics.get("profit_factor")) * 25.0) * 0.3 + max(0.0, safe_float(metrics.get("sharpe")) * 20.0) * 0.3
    if score >= 75.0:
        return "HIGH"
    if score >= 50.0:
        return "MEDIUM"
    return "LOW"


def _overall_status(effectiveness: Mapping[str, Any], regime_map: Mapping[str, Any], recommendations: list[Mapping[str, Any]]) -> str:
    if effectiveness.get("status") == "DATA UNAVAILABLE" and regime_map.get("status") == "DATA UNAVAILABLE":
        return "DATA UNAVAILABLE"
    if any(item.get("conflicts") for item in recommendations):
        return "PARTIAL"
    if effectiveness.get("status") == "OK" and regime_map.get("status") in {"OK", "PARTIAL"}:
        return "OK"
    return "PARTIAL"


def _integration_payload(
    *,
    decision_confidence: Mapping[str, Any] | None,
    broker_performance: Mapping[str, Any] | None,
    opportunity_intelligence: Mapping[str, Any] | None,
    existing_learning: Mapping[str, Any] | None,
) -> dict[str, Any]:
    return {
        "decision_confidence_consumed": isinstance(decision_confidence, Mapping),
        "broker_performance_intelligence_consumed": isinstance(broker_performance, Mapping),
        "opportunity_intelligence_consumed": isinstance(opportunity_intelligence, Mapping),
        "existing_learning_consumed": isinstance(existing_learning, Mapping),
        "execution_decisions_changed": False,
        "broker_state_changed": False,
    }


def _reasons(effectiveness: Mapping[str, Any], regime_map: Mapping[str, Any], recommendations: list[Mapping[str, Any]]) -> list[str]:
    reasons = []
    reasons.extend(str(item) for item in effectiveness.get("reasons", []))
    reasons.extend(str(item) for item in regime_map.get("reasons", []))
    if any(item.get("conflicts") for item in recommendations):
        reasons.append("conflicting_advisory_evidence_detected")
    return sorted(set(reasons)) or ["adaptive_strategy_intelligence_computed"]


def _actions(recommendations: list[Mapping[str, Any]]) -> list[str]:
    actions = sorted({str(item.get("recommendation", "Needs additional evidence")) for item in recommendations})
    actions.append("Review recommendations as advisory learning evidence only.")
    actions.append("Never use Phase 157A output to authorize execution.")
    return actions


def _safety_flags() -> dict[str, bool]:
    return {
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "execution_authority_changed": False,
        "broker_state_changed": False,
    }

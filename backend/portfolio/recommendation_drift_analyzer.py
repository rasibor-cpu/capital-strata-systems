from __future__ import annotations

from typing import Any, Iterable, Mapping

from backend.portfolio.constants import RECOMMENDATION_ORDER
from backend.portfolio.utils import advisory_response


class RecommendationDriftAnalyzerError(RuntimeError):
    """Fail-closed exception for recommendation drift analytics."""


class RecommendationDriftAnalyzer:
    """Detect deterministic recommendation instability and policy drift."""

    def analyze(self, history: Iterable[Mapping[str, Any]] | None) -> dict[str, Any]:
        rows = self._rows(history)
        if len(rows) < 2:
            return advisory_response(
                "DATA UNAVAILABLE",
                drift_status="DATA UNAVAILABLE",
                drift_score=None,
                drift_severity="RED",
                recommendation_stability=None,
                excessive_oscillation=False,
                policy_drift=False,
                regime_drift=False,
                recommendation_reversals=0,
                recommendation="Insufficient recommendation sequence for drift evaluation.",
            )

        transitions = len(rows) - 1
        recommendation_changes = 0
        policy_changes = 0
        regime_changes = 0
        reversals = 0

        for previous, current in zip(rows, rows[1:]):
            if previous["recommendation"] != current["recommendation"]:
                recommendation_changes += 1
            if previous["policy_profile"] != current["policy_profile"]:
                policy_changes += 1
            if previous["market_regime"] != current["market_regime"]:
                regime_changes += 1
            if abs(previous["rank"] - current["rank"]) >= 2:
                reversals += 1

        instability = recommendation_changes / transitions
        policy_rate = policy_changes / transitions
        regime_rate = regime_changes / transitions
        reversal_rate = reversals / transitions
        drift_score = round(
            min(100.0, (instability * 45.0) + (reversal_rate * 35.0) + (policy_rate * 10.0) + (regime_rate * 10.0)),
            6,
        )
        stability = round(max(0.0, 100.0 - drift_score), 6)
        if drift_score >= 70.0:
            severity = "RED"
            recommendation = "Recommendation sequence is unstable; review policy and regime inputs."
        elif drift_score >= 35.0:
            severity = "AMBER"
            recommendation = "Monitor recommendation movement for oscillation before operational reliance."
        else:
            severity = "GREEN"
            recommendation = "Recommendation sequence is stable."

        return advisory_response(
            "OK",
            drift_status=severity,
            drift_score=drift_score,
            drift_severity=severity,
            recommendation_stability=stability,
            excessive_oscillation=instability > 0.65 or reversals >= max(2, transitions // 2),
            policy_drift=policy_rate > 0.25,
            regime_drift=regime_rate > 0.35,
            recommendation_reversals=reversals,
            recommendation_changes=recommendation_changes,
            policy_changes=policy_changes,
            regime_changes=regime_changes,
            evaluated_recommendations=len(rows),
            recommendation=recommendation,
        )

    @staticmethod
    def _rows(history: Iterable[Mapping[str, Any]] | None) -> list[dict[str, Any]]:
        if history is None or isinstance(history, (str, bytes)):
            return []
        try:
            iterator = iter(history)
        except TypeError:
            return []
        rows: list[dict[str, Any]] = []
        for item in iterator:
            if not isinstance(item, Mapping):
                continue
            recommendation = str(
                item.get(
                    "recommendation",
                    item.get("portfolio_recommendation", item.get("adaptive_recommendation", item.get("action", ""))),
                )
                or ""
            ).strip().upper()
            if not recommendation:
                continue
            rows.append(
                {
                    "recommendation": recommendation,
                    "policy_profile": RecommendationDriftAnalyzer._dimension(item, "policy_profile", "POLICY_UNSPECIFIED"),
                    "market_regime": RecommendationDriftAnalyzer._dimension(item, "market_regime", "REGIME_UNSPECIFIED"),
                    "rank": RECOMMENDATION_ORDER.get(recommendation, 2),
                }
            )
        return rows

    @staticmethod
    def _dimension(row: Mapping[str, Any], key: str, fallback: str) -> str:
        value = row.get(key)
        if value is None and isinstance(row.get("context"), Mapping):
            value = row["context"].get(key)
        return str(value or fallback).strip().upper()

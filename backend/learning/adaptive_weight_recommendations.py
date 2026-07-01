from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.learning.common import FACTORS, BALANCED_WEIGHTS, normalize_weights
from backend.portfolio.utils import advisory_response, safe_float


class AdaptiveWeightRecommendationEngine:
    """Recommend advisory-only factor weights from learned reliability evidence."""

    def recommend(
        self,
        *,
        factor_performance: Mapping[str, Any] | None = None,
        rolling_reliability: Mapping[str, Any] | None = None,
        regime_learning: Mapping[str, Any] | None = None,
        current_weights: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        performance = factor_performance if isinstance(factor_performance, Mapping) else {}
        reliability = rolling_reliability if isinstance(rolling_reliability, Mapping) else {}
        regimes = regime_learning if isinstance(regime_learning, Mapping) else {}
        factors = performance.get("factors", {}) if isinstance(performance.get("factors"), Mapping) else {}
        latest = reliability.get("latest_reliability", {}) if isinstance(reliability.get("latest_reliability"), Mapping) else {}

        if not factors and not latest:
            recommended = normalize_weights(BALANCED_WEIGHTS)
            current = normalize_weights(current_weights or BALANCED_WEIGHTS)
            return advisory_response(
                "PARTIAL",
                recommended_weights=recommended,
                current_weights=current,
                weight_deltas={factor: round(recommended[factor] - current[factor], 6) for factor in FACTORS},
                recommendation_strength="LOW",
                strongest_regime=str(regimes.get("strongest_regime", "UNKNOWN")) if regimes else "UNKNOWN",
                reasons=["balanced_default_due_to_insufficient_learning"],
                recommended_actions=[
                    "Collect factor performance history before changing advisory weights.",
                    "Do not apply learned weights to execution authority.",
                ],
            )

        raw: dict[str, float] = {}
        reasons: list[str] = []
        for factor in FACTORS:
            perf = factors.get(factor, {}) if isinstance(factors.get(factor), Mapping) else {}
            reliability_score = safe_float(perf.get("reliability_score"), safe_float(latest.get(factor), 50.0))
            hit_rate = safe_float(perf.get("hit_rate"), reliability_score)
            avg_outcome = safe_float(perf.get("average_outcome"), 0.0)
            raw[factor] = max(0.0, 10.0 + reliability_score * 0.55 + hit_rate * 0.35 + avg_outcome * 0.1)
            if perf.get("sample_size", 0) == 0:
                raw[factor] *= 0.5
                reasons.append(f"{factor}_low_evidence")

        if not any(raw.values()):
            raw = dict(BALANCED_WEIGHTS)
            reasons.append("balanced_default_due_to_insufficient_learning")

        recommended = normalize_weights(raw)
        current = normalize_weights(current_weights or BALANCED_WEIGHTS)
        deltas = {factor: round(recommended[factor] - current[factor], 6) for factor in FACTORS}
        max_delta = max(abs(value) for value in deltas.values()) if deltas else 0.0
        strongest_regime = str(regimes.get("strongest_regime", "UNKNOWN")) if regimes else "UNKNOWN"
        status = "OK" if performance.get("status") in {"OK", "PARTIAL"} else "PARTIAL"
        return advisory_response(
            status,
            recommended_weights=recommended,
            current_weights=current,
            weight_deltas=deltas,
            recommendation_strength="HIGH" if max_delta >= 10.0 else "MEDIUM" if max_delta >= 5.0 else "LOW",
            strongest_regime=strongest_regime,
            reasons=sorted(set(reasons)) or ["adaptive_weight_recommendation_from_learning"],
            recommended_actions=[
                "Review learned weights before applying them to advisory scoring.",
                "Do not apply learned weights to execution authority.",
            ],
        )

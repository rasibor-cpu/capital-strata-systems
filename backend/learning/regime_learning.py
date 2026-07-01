from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from backend.learning.common import factor_scores, hit, outcome, regime, rows, unavailable
from backend.portfolio.utils import advisory_response


class RegimeLearningEngine:
    """Learn advisory performance patterns by market regime."""

    def analyze(self, history: Iterable[Mapping[str, Any]] | None) -> dict[str, Any]:
        buckets: dict[str, list[dict[str, Any]]] = {}
        for row in rows(history):
            realized = outcome(row)
            scores = factor_scores(row)
            if realized is None or not scores:
                continue
            avg_score = sum(scores.values()) / len(scores)
            buckets.setdefault(regime(row), []).append(
                {"outcome": realized, "hit": 1.0 if hit(avg_score, realized) else 0.0, "scores": scores}
            )

        if not buckets:
            return unavailable(
                "regime_learning_history_unavailable",
                regimes={},
                strongest_regime="DATA UNAVAILABLE",
                weakest_regime="DATA UNAVAILABLE",
            )

        regimes: dict[str, dict[str, Any]] = {}
        for name, values in buckets.items():
            count = len(values)
            avg_outcome = sum(item["outcome"] for item in values) / count
            hit_rate = sum(item["hit"] for item in values) / count
            factor_totals: dict[str, list[float]] = {}
            for item in values:
                for factor, score in item["scores"].items():
                    factor_totals.setdefault(factor, []).append(score)
            factor_strength = {
                factor: round(sum(scores) / len(scores), 6)
                for factor, scores in factor_totals.items()
                if scores
            }
            regimes[name] = {
                "sample_size": count,
                "average_outcome": round(avg_outcome, 6),
                "hit_rate": round(hit_rate * 100.0, 6),
                "factor_strength": factor_strength,
                "best_factor": max(factor_strength, key=factor_strength.get) if factor_strength else "DATA UNAVAILABLE",
            }
        ranked = sorted(regimes.items(), key=lambda item: (item[1]["average_outcome"], item[1]["hit_rate"]), reverse=True)
        return advisory_response(
            "OK",
            regimes=regimes,
            strongest_regime=ranked[0][0],
            weakest_regime=ranked[-1][0],
            recommended_actions=[
                f"Use {ranked[0][0]} as the strongest current evidence regime.",
                f"Treat {ranked[-1][0]} with additional advisory caution.",
            ],
        )

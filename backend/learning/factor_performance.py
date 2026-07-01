from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from backend.learning.common import FACTORS, factor_scores, hit, outcome, rows, unavailable
from backend.portfolio.utils import advisory_response


class FactorPerformanceEngine:
    """Evaluate historical advisory factor scores against subsequent outcomes."""

    def analyze(self, history: Iterable[Mapping[str, Any]] | None) -> dict[str, Any]:
        records = rows(history)
        factor_rows: dict[str, list[dict[str, float]]] = {factor: [] for factor in FACTORS}
        for row in records:
            realized = outcome(row)
            if realized is None:
                continue
            scores = factor_scores(row)
            for factor, score in scores.items():
                factor_rows[factor].append(
                    {
                        "score": score,
                        "outcome": realized,
                        "hit": 1.0 if hit(score, realized) else 0.0,
                    }
                )

        if not any(factor_rows.values()):
            return unavailable(
                "factor_performance_history_unavailable",
                factors={},
                best_factor="DATA UNAVAILABLE",
                weakest_factor="DATA UNAVAILABLE",
                recommended_actions=["Collect evaluated advisory history before changing factor emphasis."],
            )

        factors: dict[str, dict[str, Any]] = {}
        for factor, values in factor_rows.items():
            if not values:
                factors[factor] = {
                    "sample_size": 0,
                    "average_score": None,
                    "average_outcome": None,
                    "hit_rate": None,
                    "reliability_score": 0.0,
                }
                continue
            sample_size = len(values)
            hit_rate = sum(item["hit"] for item in values) / sample_size
            average_outcome = sum(item["outcome"] for item in values) / sample_size
            factors[factor] = {
                "sample_size": sample_size,
                "average_score": round(sum(item["score"] for item in values) / sample_size, 6),
                "average_outcome": round(average_outcome, 6),
                "hit_rate": round(hit_rate * 100.0, 6),
                "reliability_score": round(max(0.0, min(100.0, hit_rate * 70.0 + (50.0 + average_outcome) * 0.3)), 6),
            }

        ranked = sorted(
            (item for item in factors.items() if item[1]["sample_size"] > 0),
            key=lambda item: (item[1]["reliability_score"], item[1]["average_outcome"]),
            reverse=True,
        )
        status = "OK" if len(ranked) == len(FACTORS) else "PARTIAL"
        return advisory_response(
            status,
            sample_size=sum(item["sample_size"] for item in factors.values()),
            factors=factors,
            best_factor=ranked[0][0],
            weakest_factor=ranked[-1][0],
            recommended_actions=self._actions(ranked),
        )

    @staticmethod
    def _actions(ranked: list[tuple[str, dict[str, Any]]]) -> list[str]:
        if not ranked:
            return ["Collect evaluated advisory history before changing factor emphasis."]
        best, weakest = ranked[0][0], ranked[-1][0]
        if best == weakest:
            return ["Maintain balanced advisory weighting until more factor evidence accumulates."]
        return [
            f"Consider modestly increasing advisory emphasis on {best}.",
            f"Review {weakest} inputs before increasing its advisory weight.",
        ]

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from backend.learning.common import FACTORS, factor_scores, hit, outcome, rows, unavailable
from backend.portfolio.utils import advisory_response


class RollingReliabilityEngine:
    """Compute rolling hit-rate reliability for each advisory factor."""

    def evaluate(self, history: Iterable[Mapping[str, Any]] | None, *, window: int = 5) -> dict[str, Any]:
        records = rows(history)
        safe_window = max(2, int(window or 5))
        factor_hits: dict[str, list[float]] = {factor: [] for factor in FACTORS}
        for row in records:
            realized = outcome(row)
            if realized is None:
                continue
            for factor, score in factor_scores(row).items():
                factor_hits[factor].append(1.0 if hit(score, realized) else 0.0)

        if not any(factor_hits.values()):
            return unavailable(
                "rolling_reliability_history_unavailable",
                rolling_reliability={},
                latest_reliability={},
                reliability_status="DATA UNAVAILABLE",
            )

        rolling: dict[str, list[dict[str, Any]]] = {}
        latest: dict[str, float | None] = {}
        for factor, values in factor_hits.items():
            points: list[dict[str, Any]] = []
            for index in range(len(values)):
                window_values = values[max(0, index - safe_window + 1) : index + 1]
                points.append(
                    {
                        "index": index,
                        "sample_size": len(window_values),
                        "reliability": round((sum(window_values) / len(window_values)) * 100.0, 6),
                    }
                )
            rolling[factor] = points
            latest[factor] = points[-1]["reliability"] if points else None

        numeric_latest = [value for value in latest.values() if value is not None]
        average_latest = sum(numeric_latest) / len(numeric_latest) if numeric_latest else 0.0
        status = "STABLE" if average_latest >= 60.0 else "DEGRADED" if average_latest >= 40.0 else "WEAK"
        return advisory_response(
            "OK" if len(numeric_latest) == len(FACTORS) else "PARTIAL",
            window=safe_window,
            rolling_reliability=rolling,
            latest_reliability=latest,
            average_latest_reliability=round(average_latest, 6),
            reliability_status=status,
        )

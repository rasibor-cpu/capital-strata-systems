from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from backend.learning.common import FACTORS, factor_scores, factor_weights, outcome, rows, unavailable
from backend.portfolio.utils import advisory_response


class FactorAttributionEngine:
    """Attribute realized advisory outcomes to weighted factor evidence."""

    def attribute(self, history: Iterable[Mapping[str, Any]] | None) -> dict[str, Any]:
        records = rows(history)
        attribution = {factor: {"contribution": 0.0, "sample_size": 0} for factor in FACTORS}
        usable_rows = 0

        for row in records:
            realized = outcome(row)
            scores = factor_scores(row)
            if realized is None or not scores:
                continue
            usable_rows += 1
            weights = factor_weights(row)
            for factor, score in scores.items():
                centered = (score - 50.0) / 50.0
                contribution = realized * centered * (weights.get(factor, 0.0) / 100.0)
                attribution[factor]["contribution"] += contribution
                attribution[factor]["sample_size"] += 1

        if usable_rows == 0:
            return unavailable(
                "factor_attribution_history_unavailable",
                factor_attribution={},
                dominant_factor="DATA UNAVAILABLE",
                total_attributed_return=0.0,
            )

        payload: dict[str, dict[str, Any]] = {}
        for factor, values in attribution.items():
            sample_size = int(values["sample_size"])
            contribution = float(values["contribution"])
            payload[factor] = {
                "sample_size": sample_size,
                "total_contribution": round(contribution, 6),
                "average_contribution": round(contribution / sample_size, 6) if sample_size else 0.0,
            }
        dominant = max(payload, key=lambda factor: abs(payload[factor]["total_contribution"]))
        return advisory_response(
            "OK" if all(payload[factor]["sample_size"] for factor in FACTORS) else "PARTIAL",
            factor_attribution=payload,
            dominant_factor=dominant,
            total_attributed_return=round(sum(item["total_contribution"] for item in payload.values()), 6),
            attribution_method="score_centered_weighted_outcome",
        )

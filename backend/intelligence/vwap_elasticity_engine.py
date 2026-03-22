from __future__ import annotations

from typing import Dict, List


def clamp01(v: float) -> float:
    if v < 0.0:
        return 0.0
    if v > 1.0:
        return 1.0
    return v


class VWAPElasticityEngine:
    """
    Measures how stretched price is relative to VWAP momentum.

    elasticity = vwap deviation / momentum

    Higher elasticity = greater probability of mean reversion.
    """

    def enrich_rows(self, rows: List[Dict]) -> List[Dict]:

        enriched: List[Dict] = []

        for r in rows:

            vwap_dev_abs = abs(float(r.get("vwap_dev_abs", 0.0)))
            momentum = abs(float(r.get("momentum", 0.0))) + 1e-6

            elasticity = vwap_dev_abs / momentum

            elasticity_score = clamp01(elasticity * 0.6)

            row = dict(r)

            row["vwap_elasticity"] = elasticity
            row["elasticity_score"] = elasticity_score

            enriched.append(row)

        return enriched
from __future__ import annotations

from typing import Dict, List, Any


def _safe(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return default


class SignalClassifier:
    """
    CSS Signal Classification Engine

    Converts raw AI scores into structured signal tiers.

    This allows the system to surface useful signals
    even when scores are moderate.

    Tiers:

        ELITE      >= 0.70
        HIGH       >= 0.45
        STANDARD   >= 0.25
        PASS       <  0.25
    """

    def __init__(self):

        self.elite_threshold = 0.70
        self.high_threshold = 0.45
        self.standard_threshold = 0.25

    def classify(self, rows: List[Dict[str, Any]]):

        enriched = []

        for row in rows:

            score = _safe(
                row.get("score", row.get("final_score", 0.0))
            )

            if score >= self.elite_threshold:
                tier = "ELITE"

            elif score >= self.high_threshold:
                tier = "HIGH"

            elif score >= self.standard_threshold:
                tier = "STANDARD"

            else:
                tier = "PASS"

            new_row = dict(row)
            new_row["signal_tier"] = tier
            new_row["score"] = score

            enriched.append(new_row)

        return enriched
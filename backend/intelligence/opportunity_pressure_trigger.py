from __future__ import annotations

from typing import Dict, List, Any


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        if v is None:
            return default
        return float(v)
    except Exception:
        return default


class OpportunityPressureTrigger:
    """
    Converts strong AI + pressure combinations
    into TRADE decisions.
    """

    def __init__(self):

        # adjustable thresholds
        self.ai_trade_threshold = 0.55
        self.pressure_trade_threshold = 0.50

    def apply(
        self,
        ranked_rows: List[Dict[str, Any]],
        pressure_rows: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:

        pressure_map = {
            str(r.get("symbol", "")): r
            for r in pressure_rows
        }

        updated: List[Dict[str, Any]] = []

        for row in ranked_rows:

            symbol = str(row.get("symbol", ""))

            ai_score = _safe_float(row.get("score"))

            pressure_score = _safe_float(
                pressure_map.get(symbol, {}).get("pressure_score")
            )

            decision = str(row.get("decision", "IGNORE"))

            if (
                ai_score >= self.ai_trade_threshold
                and pressure_score >= self.pressure_trade_threshold
            ):
                decision = "TRADE"

            new_row = dict(row)
            new_row["decision"] = decision
            new_row["pressure_score"] = pressure_score

            updated.append(new_row)

        return updated
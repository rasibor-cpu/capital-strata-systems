from __future__ import annotations
from typing import List, Dict, Any


class CapitalAllocator:
    """
    Converts AI opportunity scores into capital allocations.
    Uses a simple AI score + volatility awareness model.
    """

    def __init__(self, total_capital: float, max_positions: int = 5) -> None:
        self.total_capital = float(total_capital)
        self.max_positions = int(max_positions)

    def _base_weight(self, ai_score: float) -> float:
        """
        Convert AI score (0–100) into a base weight.
        """
        if ai_score >= 90:
            return 1.0
        if ai_score >= 80:
            return 0.8
        if ai_score >= 70:
            return 0.6
        if ai_score >= 60:
            return 0.4
        return 0.0

    def allocate(
        self,
        ai_results: List[Dict[str, Any]],
        market_rows: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:

        rows_by_symbol = {r["asset"]: r for r in market_rows}

        candidates: List[Dict[str, Any]] = []

        for item in ai_results:

            symbol = item.get("symbol")
            ai_score = float(item.get("opportunity_score", 0))

            if symbol not in rows_by_symbol:
                continue

            row = rows_by_symbol[symbol]

            spread = abs(float(row.get("spread_bps", 0)))

            base = self._base_weight(ai_score)

            if base == 0:
                continue

            # volatility dampener
            vol_adj = 1.0

            if spread > 500:
                vol_adj = 0.4
            elif spread > 300:
                vol_adj = 0.6
            elif spread > 150:
                vol_adj = 0.8

            weight = base * vol_adj

            candidates.append(
                {
                    "symbol": symbol,
                    "score": ai_score,
                    "weight": weight,
                }
            )

        candidates.sort(key=lambda x: x["weight"], reverse=True)

        candidates = candidates[: self.max_positions]

        total_weight = sum(c["weight"] for c in candidates)

        if total_weight == 0:
            return []

        allocations: List[Dict[str, Any]] = []

        for c in candidates:

            capital = (c["weight"] / total_weight) * self.total_capital

            allocations.append(
                {
                    "symbol": c["symbol"],
                    "ai_score": c["score"],
                    "capital": round(capital, 2),
                }
            )

        return allocations
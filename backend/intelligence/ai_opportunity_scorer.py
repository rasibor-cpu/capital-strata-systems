from __future__ import annotations

from typing import Any, Dict


class AIOpportunityScorer:
    """
    CSS AI Opportunity Scorer (Stabilized + Non-Zero Output)

    Purpose:
    - Ensure non-zero signal generation
    - Normalize feature usage
    - Avoid dead-engine conditions
    """

    def _safe(self, v: Any) -> float:
        try:
            return float(v)
        except Exception:
            return 0.0

    def _clamp(self, v: float, lo: float = 0.0, hi: float = 1.0) -> float:
        return max(lo, min(v, hi))

    def score(self, row: Dict[str, Any]) -> float:

        # === EXTRACT FEATURES SAFELY ===
        momentum = abs(self._safe(row.get("momentum", row.get("momentum_window", 0.0))))
        volatility = self._safe(row.get("volatility", 0.0))
        compression = self._safe(row.get("price_compression", row.get("compression", 0.0)))
        vwap_dev = abs(self._safe(row.get("vwap_dev", 0.0)))
        pressure = self._safe(row.get("pressure_score", 0.0))
        confluence = self._safe(row.get("confluence_score", 0.0))

        # === NORMALIZATION ===
        momentum = self._clamp(momentum * 5.0)
        volatility = self._clamp(volatility * 10.0)
        vwap_dev = self._clamp(vwap_dev * 20.0)
        compression = self._clamp(compression)
        pressure = self._clamp(pressure)
        confluence = self._clamp(confluence)

        # === CORE SCORING MODEL ===
        score = (
            momentum * 0.25
            + volatility * 0.15
            + vwap_dev * 0.20
            + compression * 0.10
            + pressure * 0.15
            + confluence * 0.15
        )

        # === SAFETY FLOOR (CRITICAL) ===
        if score == 0.0:
            # inject minimal signal to avoid dead engine
            score = 0.05 + (vwap_dev * 0.1)

        return round(self._clamp(score), 6)
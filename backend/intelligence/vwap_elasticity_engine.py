from __future__ import annotations

from typing import Any, Dict, List
from backend.common.numeric_utils import clamp, safe_float


def clamp01(v: float) -> float:
    return clamp(v, 0.0, 1.0)


def _safe_float(v: Any, default: float = 0.0) -> float:
    return safe_float(v, default=default)


class VWAPElasticityEngine:
    """
    CSS VWAP Elasticity Engine

    Measures how strongly price is reverting toward VWAP.

    Supports:
    - compute(row) for dashboard/orchestrator use
    - enrich_row(row)
    - enrich_rows(rows)

    Outputs:
    - vwap_elasticity (raw)
    - elasticity_score (0 to 1 normalized)
    """

    def _extract_close(self, candle: Any) -> float:
        if isinstance(candle, dict):
            return _safe_float(candle.get("close", candle.get("c", 0.0)), 0.0)

        if isinstance(candle, (list, tuple)) and len(candle) >= 5:
            return _safe_float(candle[4], 0.0)

        if hasattr(candle, "close"):
            return _safe_float(getattr(candle, "close"), 0.0)

        return _safe_float(candle, 0.0)

    def _compute_from_candles(self, row: Dict[str, Any]) -> Dict[str, float]:
        candles: List[Any] = row.get("candles", []) or []
        vwap = _safe_float(row.get("vwap", 0.0), 0.0)

        if len(candles) < 5 or vwap <= 0:
            return {"vwap_elasticity": 0.0, "elasticity_score": 0.0}

        closes = [self._extract_close(c) for c in candles[-5:]]
        if len(closes) < 5 or any(c <= 0 for c in closes):
            return {"vwap_elasticity": 0.0, "elasticity_score": 0.0}

        distances = [c - vwap for c in closes]

        contraction = 0.0
        observations = 0

        for i in range(1, len(distances)):
            prev = abs(distances[i - 1])
            curr = abs(distances[i])

            if prev > 0:
                contraction += max(0.0, (prev - curr) / prev)
                observations += 1

        if observations == 0:
            return {"vwap_elasticity": 0.0, "elasticity_score": 0.0}

        contraction /= observations
        elasticity = contraction
        elasticity_score = clamp01(elasticity * 2.5)

        return {
            "vwap_elasticity": round(elasticity, 6),
            "elasticity_score": round(elasticity_score, 6),
        }

    def _compute_from_fields(self, row: Dict[str, Any]) -> Dict[str, float]:
        vwap_dev_abs = abs(
            _safe_float(
                row.get("vwap_dev_abs", row.get("vwap_dev", row.get("vwap_distance", 0.0))),
                0.0,
            )
        )
        momentum = abs(
            _safe_float(
                row.get("momentum", row.get("momentum_window", 0.0)),
                0.0,
            )
        ) + 1e-6

        elasticity = vwap_dev_abs / momentum
        elasticity_score = clamp01(elasticity * 0.6)

        return {
            "vwap_elasticity": round(elasticity, 6),
            "elasticity_score": round(elasticity_score, 6),
        }

    def compute(self, row: Dict[str, Any]) -> float:
        if row.get("candles"):
            result = self._compute_from_candles(row)
        else:
            result = self._compute_from_fields(row)

        return float(result.get("elasticity_score", 0.0))

    def enrich_row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        enriched = dict(row)

        if row.get("candles"):
            result = self._compute_from_candles(row)
        else:
            result = self._compute_from_fields(row)

        enriched["vwap_elasticity"] = result["vwap_elasticity"]
        enriched["elasticity_score"] = result["elasticity_score"]
        return enriched

    def enrich_rows(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [self.enrich_row(r) for r in rows]
from __future__ import annotations

from typing import Any, Dict, List


def _safe(v: Any, d: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return d


class QuantSignalOptimizer:
    """
    CSS Quant Signal Optimizer
    v2.5 - Controlled Activation (Build-up Promotion)

    Purpose:
    - keep exhaustion blocked
    - allow stronger BUILDUP states to promote from WATCH to QUALIFIED
    - preserve backward compatibility
    """

    def optimize(self, payload: Any) -> Any:
        if isinstance(payload, list):
            optimized_rows: List[Dict[str, Any]] = []
            for row in payload:
                if not isinstance(row, dict):
                    continue

                decision = self._run_logic(row)

                new_row = dict(row)
                new_row["optimizer_tier"] = decision["tier"]
                new_row["optimizer_score"] = decision["score"]
                new_row["optimizer_reason"] = decision["reason"]

                optimized_rows.append(new_row)

            optimized_rows.sort(
                key=lambda r: _safe(r.get("optimizer_score", 0.0)), reverse=True
            )
            return optimized_rows

        if isinstance(payload, dict):
            return self._run_logic(payload)

        return []

    def evaluate(self, row: Dict[str, Any]) -> Dict[str, Any]:
        return self._run_logic(row)

    def _run_logic(self, row: Dict[str, Any]) -> Dict[str, Any]:
        ai_score = _safe(row.get("ai_score"))
        confluence = _safe(row.get("confluence_score"))
        pressure = _safe(row.get("pressure_score"))

        pressure_type = str(row.get("pressure_type", "BUILDUP") or "BUILDUP").upper()
        pressure_quality = str(
            row.get("pressure_trade_quality", "LOW") or "LOW"
        ).upper()

        pressure_boost = 1.0 + (pressure * 0.80)
        adjusted_score = ai_score * pressure_boost

        if pressure_type == "EXHAUSTION":
            return self._decision("IGNORE", adjusted_score, "exhaustion_zone")

        effective_quality = pressure_quality
        if (
            effective_quality == "LOW"
            and pressure_type == "BUILDUP"
            and pressure >= 0.17
            and ai_score >= 0.09
        ):
            effective_quality = "MEDIUM"

        # ELITE
        if (
            adjusted_score >= 0.125
            and pressure >= 0.21
            and confluence >= 0.16
            and effective_quality in ("HIGH", "MEDIUM")
        ):
            return self._decision("ELITE", adjusted_score, "high_quality_buildup")

        # QUALIFIED
        if (
            adjusted_score >= 0.10
            and pressure >= 0.17
            and confluence >= 0.12
            and effective_quality in ("HIGH", "MEDIUM")
        ):
            return self._decision("QUALIFIED", adjusted_score, "valid_buildup_signal")

        # fallback qualified for strong build-up even when confluence is only modest
        if (
            adjusted_score >= 0.108
            and pressure >= 0.20
            and pressure_type == "BUILDUP"
            and effective_quality == "MEDIUM"
        ):
            return self._decision("QUALIFIED", adjusted_score, "strong_buildup_override")

        # WATCH
        if adjusted_score >= 0.08 and pressure >= 0.15:
            return self._decision("WATCH", adjusted_score, "developing_signal")

        if effective_quality == "LOW":
            return self._decision("IGNORE", adjusted_score, "low_pressure_quality")

        return self._decision("IGNORE", adjusted_score, "below_threshold")

    def _decision(self, tier: str, score: float, reason: str) -> Dict[str, Any]:
        return {
            "tier": tier,
            "score": round(score, 6),
            "reason": reason,
        }
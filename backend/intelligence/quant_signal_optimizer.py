from __future__ import annotations

from typing import Any, Dict, List, Optional


class QuantSignalOptimizer:
    """
    CSS Quant Signal Optimizer
    Mode-aware, backward-compatible, scaled for the current live dashboard.

    Goals:
    - produce non-zero trade_score
    - align thresholds with current score ranges
    - preserve optimize(rows) compatibility
    - support classify(row) for dashboard use
    """

    DEFAULT_PROFILE = {
        "elite": 0.22,
        "qualified": 0.14,
        "watch": 0.09,
        "min_confluence_elite": 0.10,
        "min_pressure_elite": 0.05,
        "min_confluence_qualified": 0.05,
    }

    def __init__(self, profile: Optional[Dict[str, float]] = None) -> None:
        merged = dict(self.DEFAULT_PROFILE)
        if isinstance(profile, dict):
            merged.update(profile)

        # Preserve dashboard mode thresholds only if they are realistic.
        # If mode thresholds are very high for the current score scale, cap them.
        elite = float(merged.get("elite", 0.22))
        qualified = float(merged.get("qualified", 0.14))
        watch = float(merged.get("watch", 0.09))

        self.elite_threshold = min(elite, 0.22)
        self.trade_threshold = min(qualified, 0.14)
        self.watch_threshold = min(watch, 0.09)

        self.min_confluence_elite = float(merged.get("min_confluence_elite", 0.10))
        self.min_pressure_elite = float(merged.get("min_pressure_elite", 0.05))
        self.min_confluence_qualified = float(merged.get("min_confluence_qualified", 0.05))

        self.profile = merged

    def _safe(self, value: Any) -> float:
        try:
            return float(value)
        except Exception:
            return 0.0

    def _clamp01(self, value: float) -> float:
        if value < 0.0:
            return 0.0
        if value > 1.0:
            return 1.0
        return value

    def _get_pressure(self, row: Dict[str, Any]) -> float:
        return self._safe(
            row.get("pressure_score")
            or row.get("pressure")
            or row.get("opportunity_pressure")
        )

    def _get_confluence(self, row: Dict[str, Any]) -> float:
        return self._safe(
            row.get("confluence_score")
            or row.get("confluence")
            or row.get("signal_confluence")
        )

    def _get_accel(self, row: Dict[str, Any]) -> float:
        return self._safe(
            row.get("pressure_acceleration")
            or row.get("acceleration_score")
            or row.get("accel")
        )

    def _get_score(self, row: Dict[str, Any]) -> float:
        return self._safe(
            row.get("score")
            or row.get("ai_score")
            or row.get("opportunity_score")
            or row.get("decision_score")
        )

    def _get_vwap_dev(self, row: Dict[str, Any]) -> float:
        return abs(
            self._safe(
                row.get("vwap_dev")
                or row.get("vwap_distance")
                or row.get("vwap_deviation")
            )
        )

    def _normalize_spread(self, spread_bps: float) -> float:
        spread = abs(self._safe(spread_bps))
        if spread >= 900:
            return 10.0
        return spread

    def _regime_bonus(self, regime: str) -> float:
        r = str(regime).upper()

        if "MEAN" in r:
            return 0.020
        if "RANGE" in r:
            return 0.015
        if "TREND" in r:
            return 0.012
        if "BREAKOUT" in r:
            return 0.010
        if "VOLATILE" in r:
            return 0.008
        if "CRYPTO" in r:
            return 0.006
        if "FX" in r:
            return 0.005
        if "FUTURES" in r:
            return 0.005
        return 0.0

    def _spread_penalty(self, spread_bps: float) -> float:
        spread = self._normalize_spread(spread_bps)

        if spread >= 20:
            return 0.050
        if spread >= 15:
            return 0.035
        if spread >= 10:
            return 0.020
        if spread >= 6:
            return 0.010
        return 0.003

    def _tier(
        self,
        trade_score: float,
        pressure: float,
        accel: float,
        confluence: float,
    ) -> str:
        if (
            trade_score >= self.elite_threshold
            and confluence >= self.min_confluence_elite
            and pressure >= self.min_pressure_elite
        ):
            return "ELITE"

        if (
            trade_score >= self.trade_threshold
            and confluence >= self.min_confluence_qualified
        ):
            return "QUALIFIED"

        if trade_score >= self.watch_threshold:
            return "WATCH"

        return "IGNORE"

    def enrich_row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        enriched = dict(row)

        score = self._get_score(row)
        pressure = self._get_pressure(row)
        confluence = self._get_confluence(row)
        accel = self._get_accel(row)
        vwap_dev = self._get_vwap_dev(row)
        spread = self._normalize_spread(row.get("spread_bps", 0.0))
        regime = str(row.get("regime", "NEUTRAL")).upper()

        # Current environment has low-to-mid raw scores, so use a lighter fusion model.
        trade_score = (
            score * 0.65
            + confluence * 0.12
            + pressure * 0.10
            + accel * 0.05
            + min(vwap_dev * 6.0, 0.08)
        )

        trade_score += self._regime_bonus(regime)
        trade_score -= self._spread_penalty(spread)
        trade_score = self._clamp01(trade_score)

        signal_tier = self._tier(
            trade_score=trade_score,
            pressure=pressure,
            accel=accel,
            confluence=confluence,
        )

        if signal_tier in {"ELITE", "QUALIFIED"}:
            decision = "TRADE"
        elif signal_tier == "WATCH":
            decision = "WATCH"
        else:
            decision = "IGNORE"

        enriched["score"] = score
        enriched["pressure_score"] = pressure
        enriched["confluence_score"] = confluence
        enriched["pressure_acceleration"] = accel
        enriched["trade_score"] = round(trade_score, 6)
        enriched["signal_tier"] = signal_tier
        enriched["decision"] = decision
        enriched["spread_bps"] = spread
        enriched["regime"] = regime

        return enriched

    def classify(self, row: Dict[str, Any]) -> str:
        enriched = self.enrich_row(row)

        # Mutate input row too, so the dashboard can print trade_score immediately.
        try:
            row.update(enriched)
        except Exception:
            pass

        return str(enriched.get("signal_tier", "IGNORE"))

    def optimize(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        optimized: List[Dict[str, Any]] = []

        for row in rows:
            enriched = self.enrich_row(row)

            print(
                f"[{enriched['signal_tier']}] {enriched.get('symbol', 'UNKNOWN')}: "
                f"score={float(enriched.get('score', 0.0)):.6f}, "
                f"confluence={float(enriched.get('confluence_score', 0.0)):.6f}, "
                f"pressure={float(enriched.get('pressure_score', 0.0)):.6f}, "
                f"accel={float(enriched.get('pressure_acceleration', 0.0)):.6f}, "
                f"spread={float(enriched.get('spread_bps', 0.0)):.6f}, "
                f"trade_score={float(enriched.get('trade_score', 0.0)):.6f}, "
                f"regime={enriched.get('regime', 'NEUTRAL')}"
            )

            optimized.append(enriched)

        optimized.sort(
            key=lambda x: float(x.get("trade_score", 0.0)),
            reverse=True,
        )

        return optimized
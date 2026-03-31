from __future__ import annotations

from typing import Any, Dict, List


class QuantSignalOptimizer:
    """
    CSS Quant Signal Optimizer (Robust Version)

    FIXES:
    - Preserves signal fields even if ranking drops them
    - Reads from ALL possible field aliases
    - Injects missing values safely
    - No regression to scoring logic
    """

    def __init__(self) -> None:
        self.elite_threshold = 0.52
        self.trade_threshold = 0.44
        self.watch_threshold = 0.28

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

    # 🔥 NEW: robust field extraction
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
            or row.get("accel")
            or row.get("acceleration_score")
        )

    def _regime_bonus(self, regime: str) -> float:
        r = str(regime).upper()

        if "MEAN" in r:
            return 0.03
        if "RANGE" in r:
            return 0.025
        if "TREND" in r:
            return 0.02
        if "BREAKOUT" in r:
            return 0.02
        if "VOLATILE" in r:
            return 0.01
        if "NEUTRAL" in r:
            return 0.01
        if "DEFENSIVE" in r or "PANIC" in r:
            return -0.05
        return 0.0

    def _spread_bonus(self, spread_bps: float) -> float:
        spread = abs(spread_bps)

        if spread >= 60:
            return 0.08
        if spread >= 40:
            return 0.06
        if spread >= 25:
            return 0.04
        if spread >= 15:
            return 0.025
        if spread >= 8:
            return 0.01
        return 0.0

    def _tier(self, trade_score: float, pressure: float, accel: float, confluence: float) -> str:
        if (
            trade_score >= self.elite_threshold
            and confluence >= 0.80
            and pressure >= 0.24
        ):
            return "ELITE"

        if (
            trade_score >= self.trade_threshold
            and confluence >= 0.78
        ):
            return "QUALIFIED"

        if trade_score >= self.watch_threshold:
            return "WATCH"

        return "IGNORE"

    def optimize(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        optimized: List[Dict[str, Any]] = []

        for row in rows:
            symbol = str(row.get("symbol", "")).upper()

            score = self._safe(row.get("score", 0.0))
            base_ai_score = self._safe(row.get("base_ai_score", 0.0))

            # 🔥 FIX: robust extraction
            pressure = self._get_pressure(row)
            accel = self._get_accel(row)
            confluence = self._get_confluence(row)

            spread = abs(self._safe(row.get("spread_bps", 0.0)))
            regime = str(row.get("regime", "NEUTRAL")).upper()

            # 🔥 CORE SCORING (UNCHANGED)
            trade_score = (
                score * 0.42
                + confluence * 0.23
                + pressure * 0.20
                + accel * 0.10
                + base_ai_score * 0.05
            )

            trade_score += self._spread_bonus(spread)
            trade_score += self._regime_bonus(regime)

            trade_score = self._clamp01(trade_score)

            tier = self._tier(
                trade_score=trade_score,
                pressure=pressure,
                accel=accel,
                confluence=confluence,
            )

            if tier in {"ELITE", "QUALIFIED"}:
                decision = "TRADE"
            elif tier == "WATCH":
                decision = "WATCH"
            else:
                decision = "IGNORE"

            enriched = dict(row)

            # 🔥 IMPORTANT: re-inject values so downstream sees them
            enriched["pressure_score"] = pressure
            enriched["confluence_score"] = confluence
            enriched["pressure_acceleration"] = accel

            enriched["symbol"] = symbol
            enriched["trade_score"] = trade_score
            enriched["signal_tier"] = tier
            enriched["decision"] = decision

            print(
                f"[{tier}] {symbol}: "
                f"base={base_ai_score:.6f}, "
                f"score={score:.6f}, "
                f"confluence={confluence:.6f}, "
                f"pressure={pressure:.6f}, "
                f"accel={accel:.6f}, "
                f"spread={spread:.6f}, "
                f"trade_score={trade_score:.6f}, "
                f"regime={regime}"
            )

            optimized.append(enriched)

        optimized.sort(
            key=lambda x: float(x.get("trade_score", 0.0)),
            reverse=True,
        )

        return optimized
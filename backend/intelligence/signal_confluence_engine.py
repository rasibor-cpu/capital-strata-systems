from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, List
import statistics


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _clamp01(value: float) -> float:
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


@dataclass
class ConfluenceDecision:
    allow_trade: bool
    confluence_score: float
    passed_checks: int
    total_checks: int
    reason: str
    details: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class SignalConfluenceEngine:
    """
    CSS Signal Confluence Engine

    Purpose:
    - approve trades only when multiple conditions align
    - support both candle-only evaluation and row-based pipeline enrichment
    - combine market structure with live CSS intelligence features

    Confluence dimensions:
    1. Candle deviation / setup structure
    2. Volatility suitability
    3. Momentum moderation
    4. Volume / liquidity floor
    5. Last candle extension control
    6. Pressure alignment
    7. Pressure acceleration alignment
    8. Regime suitability
    9. Spread location suitability
    """

    def __init__(self) -> None:
        self.min_candles = 20

        # Base candle thresholds
        self.min_deviation_from_ma = 0.0015
        self.max_volatility = 0.05
        self.max_momentum_5 = 0.0045
        self.min_avg_volume_10 = 200.0
        self.max_last_candle_extension = 0.80

        # Live row thresholds
        self.min_pressure_score = 0.12
        self.min_pressure_acceleration = 0.03
        self.min_abs_spread_bps = 8.0

        # Row-based required checks
        self.min_required_checks_row = 3

        # Candle-only required checks
        self.min_required_checks_candles = 4

        self.allowed_regimes = {
            "MEAN_REVERSION",
            "TREND",
            "VOLATILE",
            "NEUTRAL",
            "BREAKOUT",
        }

    # ------------------------------------------------
    # CANDLE-ONLY EVALUATION
    # ------------------------------------------------

    def evaluate(self, candles: List[Dict[str, Any]]) -> ConfluenceDecision:
        if not candles or len(candles) < self.min_candles:
            return ConfluenceDecision(
                allow_trade=False,
                confluence_score=0.0,
                passed_checks=0,
                total_checks=5,
                reason="Insufficient candle data for confluence check",
                details={},
            )

        try:
            opens = [float(c["open"]) for c in candles]
            highs = [float(c["high"]) for c in candles]
            lows = [float(c["low"]) for c in candles]
            closes = [float(c["close"]) for c in candles]
            volumes = [float(c.get("volume", 0.0)) for c in candles]
        except (KeyError, TypeError, ValueError):
            return ConfluenceDecision(
                allow_trade=False,
                confluence_score=0.0,
                passed_checks=0,
                total_checks=5,
                reason="Invalid candle format supplied",
                details={},
            )

        ma20 = statistics.mean(closes[-20:])
        if ma20 == 0:
            return ConfluenceDecision(
                allow_trade=False,
                confluence_score=0.0,
                passed_checks=0,
                total_checks=5,
                reason="Invalid moving average calculation",
                details={},
            )

        last_price = closes[-1]
        deviation_from_ma = abs((last_price - ma20) / ma20)
        volatility_20 = (max(highs[-20:]) - min(lows[-20:])) / ma20
        avg_volume_10 = statistics.mean(volumes[-10:])
        momentum_5 = abs(closes[-1] - closes[-5]) / ma20

        last_open = opens[-1]
        last_high = highs[-1]
        last_low = lows[-1]
        last_close = closes[-1]

        candle_range = max(last_high - last_low, 1e-12)
        candle_body = abs(last_close - last_open)
        last_candle_extension = candle_body / candle_range

        checks = {
            "deviation_from_ma": deviation_from_ma >= self.min_deviation_from_ma,
            "volatility_ok": volatility_20 <= self.max_volatility,
            "momentum_slowing": momentum_5 <= self.max_momentum_5,
            "volume_ok": avg_volume_10 >= self.min_avg_volume_10,
            "last_candle_not_extended": last_candle_extension <= self.max_last_candle_extension,
        }

        passed_checks = sum(1 for passed in checks.values() if passed)
        total_checks = len(checks)
        confluence_score = round(passed_checks / total_checks, 4)
        allow_trade = passed_checks >= self.min_required_checks_candles

        reason = (
            "Signal confluence confirmed"
            if allow_trade
            else "Signal confluence too weak"
        )

        details = {
            "ma20": round(ma20, 8),
            "last_price": round(last_price, 8),
            "deviation_from_ma": round(deviation_from_ma, 8),
            "volatility_20": round(volatility_20, 8),
            "avg_volume_10": round(avg_volume_10, 4),
            "momentum_5": round(momentum_5, 8),
            "last_candle_extension": round(last_candle_extension, 8),
            "checks": checks,
        }

        return ConfluenceDecision(
            allow_trade=allow_trade,
            confluence_score=confluence_score,
            passed_checks=passed_checks,
            total_checks=total_checks,
            reason=reason,
            details=details,
        )

    # ------------------------------------------------
    # LIVE ROW PIPELINE ENTRY
    # ------------------------------------------------

    def enrich_rows(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        enriched: List[Dict[str, Any]] = []

        for row in rows:
            new_row = dict(row)

            candles = row.get("candles", [])
            candle_decision = self.evaluate(candles) if isinstance(candles, list) else None

            candle_score = (
                _safe_float(candle_decision.confluence_score, 0.0)
                if candle_decision is not None
                else 0.0
            )

            pressure_score = _safe_float(row.get("pressure_score"), 0.0)
            pressure_acceleration = _safe_float(row.get("pressure_acceleration"), 0.0)
            spread_bps = abs(_safe_float(row.get("spread_bps"), 0.0))
            regime = str(row.get("regime", "NEUTRAL")).upper()

            row_checks = {
                "candle_structure_ok": candle_score >= 0.60,
                "pressure_ok": pressure_score >= self.min_pressure_score,
                "acceleration_ok": pressure_acceleration >= self.min_pressure_acceleration,
                "spread_ok": spread_bps >= self.min_abs_spread_bps,
                "regime_ok": regime in self.allowed_regimes,
                "high_conviction_setup": (
                    pressure_score >= 0.25
                    or pressure_acceleration >= 0.15
                    or spread_bps >= 25.0
                ),
            }

            passed_row_checks = sum(1 for passed in row_checks.values() if passed)
            total_row_checks = len(row_checks)

            row_confluence_score = (
                passed_row_checks / total_row_checks if total_row_checks > 0 else 0.0
            )

            # Final blended confluence score:
            # 60% candle structure, 40% live signal alignment
            final_confluence_score = _clamp01(
                candle_score * 0.60 + row_confluence_score * 0.40
            )

            allow_trade = passed_row_checks >= self.min_required_checks_row

            new_row["confluence_score"] = round(final_confluence_score, 4)
            new_row["confluence_passed_checks"] = passed_row_checks
            new_row["confluence_total_checks"] = total_row_checks
            new_row["confluence_allow_trade"] = allow_trade
            new_row["confluence_reason"] = (
                "row and candle confluence aligned"
                if allow_trade
                else "confluence below trading threshold"
            )
            new_row["confluence_details"] = {
                "candle_score": round(candle_score, 4),
                "pressure_score": round(pressure_score, 4),
                "pressure_acceleration": round(pressure_acceleration, 4),
                "spread_bps_abs": round(spread_bps, 4),
                "regime": regime,
                "checks": row_checks,
            }

            enriched.append(new_row)

        enriched.sort(
            key=lambda x: float(x.get("confluence_score", 0.0)),
            reverse=True,
        )

        return enriched

    # ------------------------------------------------
    # COMPATIBILITY ALIASES
    # ------------------------------------------------

    def enrich(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return self.enrich_rows(rows)

    def compute_confluence(
        self,
        *,
        asset: str,
        candles: List[Dict[str, Any]],
        regime: str | None = None,
    ) -> Dict[str, Any]:
        result = self.evaluate(candles)
        payload = result.to_dict()
        if regime is not None:
            payload["regime"] = str(regime).upper()
        payload["asset"] = asset
        payload["score"] = result.confluence_score
        return payload


if __name__ == "__main__":
    sample_candles = [
        {"open": 1.0810, "high": 1.0820, "low": 1.0800, "close": 1.0814, "volume": 900},
        {"open": 1.0814, "high": 1.0821, "low": 1.0805, "close": 1.0810, "volume": 920},
        {"open": 1.0810, "high": 1.0817, "low": 1.0802, "close": 1.0807, "volume": 940},
        {"open": 1.0807, "high": 1.0813, "low": 1.0799, "close": 1.0804, "volume": 960},
        {"open": 1.0804, "high": 1.0810, "low": 1.0796, "close": 1.0801, "volume": 980},
        {"open": 1.0801, "high": 1.0808, "low": 1.0793, "close": 1.0798, "volume": 1000},
        {"open": 1.0798, "high": 1.0805, "low": 1.0791, "close": 1.0796, "volume": 1020},
        {"open": 1.0796, "high": 1.0803, "low": 1.0789, "close": 1.0794, "volume": 1040},
        {"open": 1.0794, "high": 1.0801, "low": 1.0788, "close": 1.0792, "volume": 1060},
        {"open": 1.0792, "high": 1.0799, "low": 1.0786, "close": 1.0790, "volume": 1080},
        {"open": 1.0790, "high": 1.0798, "low": 1.0785, "close": 1.0789, "volume": 1100},
        {"open": 1.0789, "high": 1.0797, "low": 1.0784, "close": 1.0788, "volume": 1120},
        {"open": 1.0788, "high": 1.0796, "low": 1.0783, "close": 1.0787, "volume": 1140},
        {"open": 1.0787, "high": 1.0795, "low": 1.0782, "close": 1.0786, "volume": 1160},
        {"open": 1.0786, "high": 1.0794, "low": 1.0781, "close": 1.0785, "volume": 1180},
        {"open": 1.0785, "high": 1.0793, "low": 1.0780, "close": 1.0784, "volume": 1200},
        {"open": 1.0784, "high": 1.0792, "low": 1.0779, "close": 1.0783, "volume": 1220},
        {"open": 1.0783, "high": 1.0791, "low": 1.0778, "close": 1.0782, "volume": 1240},
        {"open": 1.0782, "high": 1.0790, "low": 1.0777, "close": 1.0781, "volume": 1260},
        {"open": 1.0781, "high": 1.0787, "low": 1.0776, "close": 1.0780, "volume": 1280},
    ]

    engine = SignalConfluenceEngine()
    result = engine.evaluate(sample_candles)
    print(result.to_dict())
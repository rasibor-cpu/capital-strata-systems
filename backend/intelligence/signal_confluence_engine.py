from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, List
import statistics


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

    Approves trades only when multiple conditions align.

    Checks:
    1. Price sufficiently deviated from MA20
    2. Volatility not excessive
    3. Short-term momentum slowing
    4. Liquidity / average volume acceptable
    5. Last candle shows reduced directional extension
    """

    def __init__(self) -> None:
        self.min_candles = 20
        self.min_required_checks = 4

        self.min_deviation_from_ma = 0.0015
        self.max_volatility = 0.03
        self.max_momentum_5 = 0.0025
        self.min_avg_volume_10 = 500.0
        self.max_last_candle_extension = 0.006

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
        allow_trade = passed_checks >= self.min_required_checks

        if allow_trade:
            reason = "Signal confluence confirmed"
        else:
            reason = "Signal confluence too weak"

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
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional
import statistics

from backend.intelligence.regime_intelligence_engine import (
    RegimeDecision,
    RegimeIntelligenceEngine,
)


@dataclass
class ScanCandidate:
    symbol: str
    asset_class: str
    score: float
    regime_allowed: bool
    regime: str
    reason: str
    last_price: float
    moving_average_20: float
    deviation_from_ma: float
    volatility_20: float
    avg_volume_10: float
    momentum_5: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class GlobalMarketScanner:
    """
    CSS Global Market Scanner

    Scans multiple assets across asset classes and ranks the best
    mean-reversion opportunities, while filtering out bad regimes.

    Expected input structure:

    market_data = {
        "EUR_USD": {
            "asset_class": "forex",
            "candles": [
                {"open": 1.0810, "high": 1.0820, "low": 1.0805, "close": 1.0815, "volume": 1000},
                ...
            ]
        },
        "BTC-USD": {
            "asset_class": "crypto",
            "candles": [...]
        }
    }
    """

    def __init__(
        self,
        top_n: int = 5,
        min_candles: int = 20,
    ) -> None:
        self.top_n = top_n
        self.min_candles = min_candles
        self.regime_engine = RegimeIntelligenceEngine()

    def scan_market_data(
        self,
        market_data: Dict[str, Dict[str, Any]],
    ) -> List[ScanCandidate]:
        """
        Scan all supplied symbols and return top-ranked opportunities.
        """
        candidates: List[ScanCandidate] = []

        for symbol, payload in market_data.items():
            asset_class = str(payload.get("asset_class", "unknown")).lower()
            candles = payload.get("candles", [])

            candidate = self._evaluate_symbol(
                symbol=symbol,
                asset_class=asset_class,
                candles=candles,
            )
            if candidate is not None:
                candidates.append(candidate)

        ranked = sorted(candidates, key=lambda x: x.score, reverse=True)
        return ranked[: self.top_n]

    def scan_to_dicts(
        self,
        market_data: Dict[str, Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Convenience wrapper for downstream UI / JSON rendering.
        """
        return [candidate.to_dict() for candidate in self.scan_market_data(market_data)]

    def _evaluate_symbol(
        self,
        symbol: str,
        asset_class: str,
        candles: List[Dict[str, Any]],
    ) -> Optional[ScanCandidate]:
        if not candles or len(candles) < self.min_candles:
            return None

        try:
            closes = [float(c["close"]) for c in candles]
            highs = [float(c["high"]) for c in candles]
            lows = [float(c["low"]) for c in candles]
            volumes = [float(c.get("volume", 0.0)) for c in candles]
        except (KeyError, TypeError, ValueError):
            return None

        if len(closes) < self.min_candles:
            return None

        last_price = closes[-1]
        moving_average_20 = statistics.mean(closes[-20:])

        if moving_average_20 == 0:
            return None

        deviation_from_ma = (last_price - moving_average_20) / moving_average_20
        volatility_20 = (max(highs[-20:]) - min(lows[-20:])) / moving_average_20
        avg_volume_10 = statistics.mean(volumes[-10:]) if volumes[-10:] else 0.0
        momentum_5 = closes[-1] - closes[-5]

        regime_decision: RegimeDecision = self.regime_engine.evaluate(candles)

        score = self._compute_opportunity_score(
            deviation_from_ma=deviation_from_ma,
            volatility_20=volatility_20,
            avg_volume_10=avg_volume_10,
            momentum_5=momentum_5,
            regime_allowed=regime_decision.allow_trade,
        )

        return ScanCandidate(
            symbol=symbol,
            asset_class=asset_class,
            score=round(score, 6),
            regime_allowed=regime_decision.allow_trade,
            regime=regime_decision.regime,
            reason=regime_decision.reason,
            last_price=round(last_price, 8),
            moving_average_20=round(moving_average_20, 8),
            deviation_from_ma=round(deviation_from_ma, 8),
            volatility_20=round(volatility_20, 8),
            avg_volume_10=round(avg_volume_10, 4),
            momentum_5=round(momentum_5, 8),
        )

    def _compute_opportunity_score(
        self,
        deviation_from_ma: float,
        volatility_20: float,
        avg_volume_10: float,
        momentum_5: float,
        regime_allowed: bool,
    ) -> float:
        """
        Institutional-style scoring model for mean-reversion suitability.

        Higher score means better opportunity.
        """

        # Larger deviation from MA is good for mean reversion,
        # but only if regime and volatility remain sane.
        deviation_component = min(abs(deviation_from_ma) * 100.0, 5.0)

        # Lower volatility is better for clean reversion.
        volatility_penalty = min(volatility_20 * 100.0, 5.0)

        # Lower active momentum is better for reversion timing.
        momentum_penalty = min(abs(momentum_5) * 100.0, 5.0)

        # Basic liquidity reward. Keeps score positive for actively traded assets.
        liquidity_component = min(avg_volume_10 / 1000.0, 3.0)

        regime_bonus = 3.0 if regime_allowed else -5.0

        raw_score = (
            deviation_component
            + liquidity_component
            + regime_bonus
            - volatility_penalty
            - momentum_penalty
        )

        return max(raw_score, 0.0)


if __name__ == "__main__":
    sample_market_data = {
        "EUR_USD": {
            "asset_class": "forex",
            "candles": [
                {"open": 1.0800, "high": 1.0810, "low": 1.0790, "close": 1.0805, "volume": 1200},
                {"open": 1.0805, "high": 1.0815, "low": 1.0795, "close": 1.0808, "volume": 1100},
                {"open": 1.0808, "high": 1.0818, "low": 1.0800, "close": 1.0812, "volume": 1150},
                {"open": 1.0812, "high": 1.0820, "low": 1.0805, "close": 1.0810, "volume": 1180},
                {"open": 1.0810, "high": 1.0818, "low": 1.0802, "close": 1.0807, "volume": 1170},
                {"open": 1.0807, "high": 1.0815, "low": 1.0799, "close": 1.0803, "volume": 1210},
                {"open": 1.0803, "high": 1.0810, "low": 1.0796, "close": 1.0801, "volume": 1230},
                {"open": 1.0801, "high": 1.0808, "low": 1.0793, "close": 1.0799, "volume": 1245},
                {"open": 1.0799, "high": 1.0806, "low": 1.0792, "close": 1.0797, "volume": 1260},
                {"open": 1.0797, "high": 1.0804, "low": 1.0790, "close": 1.0795, "volume": 1275},
                {"open": 1.0795, "high": 1.0803, "low": 1.0788, "close": 1.0794, "volume": 1280},
                {"open": 1.0794, "high": 1.0801, "low": 1.0787, "close": 1.0792, "volume": 1290},
                {"open": 1.0792, "high": 1.0800, "low": 1.0786, "close": 1.0791, "volume": 1310},
                {"open": 1.0791, "high": 1.0799, "low": 1.0785, "close": 1.0790, "volume": 1325},
                {"open": 1.0790, "high": 1.0798, "low": 1.0784, "close": 1.0789, "volume": 1340},
                {"open": 1.0789, "high": 1.0797, "low": 1.0783, "close": 1.0788, "volume": 1355},
                {"open": 1.0788, "high": 1.0796, "low": 1.0782, "close": 1.0787, "volume": 1365},
                {"open": 1.0787, "high": 1.0795, "low": 1.0781, "close": 1.0786, "volume": 1375},
                {"open": 1.0786, "high": 1.0794, "low": 1.0780, "close": 1.0785, "volume": 1380},
                {"open": 1.0785, "high": 1.0793, "low": 1.0779, "close": 1.0784, "volume": 1395},
            ],
        },
        "BTC-USD": {
            "asset_class": "crypto",
            "candles": [
                {"open": 62000, "high": 62400, "low": 61800, "close": 62200, "volume": 800},
                {"open": 62200, "high": 62600, "low": 62000, "close": 62400, "volume": 780},
                {"open": 62400, "high": 62800, "low": 62200, "close": 62700, "volume": 790},
                {"open": 62700, "high": 63100, "low": 62500, "close": 63000, "volume": 810},
                {"open": 63000, "high": 63400, "low": 62800, "close": 63300, "volume": 820},
                {"open": 63300, "high": 63700, "low": 63100, "close": 63600, "volume": 840},
                {"open": 63600, "high": 64000, "low": 63400, "close": 63900, "volume": 860},
                {"open": 63900, "high": 64300, "low": 63700, "close": 64200, "volume": 880},
                {"open": 64200, "high": 64600, "low": 64000, "close": 64500, "volume": 900},
                {"open": 64500, "high": 64900, "low": 64300, "close": 64800, "volume": 920},
                {"open": 64800, "high": 65200, "low": 64600, "close": 65100, "volume": 940},
                {"open": 65100, "high": 65500, "low": 64900, "close": 65400, "volume": 960},
                {"open": 65400, "high": 65800, "low": 65200, "close": 65700, "volume": 980},
                {"open": 65700, "high": 66100, "low": 65500, "close": 66000, "volume": 990},
                {"open": 66000, "high": 66400, "low": 65800, "close": 66300, "volume": 995},
                {"open": 66300, "high": 66700, "low": 66100, "close": 66600, "volume": 1005},
                {"open": 66600, "high": 67000, "low": 66400, "close": 66900, "volume": 1010},
                {"open": 66900, "high": 67300, "low": 66700, "close": 67200, "volume": 1020},
                {"open": 67200, "high": 67600, "low": 67000, "close": 67500, "volume": 1040},
                {"open": 67500, "high": 67900, "low": 67300, "close": 67800, "volume": 1050},
            ],
        },
    }

    scanner = GlobalMarketScanner(top_n=5)
    results = scanner.scan_to_dicts(sample_market_data)

    for row in results:
        print(row)
from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.engine.signal_engine import SignalEngine


class AIOpportunityScorer:
    """
    CSS AI Opportunity Scorer v1

    This is an AI-style scoring layer built on top of the existing CSS pipeline.
    It does NOT replace:
        - unified scanner
        - opportunity router
        - regime detector
        - strategy selector
        - signal engine

    It consumes the routed + signal-ready opportunities and assigns:
        - opportunity_score (0-100)
        - confidence_band
        - action_priority
        - explanation

    This is rules-driven intelligence for now, designed so we can later
    swap in ML models without breaking the rest of CSS.
    """

    def __init__(self) -> None:
        self.signal_engine = SignalEngine()

    @staticmethod
    def _clamp(value: float, low: float, high: float) -> float:
        return max(low, min(high, value))

    @staticmethod
    def _norm_abs(value: float, scale: float) -> float:
        if scale <= 0:
            return 0.0
        return min(abs(value) / scale, 1.0)

    def _score_components(self, item: Dict[str, Any]) -> Dict[str, float]:
        score = float(item.get("score", 0.0))
        trend = float(item.get("trend_pct", 0.0))
        spread = float(item.get("spread_pct", 0.0))
        vol = float(item.get("volatility_pct", 0.0))
        regime = str(item.get("regime", "MEAN_REVERSION")).upper()
        signal = str(item.get("signal", "HOLD")).upper()
        asset_class = str(item.get("asset_class", "UNKNOWN")).upper()

        # Base model components
        scanner_strength = self._clamp(score / 4.0, 0.0, 1.0)
        trend_strength = self._norm_abs(trend, 1.0)
        spread_strength = self._norm_abs(spread, 5.0)
        volatility_strength = self._norm_abs(vol, 1.0)

        # Regime / strategy alignment
        regime_fit = 0.55
        if regime == "TREND":
            regime_fit = 0.70 + 0.30 * trend_strength
        elif regime == "BREAKOUT":
            regime_fit = 0.65 + 0.35 * volatility_strength
        elif regime == "MEAN_REVERSION":
            regime_fit = 0.65 + 0.35 * spread_strength

        regime_fit = self._clamp(regime_fit, 0.0, 1.0)

        # Signal strength
        signal_strength = 0.25
        if signal == "BUY":
            signal_strength = 1.0
        elif signal == "SELL":
            signal_strength = 0.85
        elif signal == "HOLD":
            signal_strength = 0.20

        # Liquidity / stability preference by asset class
        # Slight discount to smaller crypto names relative to FX majors.
        asset_bias = 1.00
        if asset_class == "CRYPTO":
            asset_bias = 0.94
        elif asset_class == "FX":
            asset_bias = 1.03

        return {
            "scanner_strength": scanner_strength,
            "trend_strength": trend_strength,
            "spread_strength": spread_strength,
            "volatility_strength": volatility_strength,
            "regime_fit": regime_fit,
            "signal_strength": signal_strength,
            "asset_bias": asset_bias,
        }

    def _build_explanation(
        self,
        item: Dict[str, Any],
        components: Dict[str, float],
        final_score: float,
    ) -> str:
        regime = str(item.get("regime", "UNKNOWN")).upper()
        signal = str(item.get("signal", "HOLD")).upper()
        symbol = str(item.get("symbol", "UNKNOWN"))
        asset_class = str(item.get("asset_class", "UNKNOWN")).upper()

        dominant_reasons: List[str] = []

        if components["scanner_strength"] >= 0.60:
            dominant_reasons.append("strong scanner rank")

        if regime == "TREND" and components["trend_strength"] >= 0.30:
            dominant_reasons.append("solid directional trend")

        if regime == "BREAKOUT" and components["volatility_strength"] >= 0.20:
            dominant_reasons.append("healthy breakout volatility")

        if regime == "MEAN_REVERSION" and components["spread_strength"] >= 0.15:
            dominant_reasons.append("meaningful VWAP dislocation")

        if components["signal_strength"] >= 0.85:
            dominant_reasons.append(f"active {signal} signal")

        if not dominant_reasons:
            dominant_reasons.append("moderate setup quality")

        reasons = ", ".join(dominant_reasons[:3])

        return (
            f"{symbol} ({asset_class}) scored {final_score:.1f}/100 due to "
            f"{reasons}, under {regime} regime conditions."
        )

    def score_one(self, item: Dict[str, Any]) -> Dict[str, Any]:
        components = self._score_components(item)

        weighted = (
            components["scanner_strength"] * 0.30
            + components["regime_fit"] * 0.22
            + components["signal_strength"] * 0.20
            + components["trend_strength"] * 0.10
            + components["spread_strength"] * 0.08
            + components["volatility_strength"] * 0.10
        )

        adjusted = weighted * components["asset_bias"]
        final_score = round(self._clamp(adjusted, 0.0, 1.0) * 100.0, 2)

        if final_score >= 80:
            confidence_band = "HIGH"
            action_priority = "TRADE_NOW"
        elif final_score >= 65:
            confidence_band = "GOOD"
            action_priority = "WATCH_CLOSELY"
        elif final_score >= 50:
            confidence_band = "MODERATE"
            action_priority = "WATCHLIST"
        else:
            confidence_band = "LOW"
            action_priority = "IGNORE"

        explanation = self._build_explanation(item, components, final_score)

        enriched = dict(item)
        enriched["opportunity_score"] = final_score
        enriched["confidence_band"] = confidence_band
        enriched["action_priority"] = action_priority
        enriched["explanation"] = explanation
        return enriched

    def run(self) -> List[Dict[str, Any]]:
        raw_signals = self.signal_engine.run()
        scored: List[Dict[str, Any]] = []

        for item in raw_signals:
            scored.append(self.score_one(item))

        scored.sort(key=lambda x: x["opportunity_score"], reverse=True)
        return scored


def print_ai_scores(items: List[Dict[str, Any]]) -> None:
    print("\n=== CSS AI OPPORTUNITY SCANNER ===\n")

    if not items:
        print("No opportunities found.")
        return

    for item in items:
        print(
            f"{item['symbol']} | {item['asset_class']} | "
            f"signal={item['signal']} | "
            f"regime={item['regime']} | "
            f"ai_score={item['opportunity_score']:.2f} | "
            f"band={item['confidence_band']} | "
            f"priority={item['action_priority']}"
        )

    print("\n=== CSS AI EXPLANATIONS ===\n")
    for item in items[:5]:
        print(f"- {item['explanation']}")


if __name__ == "__main__":
    scorer = AIOpportunityScorer()
    results = scorer.run()
    print_ai_scores(results)
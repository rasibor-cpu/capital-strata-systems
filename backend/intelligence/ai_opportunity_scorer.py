from __future__ import annotations

from typing import Any, Dict, List, Optional

from backend.intelligence.liquidity_volatility_filter import LiquidityVolatilityFilter


class AIOpportunityScorer:
    """
    CSS AI Opportunity Scorer

    Backward-compatible scorer for live dashboard and legacy callers.

    Supports:
    - scorer.run()
    - scorer.run(assets)
    - scorer.run(assets=[...])
    - scorer.run(opportunities=[...])
    - scorer.score_assets(...)
    - scorer.score_opportunities(...)
    """

    def __init__(
        self,
        *,
        max_assets: int = 30,
        min_volume: float = 100000.0,
        min_volatility: float = 0.002,
    ) -> None:
        self.filter = LiquidityVolatilityFilter(
            max_assets=max_assets,
            min_volume=min_volume,
            min_volatility=min_volatility,
        )

    def shortlist_assets(self, assets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not assets:
            return []

        normalized: List[Dict[str, Any]] = []
        for asset in assets:
            item = dict(asset)

            item["symbol"] = str(
                item.get("symbol")
                or item.get("asset")
                or item.get("product_id")
                or "UNKNOWN"
            )
            item["volume"] = self._to_float(item.get("volume"), 0.0)
            item["volatility"] = self._to_float(item.get("volatility"), 0.0)

            normalized.append(item)

        shortlisted = self.filter.filter(normalized)

        if not shortlisted:
            fallback = sorted(
                normalized,
                key=lambda x: (
                    self._to_float(x.get("volatility"), 0.0),
                    -abs(self._to_float(x.get("spread_bps"), 999999.0)),
                ),
                reverse=True,
            )
            shortlisted = fallback[: min(len(fallback), self.filter.max_assets)]

        return shortlisted

    def score_opportunities(
        self,
        assets: List[Dict[str, Any]],
        *,
        top_n: int = 5,
    ) -> List[Dict[str, Any]]:
        shortlisted = self.shortlist_assets(assets)
        if not shortlisted:
            return []

        scored: List[Dict[str, Any]] = []
        for asset in shortlisted:
            score = self._rule_based_score(asset)
            band = self._score_band(score)
            priority = self._priority_label(score)

            item = dict(asset)

            # New field names
            item["ai_score"] = round(score, 4)
            item["score_band"] = band
            item["priority"] = priority

            # Backward-compatible legacy field names
            item["opportunity_score"] = round(score, 4)
            item["confidence_band"] = band
            item["action_priority"] = priority

            # Common fields expected downstream
            item["asset_class"] = str(item.get("asset_class", "CRYPTO"))
            item["signal"] = str(item.get("signal", "HOLD")).upper()
            item["regime"] = str(item.get("regime", "MEAN_REVERSION"))

            item["explanation"] = self._build_explanation(item)

            scored.append(item)

        scored.sort(key=lambda x: float(x["opportunity_score"]), reverse=True)
        return scored[:top_n]

    def score_assets(
        self,
        assets: List[Dict[str, Any]],
        *,
        top_n: int = 5,
    ) -> List[Dict[str, Any]]:
        return self.score_opportunities(assets, top_n=top_n)

    def run(
        self,
        assets: Optional[Any] = None,
        *args: Any,
        **kwargs: Any,
    ) -> List[Dict[str, Any]]:
        extracted_assets = self._extract_assets(assets, *args, **kwargs)
        top_n = int(kwargs.get("top_n", 5))

        if not extracted_assets:
            return []

        return self.score_opportunities(extracted_assets, top_n=top_n)

    def score_single(self, asset: Dict[str, Any]) -> Dict[str, Any]:
        scored = self.score_opportunities([asset], top_n=1)
        return scored[0] if scored else {}

    def _extract_assets(
        self,
        assets: Optional[Any] = None,
        *args: Any,
        **kwargs: Any,
    ) -> List[Dict[str, Any]]:
        if isinstance(assets, list):
            return [dict(x) for x in assets if isinstance(x, dict)]

        if args:
            first = args[0]
            if isinstance(first, list):
                return [dict(x) for x in first if isinstance(x, dict)]

        for key in ("assets", "opportunities", "watchlist", "signals", "items"):
            value = kwargs.get(key)
            if isinstance(value, list):
                return [dict(x) for x in value if isinstance(x, dict)]

        if isinstance(assets, dict):
            return [dict(assets)]

        for key in ("asset", "opportunity", "signal", "item"):
            value = kwargs.get(key)
            if isinstance(value, dict):
                return [dict(value)]

        return []

    def _rule_based_score(self, asset: Dict[str, Any]) -> float:
        signal = str(asset.get("signal", "HOLD")).upper()
        regime = str(asset.get("regime", "")).upper()
        spread_bps = abs(self._to_float(asset.get("spread_bps"), 999.0))
        volume = self._to_float(asset.get("volume"), 0.0)
        volatility = self._to_float(asset.get("volatility"), 0.0)
        mid = self._to_float(asset.get("mid"), 0.0)
        vwap = self._to_float(asset.get("vwap"), 0.0)

        score = 0.0

        if signal == "BUY":
            score += 0.35
        elif signal == "SELL":
            score += 0.30
        else:
            score += 0.05

        if "TREND" in regime:
            score += 0.18
        elif "MEAN" in regime:
            score += 0.14
        elif "VOLATILITY REGIME UNSTABLE" in regime:
            score -= 0.10
        elif "UNSTABLE" in regime:
            score -= 0.08
        else:
            score += 0.06

        if mid > 0 and vwap > 0:
            deviation = abs(mid - vwap) / vwap
            score += min(deviation * 8.0, 0.20)

        if volume >= 5_000_000:
            score += 0.12
        elif volume >= 1_000_000:
            score += 0.09
        elif volume >= 250_000:
            score += 0.06
        elif volume >= 100_000:
            score += 0.03

        if volatility >= 0.03:
            score += 0.10
        elif volatility >= 0.015:
            score += 0.08
        elif volatility >= 0.0075:
            score += 0.05
        elif volatility >= 0.002:
            score += 0.02

        if spread_bps > 80:
            score -= 0.18
        elif spread_bps > 40:
            score -= 0.10
        elif spread_bps > 20:
            score -= 0.05
        elif spread_bps <= 10:
            score += 0.04

        return max(0.0, min(score, 0.99))

    def _build_explanation(self, asset: Dict[str, Any]) -> str:
        symbol = str(asset.get("symbol", "UNKNOWN"))
        signal = str(asset.get("signal", "HOLD")).upper()
        spread_bps = abs(self._to_float(asset.get("spread_bps"), 0.0))
        regime = str(asset.get("regime", "MEAN_REVERSION"))
        score = self._to_float(asset.get("opportunity_score"), 0.0)

        return (
            f"{symbol}: {signal} setup under {regime}; "
            f"spread={spread_bps:.2f} bps; score={score:.2f}"
        )

    @staticmethod
    def _score_band(score: float) -> str:
        if score >= 0.75:
            return "HIGH"
        if score >= 0.55:
            return "MEDIUM"
        if score >= 0.35:
            return "WATCH"
        return "LOW"

    @staticmethod
    def _priority_label(score: float) -> str:
        if score >= 0.75:
            return "PRIORITY-1"
        if score >= 0.55:
            return "PRIORITY-2"
        if score >= 0.35:
            return "PRIORITY-3"
        return "PASS"

    @staticmethod
    def _to_float(value: Optional[Any], default: float = 0.0) -> float:
        try:
            if value is None:
                return default
            return float(value)
        except (TypeError, ValueError):
            return default
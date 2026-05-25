from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.intelligence.ai_opportunity_scorer import AIOpportunityScorer
from backend.intelligence.opportunity_scoring_engine import OpportunityScoringEngine
from backend.scanner.unified_market_scanner import UnifiedMarketScanner
from backend.strategies.market_regime import MarketRegimeDetector


class OpportunityRouter:
    """
    CSS Opportunity Router

    Connects:
    scanner -> regime detection -> AI opportunity scoring -> strategy selection

    This version also preserves richer fields needed by:
    - volatility gate
    - liquidity gate
    - downstream execution/risk logic
    """

    def __init__(
        self,
        trade_threshold: float = 0.68,
        watch_threshold: float = 0.55,
    ) -> None:
        self.scanner = UnifiedMarketScanner()
        self.regime_detector = MarketRegimeDetector()
        self.scorer = AIOpportunityScorer(
            trade_threshold=trade_threshold,
            watch_threshold=watch_threshold,
        )
        self.trade_threshold = trade_threshold
        self.watch_threshold = watch_threshold
        self.opportunity_scoring_engine = OpportunityScoringEngine()

    def select_strategy(self, regime: str) -> str:
        regime = str(regime).upper()

        if regime == "TREND":
            return "momentum_strategy"

        if regime == "BREAKOUT":
            return "breakout_strategy"

        return "vwap_mean_reversion"

    def route(self, include_watchlist: bool = False) -> List[Dict[str, Any]]:
        raw_opportunities = self.scanner.scan_all()
        routed: List[Dict[str, Any]] = []

        for asset in raw_opportunities:
            prepared = self._prepare_asset(asset)

            regime_result = self.regime_detector.classify(
                trend_pct=prepared["trend_pct"],
                volatility_pct=prepared["volatility_pct"],
                vwap_spread_pct=prepared["spread_pct"],
            )

            scoring_payload = self._build_scoring_payload(
                asset=prepared,
                regime=str(regime_result.regime),
            )
            scored = self.scorer.score_opportunity(scoring_payload)

            decision = str(scored.get("decision", "IGNORE")).upper()
            final_score = self._to_float(scored.get("score"), 0.0)

            if decision == "IGNORE":
                continue

            if decision == "WATCH" and not include_watchlist:
                continue

            if decision == "TRADE" and final_score < self.trade_threshold:
                continue

            strategy = self.select_strategy(str(regime_result.regime))

            candidate_payload = {
                    "asset_class": prepared["asset_class"],
                    "symbol": prepared["symbol"],
                    "last_price": prepared["last_price"],
                    "source": prepared["source"],
                    "regime": str(regime_result.regime),
                    "confidence": self._to_float(getattr(regime_result, "confidence", 0.0), 0.0),
                    "strategy": strategy,
                    "decision": decision,
                    "score": final_score,
                    "scanner_score": prepared["scanner_score"],
                    "spread_pct": prepared["spread_pct"],
                    "spread_bps": prepared["spread_bps"],
                    "volatility_pct": prepared["volatility_pct"],
                    "avg_volatility": scoring_payload["avg_volatility"],
                    "volume_24h": scoring_payload["volume_24h"],
                    "avg_volume_24h": scoring_payload["avg_volume_24h"],
                    "trend_pct": prepared["trend_pct"],
                    "top_of_book_depth": scoring_payload["top_of_book_depth"],
                    "slippage_bps": scoring_payload["slippage_bps"],
                    "order_flow_delta": scoring_payload["order_flow_delta"],
                    "buy_pressure": scoring_payload["buy_pressure"],
                    "sell_pressure": scoring_payload["sell_pressure"],
                    "recent_high": scoring_payload["recent_high"],
                    "recent_low": scoring_payload["recent_low"],
                    "rejection_strength": scoring_payload["rejection_strength"],
                    "wick_reversal_strength": scoring_payload["wick_reversal_strength"],
                    "liquidity_sweep_flag": scoring_payload["liquidity_sweep_flag"],
                    "breakdown": scored.get("breakdown", {}),
                }

            candidate_payload["scoring_summary"] = self.opportunity_scoring_engine.score_opportunity(candidate_payload).to_dict()
            routed.append(candidate_payload)

        routed.sort(key=lambda item: item["score"], reverse=True)
        return routed

    def _prepare_asset(self, asset: Dict[str, Any]) -> Dict[str, Any]:
        symbol = str(asset.get("symbol", "UNKNOWN"))
        asset_class = str(asset.get("asset_class", "UNKNOWN"))
        source = str(asset.get("source", "UNKNOWN"))

        last_price = self._to_float(asset.get("last_price"), 0.0)
        spread_pct = self._to_float(asset.get("spread_pct"), 0.0)
        volatility_pct = self._to_float(asset.get("volatility_pct"), 0.0)
        trend_pct = self._to_float(asset.get("trend_pct"), 0.0)
        scanner_score = self._to_float(asset.get("score"), 0.0)

        spread_bps = self._pct_to_bps(spread_pct)

        return {
            "symbol": symbol,
            "asset_class": asset_class,
            "source": source,
            "last_price": last_price,
            "spread_pct": spread_pct,
            "spread_bps": spread_bps,
            "volatility_pct": volatility_pct,
            "trend_pct": trend_pct,
            "scanner_score": scanner_score,
            "raw": asset,
        }

    def _build_scoring_payload(self, asset: Dict[str, Any], regime: str) -> Dict[str, Any]:
        raw = asset["raw"]

        volume_24h = self._first_float(
            raw,
            ["volume_24h", "quote_volume", "base_volume", "notional_volume"],
            0.0,
        )
        avg_volume_24h = self._first_float(
            raw,
            ["avg_volume_24h", "average_volume_24h", "avg_quote_volume"],
            0.0,
        )
        top_of_book_depth = self._first_float(
            raw,
            ["top_of_book_depth", "book_depth", "depth", "bid_ask_depth"],
            0.0,
        )
        slippage_bps = self._first_float(
            raw,
            ["slippage_bps", "estimated_slippage_bps"],
            10.0,
        )
        order_flow_delta = self._first_float(
            raw,
            ["order_flow_delta", "flow_delta", "delta"],
            0.0,
        )
        buy_pressure = self._first_float(
            raw,
            ["buy_pressure", "bid_pressure"],
            0.0,
        )
        sell_pressure = self._first_float(
            raw,
            ["sell_pressure", "ask_pressure"],
            0.0,
        )
        recent_high = self._first_float(
            raw,
            ["recent_high", "high", "session_high"],
            0.0,
        )
        recent_low = self._first_float(
            raw,
            ["recent_low", "low", "session_low"],
            0.0,
        )
        rejection_strength = self._first_float(
            raw,
            ["rejection_strength"],
            0.0,
        )
        wick_reversal_strength = self._first_float(
            raw,
            ["wick_reversal_strength"],
            0.0,
        )
        liquidity_sweep_flag = bool(raw.get("liquidity_sweep_flag", False))

        payload: Dict[str, Any] = {
            "symbol": asset["symbol"],
            "price": asset["last_price"],
            "current_price": asset["last_price"],
            "spread_bps": asset["spread_bps"],
            "spread_pct": asset["spread_pct"],
            "volatility": asset["volatility_pct"],
            "avg_volatility": self._first_float(
                raw,
                ["avg_volatility", "average_volatility"],
                0.0,
            ),
            "regime": regime,
            "momentum": asset["trend_pct"],
            "trend_strength": abs(asset["trend_pct"]),
            "volume_24h": volume_24h,
            "avg_volume_24h": avg_volume_24h,
            "top_of_book_depth": top_of_book_depth,
            "slippage_bps": slippage_bps,
            "order_flow_delta": order_flow_delta,
            "buy_pressure": buy_pressure,
            "sell_pressure": sell_pressure,
            "recent_high": recent_high,
            "recent_low": recent_low,
            "rejection_strength": rejection_strength,
            "wick_reversal_strength": wick_reversal_strength,
            "liquidity_sweep_flag": liquidity_sweep_flag,
        }

        return payload

    @staticmethod
    def _to_float(value: Any, default: float = 0.0) -> float:
        try:
            if value is None:
                return default
            return float(value)
        except (TypeError, ValueError):
            return default

    def _first_float(self, data: Dict[str, Any], keys: List[str], default: float = 0.0) -> float:
        for key in keys:
            if key in data and data[key] is not None:
                return self._to_float(data[key], default)
        return default

    @staticmethod
    def _pct_to_bps(value: float) -> float:
        return float(value) * 10000.0


def print_routes(routes: List[Dict[str, Any]]) -> None:
    print("\n=== CSS OPPORTUNITY ROUTER ===\n")

    if not routes:
        print("No routed opportunities passed the AI score gate.")
        return

    for r in routes:
        print(
            f"{r['symbol']} | {r['asset_class']} | "
            f"decision={r['decision']} | "
            f"score={r['score']:.4f} | "
            f"regime={r['regime']} | "
            f"strategy={r['strategy']}"
        )


if __name__ == "__main__":
    router = OpportunityRouter()
    routes = router.route(include_watchlist=False)
    print_routes(routes)
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.intelligence.opportunity_router import OpportunityRouter
from backend.strategies.strategy_router import StrategyDecision, StrategyRouter


class SignalEngine:
    """
    CSS Signal Engine

    Flow:
        OpportunityRouter -> StrategyRouter -> normalized routed signals

    Purpose:
        - read routed opportunities from the intelligence layer
        - normalize regime/score/opportunity data into scanner-style payloads
        - pass each payload through StrategyRouter
        - return execution-friendly signal dictionaries
    """

    def __init__(self) -> None:
        self.router = OpportunityRouter()
        self.strategy_router = StrategyRouter(
            default_timeframe="15m",
            min_confidence_to_trade=0.55,
            allow_short_signals=False,
        )

    def _safe_float(self, value: Any, default: float = 0.0) -> float:
        try:
            if value is None or value == "":
                return default
            return float(value)
        except (TypeError, ValueError):
            return default

    def _normalize_regime(self, regime: Any) -> str:
        text = str(regime or "unknown").strip().lower().replace("-", "_").replace(" ", "_")

        alias_map = {
            "meanrev": "mean_reversion",
            "mean_revert": "mean_reversion",
            "mr": "mean_reversion",
            "trending": "trend",
            "uptrend": "trend",
            "downtrend": "trend",
            "riskoff": "risk_off",
        }

        return alias_map.get(text, text)

    def _infer_scanner_signal(self, regime: str, score: float) -> str:
        """
        Internal directional bias used before StrategyRouter finalizes action.
        """
        if regime in {"trend", "breakout", "momentum"} and score > 0.40:
            return "BUY"

        if regime in {"mean_reversion", "range"} and score > 0.30:
            # Long-only bias for now. StrategyRouter will convert to HOLD/BLOCK/BUY.
            return "BUY"

        if regime in {"risk_off", "blocked"}:
            return "BLOCK"

        return "HOLD"

    def _infer_strategy_name(self, regime: str) -> str:
        strategy_map = {
            "trend": "momentum_follow",
            "momentum": "momentum_follow",
            "breakout": "breakout_expansion",
            "mean_reversion": "vwap_mean_reversion",
            "range": "range_mean_reversion",
            "risk_off": "risk_block",
            "blocked": "risk_block",
        }
        return strategy_map.get(regime, "hold_cash")

    def _build_scanner_payload(self, opportunity: Dict[str, Any]) -> Dict[str, Any]:
        score = self._safe_float(opportunity.get("score"), 0.0)
        confidence = self._safe_float(opportunity.get("confidence"), score)
        regime = self._normalize_regime(opportunity.get("regime"))
        scanner_signal = self._infer_scanner_signal(regime, score)

        symbol = str(opportunity.get("symbol", "UNKNOWN")).strip() or "UNKNOWN"
        asset_class = str(opportunity.get("asset_class", "UNKNOWN")).strip() or "UNKNOWN"

        blocked = regime in {"risk_off", "blocked"}

        price_candidates = [
            opportunity.get("price"),
            opportunity.get("last_price"),
            opportunity.get("mid"),
        ]
        price: Optional[float] = None
        for candidate in price_candidates:
            parsed = self._safe_float(candidate, 0.0)
            if parsed > 0:
                price = parsed
                break

        reason = (
            f"OpportunityRouter selected {symbol} | "
            f"regime={regime} | score={score:.2f} | confidence={confidence:.2f}"
        )

        payload: Dict[str, Any] = {
            "symbol": symbol,
            "asset_class": asset_class,
            "regime": regime,
            "score": score,
            "confidence": confidence,
            "price": price,
            "timeframe": str(opportunity.get("timeframe", "15m")),
            "scanner_signal": scanner_signal,
            "scanner_reason": reason,
            "blocked": blocked,
            "block_reason": "Risk-off regime detected from opportunity router" if blocked else "",
            "strategy_hint": opportunity.get("strategy", self._infer_strategy_name(regime)),
            "trend_pct": self._safe_float(opportunity.get("trend_pct"), 0.0),
            "volatility_pct": self._safe_float(opportunity.get("volatility_pct"), 0.0),
            "spread_pct": self._safe_float(opportunity.get("spread_pct"), 0.0),
        }

        return payload

    def _decision_to_signal_dict(
        self,
        opportunity: Dict[str, Any],
        scanner_payload: Dict[str, Any],
        decision: StrategyDecision,
    ) -> Dict[str, Any]:
        signal = decision.signal

        return {
            "symbol": signal.symbol,
            "asset_class": str(opportunity.get("asset_class", "UNKNOWN")),
            "score": scanner_payload.get("score", 0.0),
            "regime": signal.regime,
            "confidence": signal.confidence,
            "strategy": signal.strategy_name,
            "strategy_selected": decision.selected_strategy,
            "route_status": decision.route_status,
            "signal": signal.action,
            "reason": signal.reason,
            "price": signal.price,
            "timeframe": signal.timeframe,
            "trend_pct": scanner_payload.get("trend_pct", 0.0),
            "volatility_pct": scanner_payload.get("volatility_pct", 0.0),
            "spread_pct": scanner_payload.get("spread_pct", 0.0),
            "router_explanation": decision.explanation,
            "metadata": signal.metadata,
        }

    def generate_signal(self, opportunity: Dict[str, Any]) -> Dict[str, Any]:
        """
        Converts one opportunity into one routed signal dictionary.
        """
        scanner_payload = self._build_scanner_payload(opportunity)
        decision = self.strategy_router.route(scanner_payload)
        return self._decision_to_signal_dict(opportunity, scanner_payload, decision)

    def run(self) -> List[Dict[str, Any]]:
        routes = self.router.route()
        signals: List[Dict[str, Any]] = []

        for route in routes:
            try:
                routed_signal = self.generate_signal(route)
                signals.append(routed_signal)
            except Exception as exc:
                signals.append(
                    {
                        "symbol": str(route.get("symbol", "UNKNOWN")),
                        "asset_class": str(route.get("asset_class", "UNKNOWN")),
                        "score": self._safe_float(route.get("score"), 0.0),
                        "regime": self._normalize_regime(route.get("regime")),
                        "confidence": self._safe_float(route.get("confidence"), 0.0),
                        "strategy": "signal_engine_error",
                        "strategy_selected": "signal_engine_error",
                        "route_status": "ERROR",
                        "signal": "HOLD",
                        "reason": f"SignalEngine error: {exc}",
                        "price": None,
                        "timeframe": str(route.get("timeframe", "15m")),
                        "trend_pct": self._safe_float(route.get("trend_pct"), 0.0),
                        "volatility_pct": self._safe_float(route.get("volatility_pct"), 0.0),
                        "spread_pct": self._safe_float(route.get("spread_pct"), 0.0),
                        "router_explanation": "Signal generation failed; safe HOLD applied",
                        "metadata": {},
                    }
                )

        return signals


def print_signals(signals: List[Dict[str, Any]]) -> None:
    print("\n=== CSS SIGNAL ENGINE ===\n")

    for s in signals:
        print(
            f"{s['symbol']} | {s['asset_class']} | "
            f"regime={s['regime']} | "
            f"strategy={s['strategy']} | "
            f"route_status={s['route_status']} | "
            f"signal={s['signal']} | "
            f"reason={s['reason']}"
        )


if __name__ == "__main__":
    engine = SignalEngine()
    signals = engine.run()
    print_signals(signals)
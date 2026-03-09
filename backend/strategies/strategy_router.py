from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


ALLOWED_REGIMES = {
    "trend",
    "momentum",
    "breakout",
    "mean_reversion",
    "range",
    "neutral",
    "unknown",
    "risk_off",
    "blocked",
}


@dataclass
class StrategySignal:
    """
    Canonical signal object produced by the strategy router and passed forward
    to downstream execution / simulation layers.

    action:
        BUY / SELL / HOLD / BLOCK
    """

    symbol: str
    strategy_name: str
    action: str
    confidence: float
    reason: str
    price: Optional[float] = None
    regime: str = "unknown"
    timeframe: str = "15m"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "strategy_name": self.strategy_name,
            "action": self.action,
            "confidence": self.confidence,
            "reason": self.reason,
            "price": self.price,
            "regime": self.regime,
            "timeframe": self.timeframe,
            "metadata": self.metadata,
        }


@dataclass
class StrategyDecision:
    """
    Full routing decision, including the chosen strategy and the final signal.
    """

    symbol: str
    selected_strategy: str
    regime: str
    route_status: str
    explanation: str
    signal: StrategySignal

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "selected_strategy": self.selected_strategy,
            "regime": self.regime,
            "route_status": self.route_status,
            "explanation": self.explanation,
            "signal": self.signal.to_dict(),
        }


class StrategyRouter:
    """
    StrategyRouter reads scanner output, determines the prevailing regime,
    selects the appropriate strategy, and emits a normalized signal object.

    This module does NOT place orders.
    It only decides what strategy should act and what signal should be passed
    to the execution / paper-trading / simulator layer.

    Expected scanner payload examples:
    {
        "symbol": "BTC-USD",
        "regime": "mean_reversion",
        "score": 0.71,
        "price": 62450.12,
        "timeframe": "15m",
        "scanner_signal": "BUY",
        "scanner_reason": "Price stretched below VWAP",
        "blocked": False
    }

    or more nested:
    {
        "asset": "ETH-USD",
        "scanner": {
            "regime": "trend",
            "score": 0.84,
            "signal": "BUY",
            "reason": "Momentum continuation"
        },
        "market": {
            "price": 3421.50,
            "timeframe": "15m"
        }
    }
    """

    def __init__(
        self,
        default_timeframe: str = "15m",
        min_confidence_to_trade: float = 0.55,
        allow_short_signals: bool = False,
    ) -> None:
        self.default_timeframe = default_timeframe
        self.min_confidence_to_trade = float(min_confidence_to_trade)
        self.allow_short_signals = bool(allow_short_signals)

        self._regime_strategy_map: Dict[str, str] = {
            "trend": "momentum_follow",
            "momentum": "momentum_follow",
            "breakout": "breakout_expansion",
            "mean_reversion": "vwap_mean_reversion",
            "range": "range_mean_reversion",
            "neutral": "hold_cash",
            "unknown": "hold_cash",
            "risk_off": "risk_block",
            "blocked": "risk_block",
        }

    # ---------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------

    def route(
        self,
        scanner_payload: Dict[str, Any],
        market_snapshot: Optional[Dict[str, Any]] = None,
    ) -> StrategyDecision:
        """
        Main entry point.

        Reads scanner output, chooses a strategy, and returns a normalized
        StrategyDecision object.
        """
        payload = scanner_payload or {}
        market = market_snapshot or {}

        symbol = self._extract_symbol(payload, market)
        regime = self._extract_regime(payload)
        confidence = self._extract_confidence(payload)
        price = self._extract_price(payload, market)
        timeframe = self._extract_timeframe(payload, market)
        blocked, block_reason = self._extract_block_status(payload)

        selected_strategy = self._select_strategy(regime, blocked)

        if blocked:
            signal = StrategySignal(
                symbol=symbol,
                strategy_name=selected_strategy,
                action="BLOCK",
                confidence=confidence,
                reason=block_reason or "Scanner marked asset as blocked",
                price=price,
                regime=regime,
                timeframe=timeframe,
                metadata=self._build_metadata(payload, market),
            )
            return StrategyDecision(
                symbol=symbol,
                selected_strategy=selected_strategy,
                regime=regime,
                route_status="BLOCKED",
                explanation=signal.reason,
                signal=signal,
            )

        signal = self._build_signal(
            selected_strategy=selected_strategy,
            symbol=symbol,
            regime=regime,
            confidence=confidence,
            price=price,
            timeframe=timeframe,
            payload=payload,
            market=market,
        )

        return StrategyDecision(
            symbol=symbol,
            selected_strategy=selected_strategy,
            regime=regime,
            route_status="READY",
            explanation=signal.reason,
            signal=signal,
        )

    def route_many(
        self,
        scanner_payloads: List[Dict[str, Any]],
        market_snapshot_by_symbol: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> List[StrategyDecision]:
        """
        Batch router for multiple scanner outputs.
        """
        decisions: List[StrategyDecision] = []
        market_map = market_snapshot_by_symbol or {}

        for item in scanner_payloads:
            symbol = self._extract_symbol(item, {})
            market = market_map.get(symbol, {})
            decisions.append(self.route(item, market))

        return decisions

    def to_execution_payload(self, decision: StrategyDecision) -> Dict[str, Any]:
        """
        Converts a StrategyDecision into a lightweight execution-ready payload.

        The downstream execution layer can decide whether to simulate, paper
        trade, or live trade.
        """
        signal = decision.signal
        return {
            "symbol": signal.symbol,
            "strategy": signal.strategy_name,
            "action": signal.action,
            "confidence": signal.confidence,
            "reason": signal.reason,
            "price": signal.price,
            "regime": signal.regime,
            "timeframe": signal.timeframe,
            "metadata": signal.metadata,
        }

    # ---------------------------------------------------------------------
    # Core decision logic
    # ---------------------------------------------------------------------

    def _select_strategy(self, regime: str, blocked: bool) -> str:
        if blocked:
            return "risk_block"
        return self._regime_strategy_map.get(regime, "hold_cash")

    def _build_signal(
        self,
        selected_strategy: str,
        symbol: str,
        regime: str,
        confidence: float,
        price: Optional[float],
        timeframe: str,
        payload: Dict[str, Any],
        market: Dict[str, Any],
    ) -> StrategySignal:
        scanner_action = self._extract_scanner_action(payload)
        scanner_reason = self._extract_reason(payload)

        if confidence < self.min_confidence_to_trade:
            return StrategySignal(
                symbol=symbol,
                strategy_name=selected_strategy,
                action="HOLD",
                confidence=confidence,
                reason=(
                    f"Confidence {confidence:.2f} below minimum trade threshold "
                    f"{self.min_confidence_to_trade:.2f}"
                ),
                price=price,
                regime=regime,
                timeframe=timeframe,
                metadata=self._build_metadata(payload, market),
            )

        if selected_strategy == "hold_cash":
            return StrategySignal(
                symbol=symbol,
                strategy_name=selected_strategy,
                action="HOLD",
                confidence=confidence,
                reason=scanner_reason or "No actionable regime detected",
                price=price,
                regime=regime,
                timeframe=timeframe,
                metadata=self._build_metadata(payload, market),
            )

        if selected_strategy == "risk_block":
            return StrategySignal(
                symbol=symbol,
                strategy_name=selected_strategy,
                action="BLOCK",
                confidence=confidence,
                reason=scanner_reason or "Risk-off regime detected",
                price=price,
                regime=regime,
                timeframe=timeframe,
                metadata=self._build_metadata(payload, market),
            )

        final_action = self._normalize_action(scanner_action, regime)

        if final_action == "SELL" and not self.allow_short_signals:
            return StrategySignal(
                symbol=symbol,
                strategy_name=selected_strategy,
                action="HOLD",
                confidence=confidence,
                reason=(
                    "Sell/short signal detected but short routing is disabled "
                    "in current router configuration"
                ),
                price=price,
                regime=regime,
                timeframe=timeframe,
                metadata=self._build_metadata(payload, market),
            )

        return StrategySignal(
            symbol=symbol,
            strategy_name=selected_strategy,
            action=final_action,
            confidence=confidence,
            reason=scanner_reason or self._default_reason(selected_strategy, regime),
            price=price,
            regime=regime,
            timeframe=timeframe,
            metadata=self._build_metadata(payload, market),
        )

    # ---------------------------------------------------------------------
    # Extraction helpers
    # ---------------------------------------------------------------------

    def _extract_symbol(
        self,
        payload: Dict[str, Any],
        market: Dict[str, Any],
    ) -> str:
        candidates = [
            payload.get("symbol"),
            payload.get("asset"),
            payload.get("product_id"),
            (payload.get("scanner") or {}).get("symbol"),
            (payload.get("scanner") or {}).get("asset"),
            market.get("symbol"),
            market.get("asset"),
        ]
        for value in candidates:
            if isinstance(value, str) and value.strip():
                return value.strip()
        return "UNKNOWN"

    def _extract_regime(self, payload: Dict[str, Any]) -> str:
        candidates = [
            payload.get("regime"),
            payload.get("market_regime"),
            payload.get("detected_regime"),
            (payload.get("scanner") or {}).get("regime"),
            (payload.get("scanner") or {}).get("market_regime"),
            (payload.get("scan_result") or {}).get("regime"),
        ]
        for value in candidates:
            if isinstance(value, str):
                normalized = value.strip().lower().replace("-", "_").replace(" ", "_")
                if normalized in ALLOWED_REGIMES:
                    return normalized
                if normalized in {"mr", "meanrev", "mean_revert"}:
                    return "mean_reversion"
                if normalized in {"trending", "uptrend", "downtrend"}:
                    return "trend"
        return "unknown"

    def _extract_confidence(self, payload: Dict[str, Any]) -> float:
        candidates = [
            payload.get("confidence"),
            payload.get("score"),
            payload.get("signal_score"),
            (payload.get("scanner") or {}).get("confidence"),
            (payload.get("scanner") or {}).get("score"),
            (payload.get("scan_result") or {}).get("score"),
        ]
        for value in candidates:
            parsed = self._safe_float(value)
            if parsed is not None:
                return max(0.0, min(parsed, 1.0))
        return 0.50

    def _extract_price(
        self,
        payload: Dict[str, Any],
        market: Dict[str, Any],
    ) -> Optional[float]:
        candidates = [
            payload.get("price"),
            payload.get("last_price"),
            payload.get("mid"),
            (payload.get("market") or {}).get("price"),
            (payload.get("market") or {}).get("last_price"),
            (payload.get("scanner") or {}).get("price"),
            market.get("price"),
            market.get("last_price"),
            market.get("mid"),
        ]
        for value in candidates:
            parsed = self._safe_float(value)
            if parsed is not None and parsed > 0:
                return parsed
        return None

    def _extract_timeframe(
        self,
        payload: Dict[str, Any],
        market: Dict[str, Any],
    ) -> str:
        candidates = [
            payload.get("timeframe"),
            (payload.get("market") or {}).get("timeframe"),
            (payload.get("scanner") or {}).get("timeframe"),
            market.get("timeframe"),
        ]
        for value in candidates:
            if isinstance(value, str) and value.strip():
                return value.strip()
        return self.default_timeframe

    def _extract_scanner_action(self, payload: Dict[str, Any]) -> str:
        candidates = [
            payload.get("scanner_signal"),
            payload.get("signal"),
            payload.get("action"),
            (payload.get("scanner") or {}).get("signal"),
            (payload.get("scanner") or {}).get("action"),
            (payload.get("scan_result") or {}).get("signal"),
        ]
        for value in candidates:
            if isinstance(value, str) and value.strip():
                normalized = value.strip().upper()
                if normalized in {"BUY", "SELL", "HOLD", "BLOCK"}:
                    return normalized
        return "HOLD"

    def _extract_reason(self, payload: Dict[str, Any]) -> str:
        candidates = [
            payload.get("scanner_reason"),
            payload.get("reason"),
            payload.get("explanation"),
            (payload.get("scanner") or {}).get("reason"),
            (payload.get("scan_result") or {}).get("reason"),
        ]
        for value in candidates:
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""

    def _extract_block_status(self, payload: Dict[str, Any]) -> Tuple[bool, str]:
        if bool(payload.get("blocked", False)):
            return True, str(payload.get("block_reason", "Blocked by scanner"))
        if bool((payload.get("scanner") or {}).get("blocked", False)):
            return True, str(
                (payload.get("scanner") or {}).get(
                    "block_reason",
                    "Blocked by scanner",
                )
            )

        regime = self._extract_regime(payload)
        if regime in {"risk_off", "blocked"}:
            return True, f"Blocked due to regime={regime}"

        return False, ""

    # ---------------------------------------------------------------------
    # Utility helpers
    # ---------------------------------------------------------------------

    def _normalize_action(self, scanner_action: str, regime: str) -> str:
        action = scanner_action.upper().strip()

        if action in {"BUY", "SELL", "HOLD", "BLOCK"}:
            return action

        if regime in {"trend", "momentum", "breakout"}:
            return "BUY"

        if regime in {"mean_reversion", "range"}:
            return "BUY"

        if regime in {"risk_off", "blocked"}:
            return "BLOCK"

        return "HOLD"

    def _default_reason(self, strategy_name: str, regime: str) -> str:
        if strategy_name == "momentum_follow":
            return f"Momentum/trend regime detected ({regime})"
        if strategy_name == "breakout_expansion":
            return f"Breakout regime detected ({regime})"
        if strategy_name == "vwap_mean_reversion":
            return f"Mean reversion regime detected ({regime})"
        if strategy_name == "range_mean_reversion":
            return f"Range regime detected ({regime})"
        if strategy_name == "risk_block":
            return "Risk-off routing block"
        return "No valid strategy route"

    def _build_metadata(
        self,
        payload: Dict[str, Any],
        market: Dict[str, Any],
    ) -> Dict[str, Any]:
        metadata: Dict[str, Any] = {
            "router": "StrategyRouter",
            "router_version": "1.0.0",
        }

        for key in (
            "score",
            "confidence",
            "volatility",
            "volume",
            "spread_bps",
            "scanner_rank",
            "scanner_name",
        ):
            if key in payload:
                metadata[key] = payload[key]

        scanner_obj = payload.get("scanner")
        if isinstance(scanner_obj, dict):
            for key in (
                "score",
                "confidence",
                "volatility",
                "volume",
                "spread_bps",
                "scanner_rank",
                "scanner_name",
            ):
                if key in scanner_obj and key not in metadata:
                    metadata[key] = scanner_obj[key]

        if market:
            for key in ("bid", "ask", "mid", "price", "last_price"):
                if key in market:
                    metadata[f"market_{key}"] = market[key]

        return metadata

    @staticmethod
    def _safe_float(value: Any) -> Optional[float]:
        try:
            if value is None or value == "":
                return None
            return float(value)
        except (TypeError, ValueError):
            return None


if __name__ == "__main__":
    sample_payload = {
        "symbol": "BTC-USD",
        "regime": "mean_reversion",
        "score": 0.78,
        "price": 62500.55,
        "timeframe": "15m",
        "scanner_signal": "BUY",
        "scanner_reason": "Price stretched below VWAP in a reverting regime",
        "blocked": False,
    }

    router = StrategyRouter(
        default_timeframe="15m",
        min_confidence_to_trade=0.55,
        allow_short_signals=False,
    )

    decision = router.route(sample_payload)
    print(decision.to_dict())
    print(router.to_execution_payload(decision))
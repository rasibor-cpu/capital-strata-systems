from __future__ import annotations

from typing import Any, Mapping


class AdaptiveExitEngineError(RuntimeError):
    """Fail-closed exception for adaptive exit recommendations."""


class AdaptiveExitEngine:
    """Recommendation-only adaptive exit engine with no execution side effects."""

    _VALID_ACTIONS = {"HOLD", "TAKE_PROFIT", "STOP_LOSS", "TRAIL", "TIME_EXIT", "REDUCE"}
    _WEAK_REGIMES = {"RANGING", "REVERSAL", "LOW_VOLATILITY", "UNKNOWN"}
    _STRONG_REGIMES = {"TRENDING", "BREAKOUT"}

    def __init__(
        self,
        *,
        drawdown_threshold: float = -0.02,
        protect_profit_threshold: float = 0.005,
        strong_trend_threshold: float = 0.65,
        weak_trend_threshold: float = 0.25,
        default_max_hold_seconds: int = 3600,
    ) -> None:
        self.drawdown_threshold = float(drawdown_threshold)
        self.protect_profit_threshold = float(protect_profit_threshold)
        self.strong_trend_threshold = float(strong_trend_threshold)
        self.weak_trend_threshold = float(weak_trend_threshold)
        self.default_max_hold_seconds = int(default_max_hold_seconds)

    def recommend_exit(
        self,
        *,
        open_trade_context: Mapping[str, Any],
        market_regime: str,
        strategy_memory_summary: Mapping[str, Any],
        current_unrealized_pnl: float,
        holding_duration: float,
        volatility: float,
        trend_strength: float,
    ) -> dict[str, Any]:
        trade = self._normalize_trade_context(open_trade_context)
        regime = str(market_regime or "").strip().upper()
        if not regime:
            raise AdaptiveExitEngineError("market_regime must be non-empty")

        if not isinstance(strategy_memory_summary, Mapping):
            raise AdaptiveExitEngineError("strategy_memory_summary must be a mapping")

        unrealized_pnl = self._safe_float(current_unrealized_pnl, "current_unrealized_pnl")
        hold_seconds = self._safe_float(holding_duration, "holding_duration")
        current_volatility = self._safe_float(volatility, "volatility")
        current_trend = self._safe_float(trend_strength, "trend_strength")

        if hold_seconds < 0:
            raise AdaptiveExitEngineError("holding_duration must be non-negative")

        max_hold_seconds = int(strategy_memory_summary.get("max_hold_seconds", self.default_max_hold_seconds))
        if max_hold_seconds <= 0:
            raise AdaptiveExitEngineError("max_hold_seconds must be positive")

        entry_price = float(trade.get("entry_price", 1.0))
        if entry_price <= 0:
            raise AdaptiveExitEngineError("open_trade_context.entry_price must be positive")

        action = "HOLD"
        exit_reason = "HOLD_STRONG_OR_NEUTRAL_CONDITIONS"

        if hold_seconds >= max_hold_seconds:
            action = "TIME_EXIT"
            exit_reason = "MAX_HOLD_EXCEEDED"
        elif unrealized_pnl <= self.drawdown_threshold:
            action = "STOP_LOSS"
            exit_reason = "DRAWDOWN_THRESHOLD_BREACHED"
        elif (
            unrealized_pnl > self.protect_profit_threshold
            and (regime in self._WEAK_REGIMES or current_trend <= self.weak_trend_threshold)
        ):
            action = "TAKE_PROFIT"
            exit_reason = "PROFIT_PROTECTION_ON_WEAK_REGIME"
        elif unrealized_pnl > 0 and current_volatility >= 0.045 and current_trend < self.strong_trend_threshold:
            action = "REDUCE"
            exit_reason = "VOLATILITY_SPIKE_POSITION_REDUCTION"
        elif (
            unrealized_pnl > 0
            and current_trend >= self.strong_trend_threshold
            and regime in self._STRONG_REGIMES
        ):
            action = "TRAIL"
            exit_reason = "STRONG_TREND_TRAIL_PROTECTION"

        confidence = self._build_confidence(
            action=action,
            unrealized_pnl=unrealized_pnl,
            trend_strength=current_trend,
            volatility=current_volatility,
            regime=regime,
        )

        stop_distance = max(0.003, current_volatility * 1.5)
        take_profit_distance = max(0.004, current_volatility * 2.0)
        trailing_distance = max(0.002, current_volatility * 1.2)

        recommended_stop = round(entry_price * (1.0 - stop_distance), 8)
        recommended_take_profit = round(entry_price * (1.0 + take_profit_distance), 8)
        recommended_trailing_stop = round(entry_price * (1.0 - trailing_distance), 8)

        result = {
            "trade_id": trade["trade_id"],
            "symbol": trade["symbol"],
            "action": action,
            "exit_reason": exit_reason,
            "confidence": confidence,
            "recommended_stop": recommended_stop,
            "recommended_take_profit": recommended_take_profit,
            "recommended_trailing_stop": recommended_trailing_stop,
            "max_hold_seconds": max_hold_seconds,
        }

        if result["action"] not in self._VALID_ACTIONS:
            raise AdaptiveExitEngineError("Invalid action generated")

        return result

    def _normalize_trade_context(self, context: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(context, Mapping):
            raise AdaptiveExitEngineError("open_trade_context must be a mapping")

        trade_id = str(context.get("trade_id") or "").strip()
        symbol = str(context.get("symbol") or "").strip().upper()

        if not trade_id:
            raise AdaptiveExitEngineError("open_trade_context.trade_id must be non-empty")
        if not symbol:
            raise AdaptiveExitEngineError("open_trade_context.symbol must be non-empty")

        payload = {"trade_id": trade_id, "symbol": symbol}
        if "entry_price" in context and context.get("entry_price") is not None:
            try:
                payload["entry_price"] = float(context["entry_price"])
            except (TypeError, ValueError) as exc:
                raise AdaptiveExitEngineError("open_trade_context.entry_price must be numeric") from exc
        else:
            payload["entry_price"] = 1.0

        return payload

    @staticmethod
    def _safe_float(value: Any, field_name: str) -> float:
        try:
            return float(value)
        except (TypeError, ValueError) as exc:
            raise AdaptiveExitEngineError(f"{field_name} must be numeric") from exc

    def _build_confidence(
        self,
        *,
        action: str,
        unrealized_pnl: float,
        trend_strength: float,
        volatility: float,
        regime: str,
    ) -> float:
        base = 0.35

        if action == "STOP_LOSS":
            base = 0.95
        elif action == "TIME_EXIT":
            base = 0.9
        elif action == "TAKE_PROFIT":
            base = 0.8
        elif action == "TRAIL":
            base = 0.78
        elif action == "REDUCE":
            base = 0.7
        elif action == "HOLD":
            base = 0.6 if regime in self._STRONG_REGIMES else 0.45

        modifier = min(0.15, abs(unrealized_pnl) * 2.0)
        modifier += min(0.1, max(0.0, trend_strength) * 0.2)
        modifier -= min(0.1, max(0.0, volatility) * 0.5)

        return round(max(0.0, min(1.0, base + modifier)), 4)

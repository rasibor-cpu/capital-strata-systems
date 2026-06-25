from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any, Mapping


class PerformanceAttributionEngineError(RuntimeError):
    """Fail-closed exception for performance attribution."""


class PerformanceAttributionEngine:
    def attribute(self, trades: list[Mapping[str, Any]] | None) -> dict[str, list[dict[str, Any]]]:
        rows = trades if isinstance(trades, list) else []
        if not rows:
            return {
                "strategy": [],
                "asset_class": [],
                "market_regime": [],
                "day_of_week": [],
                "hour_of_day": [],
                "trade_duration_bucket": [],
                "confidence_bucket": [],
                "trade_quality_bucket": [],
                "exit_reason": [],
                "position_size_bucket": [],
            }

        normalized = [self._normalize_trade(trade) for trade in rows]
        return {
            "strategy": self._aggregate(normalized, "strategy_id"),
            "asset_class": self._aggregate(normalized, "asset_class"),
            "market_regime": self._aggregate(normalized, "market_regime"),
            "day_of_week": self._aggregate(normalized, "day_of_week"),
            "hour_of_day": self._aggregate(normalized, "hour_of_day"),
            "trade_duration_bucket": self._aggregate(normalized, "trade_duration_bucket"),
            "confidence_bucket": self._aggregate(normalized, "confidence_bucket"),
            "trade_quality_bucket": self._aggregate(normalized, "trade_quality_bucket"),
            "exit_reason": self._aggregate(normalized, "exit_reason"),
            "position_size_bucket": self._aggregate(normalized, "position_size_bucket"),
        }

    def _aggregate(self, trades: list[dict[str, Any]], field_name: str) -> list[dict[str, Any]]:
        totals: dict[str, dict[str, float]] = defaultdict(lambda: {"trade_count": 0.0, "total_pnl": 0.0, "wins": 0.0, "confidence": 0.0})
        for trade in trades:
            bucket = str(trade[field_name])
            slot = totals[bucket]
            slot["trade_count"] += 1.0
            slot["total_pnl"] += trade["pnl"]
            slot["wins"] += 1.0 if trade["pnl"] > 0.0 else 0.0
            slot["confidence"] += trade["confidence"]

        output: list[dict[str, Any]] = []
        for bucket in sorted(totals.keys()):
            slot = totals[bucket]
            trade_count = int(slot["trade_count"])
            output.append(
                {
                    field_name: bucket,
                    "trade_count": trade_count,
                    "total_pnl": round(slot["total_pnl"], 8),
                    "win_rate": round((slot["wins"] / trade_count) if trade_count else 0.0, 8),
                    "average_pnl": round((slot["total_pnl"] / trade_count) if trade_count else 0.0, 8),
                    "average_confidence": round((slot["confidence"] / trade_count) if trade_count else 0.0, 8),
                }
            )
        return output

    def _normalize_trade(self, trade: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(trade, Mapping):
            raise PerformanceAttributionEngineError("trade must be a mapping")
        pnl = self._float(trade.get("realized_pnl", trade.get("pnl", 0.0)))
        confidence = self._float(trade.get("confidence", trade.get("decision_confidence", 0.0)))
        quality_score = self._float(trade.get("quality_score", trade.get("trade_quality_score", 0.0)))
        position_size = self._float(trade.get("position_size", trade.get("recommended_position_size", 0.0)))
        timestamp = str(trade.get("timestamp_close") or trade.get("exit_time") or trade.get("timestamp") or "").strip()
        dt = self._parse_datetime(timestamp)
        duration_seconds = self._duration_seconds(trade)

        return {
            "strategy_id": str(trade.get("strategy_id") or trade.get("strategy") or "UNKNOWN").strip() or "UNKNOWN",
            "asset_class": str(trade.get("asset_class") or "UNKNOWN").strip().upper() or "UNKNOWN",
            "market_regime": str(trade.get("market_regime") or "UNKNOWN").strip().upper() or "UNKNOWN",
            "day_of_week": dt.strftime("%A") if dt else "UNKNOWN",
            "hour_of_day": dt.strftime("%H") if dt else "UNKNOWN",
            "trade_duration_bucket": self._duration_bucket(duration_seconds),
            "confidence_bucket": self._confidence_bucket(confidence),
            "trade_quality_bucket": self._quality_bucket(quality_score),
            "exit_reason": str(trade.get("exit_reason") or trade.get("close_reason") or trade.get("exit_action") or "UNKNOWN").strip() or "UNKNOWN",
            "position_size_bucket": self._position_bucket(position_size),
            "pnl": round(pnl, 8),
            "confidence": round(confidence, 8),
        }

    @staticmethod
    def _parse_datetime(timestamp: str) -> datetime | None:
        if not timestamp:
            return None
        try:
            return datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except ValueError:
            return None

    @staticmethod
    def _duration_seconds(trade: Mapping[str, Any]) -> float:
        for key in ("holding_time_seconds", "holding_duration_seconds", "holding_duration_minutes"):
            if key in trade:
                value = trade.get(key)
                try:
                    numeric = float(value)
                except (TypeError, ValueError):
                    numeric = 0.0
                return numeric * 60.0 if key.endswith("minutes") else numeric
        return 0.0

    @staticmethod
    def _duration_bucket(seconds: float) -> str:
        if seconds <= 900:
            return "0-15m"
        if seconds <= 3600:
            return "15m-1h"
        if seconds <= 14400:
            return "1h-4h"
        return "4h+"

    @staticmethod
    def _confidence_bucket(confidence: float) -> str:
        if confidence < 0.25:
            return "0-25%"
        if confidence < 0.5:
            return "25-50%"
        if confidence < 0.75:
            return "50-75%"
        return "75-100%"

    @staticmethod
    def _quality_bucket(quality_score: float) -> str:
        if quality_score >= 85:
            return "A"
        if quality_score >= 70:
            return "B"
        if quality_score >= 55:
            return "C"
        if quality_score >= 40:
            return "D"
        return "E"

    @staticmethod
    def _position_bucket(position_size: float) -> str:
        if position_size <= 1000:
            return "0-1k"
        if position_size <= 5000:
            return "1k-5k"
        return "5k+"

    @staticmethod
    def _float(value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

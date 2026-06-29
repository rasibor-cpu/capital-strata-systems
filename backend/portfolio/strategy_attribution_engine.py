from __future__ import annotations

from typing import Any, Iterable, Mapping


class StrategyAttributionEngineError(RuntimeError):
    """Fail-closed exception for strategy attribution analysis."""


class StrategyAttributionEngine:
    """Deterministic attribution summaries for closed trade evidence."""

    def analyze(self, trades: Iterable[Mapping[str, Any]] | None) -> dict[str, Any]:
        if trades is None:
            return self._empty("trade_history_unavailable")
        if isinstance(trades, (str, bytes)) or not isinstance(trades, Iterable):
            return self._empty("trade_history_malformed")

        normalized: list[dict[str, Any]] = []
        for idx, raw in enumerate(trades):
            if not isinstance(raw, Mapping):
                return self._empty("trade_row_malformed")
            normalized.append(self._normalize_trade(raw, idx))

        if not normalized:
            return self._empty("No closed trade history available.")

        strategy = self._group(normalized, "strategy")
        asset_class = self._group(normalized, "asset_class")
        symbol = self._group(normalized, "symbol")
        regime = self._group(normalized, "market_regime")
        time_bucket = self._group(normalized, "time_bucket")
        ranked = sorted(normalized, key=lambda row: (-row["pnl"], row["symbol"], row["strategy"]))
        top_contributors = [self._contributor(row) for row in ranked[:3] if row["pnl"] > 0.0]
        top_detractors = [self._contributor(row) for row in sorted(normalized, key=lambda row: (row["pnl"], row["symbol"]))[:3] if row["pnl"] < 0.0]

        total_pnl = sum(row["pnl"] for row in normalized)
        win_rate = (sum(1 for row in normalized if row["pnl"] > 0.0) / len(normalized)) * 100.0
        reasons: list[str] = []
        if total_pnl < 0.0 and win_rate < 40.0:
            recommendation = "PAUSE_UNDERPERFORMERS"
            reasons.append("Negative total PnL with weak win rate.")
        elif top_detractors:
            recommendation = "REVIEW_DETRACTORS"
            reasons.append("Attribution includes losing contributors.")
        elif total_pnl > 0.0 and win_rate >= 60.0:
            recommendation = "EXPAND_WINNERS"
            reasons.append("Positive PnL and healthy win rate.")
        else:
            recommendation = "MAINTAIN"
            reasons.append("Attribution is mixed or insufficient for expansion.")

        return {
            "status": "OK",
            "strategy_attribution": strategy,
            "asset_class_attribution": asset_class,
            "symbol_attribution": symbol,
            "regime_attribution": regime,
            "time_bucket_attribution": time_bucket,
            "top_contributors": top_contributors,
            "top_detractors": top_detractors,
            "recommendation": recommendation,
            "reasons": reasons,
        }

    def _normalize_trade(self, raw: Mapping[str, Any], idx: int) -> dict[str, Any]:
        return {
            "strategy": self._text(raw.get("strategy_id", raw.get("strategy")), "STRATEGY_UNSPECIFIED"),
            "asset_class": self._text(raw.get("asset_class"), "ASSET_CLASS_UNSPECIFIED"),
            "symbol": self._text(raw.get("symbol"), f"SYMBOL_{idx}"),
            "market_regime": self._text(raw.get("market_regime", raw.get("regime")), "REGIME_UNSPECIFIED"),
            "time_bucket": self._time_bucket(raw.get("timestamp_close", raw.get("closed_at", raw.get("timestamp")))),
            "pnl": self._float(raw.get("realized_pnl", raw.get("pnl", raw.get("profit_loss", 0.0)))),
            "drawdown": max(0.0, self._float(raw.get("drawdown", raw.get("max_drawdown", 0.0)))),
        }

    def _group(self, trades: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        for row in trades:
            bucket = row[key]
            if bucket not in result:
                result[bucket] = {
                    "trade_count": 0,
                    "total_pnl": 0.0,
                    "average_pnl": 0.0,
                    "win_rate": 0.0,
                    "drawdown_proxy": 0.0,
                }
            item = result[bucket]
            item["trade_count"] += 1
            item["total_pnl"] += row["pnl"]
            item["drawdown_proxy"] = max(item["drawdown_proxy"], row["drawdown"], max(0.0, -row["pnl"]))

        for bucket in sorted(result.keys()):
            bucket_rows = [row for row in trades if row[key] == bucket]
            item = result[bucket]
            item["total_pnl"] = round(item["total_pnl"], 6)
            item["average_pnl"] = round(item["total_pnl"] / item["trade_count"], 6)
            item["win_rate"] = round((sum(1 for row in bucket_rows if row["pnl"] > 0.0) / item["trade_count"]) * 100.0, 6)
            item["drawdown_proxy"] = round(item["drawdown_proxy"], 6)

        return {key: result[key] for key in sorted(result.keys())}

    @staticmethod
    def _contributor(row: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "strategy": row["strategy"],
            "asset_class": row["asset_class"],
            "symbol": row["symbol"],
            "pnl": round(row["pnl"], 6),
        }

    @staticmethod
    def _time_bucket(value: Any) -> str:
        text = str(value or "").strip()
        if len(text) >= 10:
            return text[:10]
        return "TIME_BUCKET_UNSPECIFIED"

    @staticmethod
    def _text(value: Any, fallback: str) -> str:
        text = str(value or "").strip().upper()
        return text or fallback

    @staticmethod
    def _float(value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _empty(reason: str) -> dict[str, Any]:
        return {
            "status": "DATA UNAVAILABLE",
            "strategy_attribution": {},
            "asset_class_attribution": {},
            "symbol_attribution": {},
            "regime_attribution": {},
            "time_bucket_attribution": {},
            "top_contributors": [],
            "top_detractors": [],
            "recommendation": "MAINTAIN",
            "reasons": [reason],
        }

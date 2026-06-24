from __future__ import annotations

from typing import Any, Mapping

from backend.analytics.trade_outcome_repository import (
    TradeOutcomeRepository,
    TradeOutcomeRepositoryError,
    persist_completed_trade_outcome,
)


class CanonicalTradeLifecycleError(RuntimeError):
    """Fail-closed exception for canonical lifecycle normalization and persistence."""


class CanonicalTradeLifecycle:
    """Backend-only adapter for canonical trade lifecycle normalization."""

    _SUPPORTED_ASSET_CLASSES = {"FX", "CRYPTO", "OPTIONS", "FUTURES"}
    _ASSET_CLASS_ALIASES = {
        "fx": "FX",
        "forex": "FX",
        "crypto": "CRYPTO",
        "spot_crypto": "CRYPTO",
        "options": "OPTIONS",
        "futures": "FUTURES",
    }

    def __init__(self, repository: TradeOutcomeRepository | None = None) -> None:
        self.repository = repository or TradeOutcomeRepository("./trade_outcomes.json")

    def normalize_open_result(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        return self._normalize_trade_result(payload, is_open=True)

    def normalize_close_result(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        return self._normalize_trade_result(payload, is_open=False)

    def persist_closed_trade_outcome(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        normalized = self.normalize_close_result(payload)
        if normalized.get("realized_pnl") is None:
            raise CanonicalTradeLifecycleError("Missing required field: realized_pnl")
        try:
            return persist_completed_trade_outcome(self.repository, normalized)
        except TradeOutcomeRepositoryError as exc:
            raise CanonicalTradeLifecycleError(str(exc)) from exc

    def _normalize_trade_result(self, payload: Mapping[str, Any], *, is_open: bool) -> dict[str, Any]:
        if not isinstance(payload, Mapping):
            raise CanonicalTradeLifecycleError("Trade payload must be a mapping")

        required = [
            "trade_id",
            "timestamp_open",
            "timestamp_close",
            "symbol",
            "asset_class",
            "entry_price",
            "exit_price",
            "quantity",
            "holding_duration_seconds",
            "strategy_id",
            "market_regime",
            "broker",
        ]
        for field in required:
            if field not in payload:
                raise CanonicalTradeLifecycleError(f"Missing required field: {field}")

        if not payload["trade_id"] or not str(payload["trade_id"]).strip():
            raise CanonicalTradeLifecycleError("Missing required field: trade_id")
        if not payload["timestamp_open"] or not str(payload["timestamp_open"]).strip():
            raise CanonicalTradeLifecycleError("Missing required field: timestamp_open")
        if not payload["timestamp_close"] or not str(payload["timestamp_close"]).strip():
            raise CanonicalTradeLifecycleError("Missing required field: timestamp_close")

        normalized_asset_class = self._normalize_asset_class(payload["asset_class"])
        if is_open:
            return {
                "trade_id": str(payload["trade_id"]).strip(),
                "timestamp_open": str(payload["timestamp_open"]).strip(),
                "timestamp_close": str(payload["timestamp_close"]).strip(),
                "symbol": str(payload["symbol"]).strip(),
                "asset_class": normalized_asset_class,
                "entry_price": float(payload["entry_price"]),
                "exit_price": float(payload["exit_price"]),
                "quantity": float(payload["quantity"]),
                "realized_pnl": float(payload.get("realized_pnl", 0.0)),
                "holding_duration_seconds": float(payload["holding_duration_seconds"]),
                "strategy_id": str(payload["strategy_id"]).strip(),
                "market_regime": str(payload["market_regime"]).strip(),
                "broker": str(payload["broker"]).strip(),
            }

        if payload.get("realized_pnl") is None:
            raise CanonicalTradeLifecycleError("Missing required field: realized_pnl")

        return {
            "trade_id": str(payload["trade_id"]).strip(),
            "timestamp_open": str(payload["timestamp_open"]).strip(),
            "timestamp_close": str(payload["timestamp_close"]).strip(),
            "symbol": str(payload["symbol"]).strip(),
            "asset_class": normalized_asset_class,
            "entry_price": float(payload["entry_price"]),
            "exit_price": float(payload["exit_price"]),
            "quantity": float(payload["quantity"]),
            "realized_pnl": float(payload["realized_pnl"]),
            "holding_duration_seconds": float(payload["holding_duration_seconds"]),
            "strategy_id": str(payload["strategy_id"]).strip(),
            "market_regime": str(payload["market_regime"]).strip(),
            "broker": str(payload["broker"]).strip(),
        }

    def _normalize_asset_class(self, asset_class: Any) -> str:
        if asset_class is None:
            raise CanonicalTradeLifecycleError("Unsupported asset class")
        normalized = str(asset_class).strip().upper()
        alias = self._ASSET_CLASS_ALIASES.get(normalized.lower())
        if alias is not None:
            normalized = alias
        if normalized not in self._SUPPORTED_ASSET_CLASSES:
            raise CanonicalTradeLifecycleError(f"Unsupported asset class: {asset_class}")
        return normalized

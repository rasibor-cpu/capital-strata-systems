from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import uuid4


class UnifiedExecutionPipelineError(Exception):
    """Raised when a unified execution request is invalid or rejected."""


@dataclass(frozen=True)
class UnifiedExecutionRequest:
    asset_class: str
    symbol: str
    side: str
    quantity: int
    mode: str


@dataclass(frozen=True)
class UnifiedExecutionResult:
    trade_id: str
    symbol: str
    asset_class: str
    side: str
    quantity: int
    mode: str
    status: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "trade_id": self.trade_id,
            "symbol": self.symbol,
            "asset_class": self.asset_class,
            "side": self.side,
            "quantity": self.quantity,
            "mode": self.mode,
            "status": self.status,
            "reason": self.reason,
        }


class UnifiedExecutionPipeline:
    """Validation-only foundation for shared execution routing.

    This pipeline normalizes and validates paper-mode requests. It does **not**
    dispatch to a broker, journal fills, or claim order execution. Successful
    validation returns ``validated_not_executed``.
    """

    SUPPORTED_ASSET_CLASSES = {"FX", "CRYPTO", "OPTIONS", "FUTURES"}

    def execute(self, request: UnifiedExecutionRequest) -> UnifiedExecutionResult:
        asset_class = self._normalize_asset_class(request.asset_class)
        symbol = self._normalize_symbol(request.symbol)
        side = self._normalize_side(request.side)
        quantity = self._normalize_quantity(request.quantity)
        mode = self._normalize_mode(request.mode)

        if asset_class not in self.SUPPORTED_ASSET_CLASSES:
            raise UnifiedExecutionPipelineError("Unsupported asset class")

        if not symbol:
            raise UnifiedExecutionPipelineError("Missing symbol")
        if not side:
            raise UnifiedExecutionPipelineError("Missing side")
        if quantity <= 0:
            raise UnifiedExecutionPipelineError("Missing quantity")
        if not mode:
            raise UnifiedExecutionPipelineError("Missing mode")
        if mode == "live":
            raise UnifiedExecutionPipelineError("Live mode rejected in foundation phase")

        return UnifiedExecutionResult(
            trade_id=str(uuid4()),
            symbol=symbol,
            asset_class=asset_class,
            side=side,
            quantity=quantity,
            mode=mode,
            status="validated_not_executed",
            reason="validation_only_no_broker_dispatch",
        )

    def _normalize_asset_class(self, value: str) -> str:
        normalized = str(value or "").strip().upper()
        return normalized

    def _normalize_symbol(self, value: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            return ""
        return normalized.upper()

    def _normalize_side(self, value: str) -> str:
        normalized = str(value or "").strip().upper()
        if normalized in {"BUY", "SELL"}:
            return normalized
        return ""

    def _normalize_quantity(self, value: int) -> int:
        try:
            quantity = int(value)
        except (TypeError, ValueError):
            return 0
        return quantity

    def _normalize_mode(self, value: str) -> str:
        normalized = str(value or "").strip().lower()
        if normalized in {"paper", "live"}:
            return normalized
        return ""

from __future__ import annotations

from typing import Any, Mapping

from backend.analytics.trade_outcome_repository import TradeOutcomeRepository
from backend.app.options.options_contract_registry import get_options_contract
from backend.app.options.options_execution_adapter import OptionsExecutionAdapter
from backend.execution.canonical_trade_lifecycle import CanonicalTradeLifecycle, CanonicalTradeLifecycleError


class OptionsLifecycleAdapter(CanonicalTradeLifecycle):
    """Options-specific lifecycle adapter that exposes the canonical lifecycle contract."""

    def __init__(self, repository: TradeOutcomeRepository | None = None) -> None:
        super().__init__(repository=repository)
        self.execution_adapter = OptionsExecutionAdapter()

    def build_open_payload(
        self,
        *,
        trade_id: str,
        timestamp_open: str,
        timestamp_close: str,
        symbol: str,
        entry_price: float,
        exit_price: float,
        quantity: float,
        strategy_id: str,
        market_regime: str,
        broker: str,
    ) -> dict[str, Any]:
        contract = get_options_contract(symbol)
        normalized_symbol = contract.symbol if contract is not None else str(symbol or "").strip().upper()
        return {
            "trade_id": str(trade_id),
            "timestamp_open": str(timestamp_open),
            "timestamp_close": str(timestamp_close),
            "symbol": normalized_symbol,
            "asset_class": "OPTIONS",
            "entry_price": float(entry_price),
            "exit_price": float(exit_price),
            "quantity": float(quantity),
            "realized_pnl": 0.0,
            "holding_duration_seconds": 300.0,
            "strategy_id": str(strategy_id),
            "market_regime": str(market_regime),
            "broker": str(broker),
        }

    def build_close_payload(
        self,
        *,
        trade_id: str,
        timestamp_open: str,
        timestamp_close: str,
        symbol: str,
        entry_price: float,
        exit_price: float,
        quantity: float,
        realized_pnl: float,
        strategy_id: str,
        market_regime: str,
        broker: str,
    ) -> dict[str, Any]:
        payload = self.build_open_payload(
            trade_id=trade_id,
            timestamp_open=timestamp_open,
            timestamp_close=timestamp_close,
            symbol=symbol,
            entry_price=entry_price,
            exit_price=exit_price,
            quantity=quantity,
            strategy_id=strategy_id,
            market_regime=market_regime,
            broker=broker,
        )
        payload["realized_pnl"] = float(realized_pnl)
        return payload

    def normalize_open_result(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        return super().normalize_open_result(payload)

    def normalize_close_result(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        return super().normalize_close_result(payload)

    def persist_closed_trade_outcome(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        return super().persist_closed_trade_outcome(payload)

    def execute_paper_order(self, *, symbol: str, side: str, contracts: int, mode: str) -> dict[str, Any]:
        if str(mode or "").strip().lower() not in {"paper", "dry_run", "sim", "demo"}:
            raise CanonicalTradeLifecycleError("Unsupported execution mode")
        result = self.execution_adapter.execute_options_order(
            symbol=symbol,
            side=side,
            contracts=contracts,
            mode=mode,
        )
        return self.execution_adapter.result_to_dict(result)

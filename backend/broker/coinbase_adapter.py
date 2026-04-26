from __future__ import annotations

from typing import Any, Dict, Optional


class CoinbaseAdapter:
    """
    CSS Coinbase Adapter

    Compatible with:
    - broker_bootstrap.py
    - unified broker registry
    - dashboard route_execution(...)
    - CoinbaseExecutor where available

    SAFE DEFAULT:
    - paper mode does not place live orders
    - live mode only delegates to CoinbaseExecutor if it supports execution
    """

    def __init__(
        self,
        broker_name: str = "coinbase",
        mode: str = "paper",
        credentials: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        self.broker_name = broker_name
        self.mode = str(mode or "paper").lower()
        self.credentials = credentials or {}
        self.extra = kwargs
        self.connected = False
        self.executor = None

    def connect(self) -> bool:
        try:
            from backend.execution.coinbase_executor import CoinbaseExecutor

            self.executor = CoinbaseExecutor()
            self.connected = True
            return True
        except Exception as exc:
            self.executor = None
            self.connected = False
            print(f"[COINBASE ADAPTER WARN] Executor unavailable: {exc}")
            return False

    def is_configured(self) -> bool:
        return True

    def is_live_mode(self) -> bool:
        return self.mode == "live"

    def supports_asset_class(self, asset_class: str) -> bool:
        return str(asset_class or "").lower() in {"crypto", "spot", "coinbase"}

    def get_account_info(self) -> Dict[str, Any]:
        return {
            "broker": "coinbase",
            "mode": self.mode,
            "connected": self.connected,
        }

    def get_positions(self):
        return []

    def get_orders(self):
        return []

    def place_order(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        """
        Accepts either:
        - place_order(symbol="BTC-USD", units=1, side="BUY")
        - place_order(OrderRequest(...))
        """

        symbol = kwargs.get("symbol")
        units = kwargs.get("units") or kwargs.get("quantity") or kwargs.get("qty") or 1
        side = kwargs.get("side", "BUY")
        order_type = kwargs.get("order_type", "market")

        if args:
            req = args[0]
            symbol = getattr(req, "symbol", symbol)
            units = getattr(req, "units", units)
            units = getattr(req, "quantity", units)
            units = getattr(req, "qty", units)
            side = getattr(req, "side", side)
            order_type = getattr(req, "order_type", order_type)

        if not symbol:
            return {
                "ok": False,
                "status": "REJECTED",
                "error": "Missing symbol",
                "broker": "coinbase",
            }

        if self.executor is None:
            self.connect()

        if self.mode != "live":
            return {
                "ok": True,
                "status": "PAPER_FILLED",
                "broker": "coinbase",
                "symbol": symbol,
                "side": side,
                "units": units,
                "order_type": order_type,
                "order_id": f"PAPER-COINBASE-{symbol}",
                "message": "Coinbase paper route simulated safely; no live order sent.",
            }

        if self.executor is None:
            return {
                "ok": False,
                "status": "NO_EXECUTOR",
                "broker": "coinbase",
                "symbol": symbol,
                "error": "CoinbaseExecutor unavailable",
            }

        try:
            if hasattr(self.executor, "create_order"):
                result = self.executor.create_order(
                    symbol=symbol,
                    side=side,
                    quantity=units,
                    order_type=order_type,
                )
            elif hasattr(self.executor, "place_order"):
                result = self.executor.place_order(
                    symbol=symbol,
                    side=side,
                    quantity=units,
                    order_type=order_type,
                )
            else:
                return {
                    "ok": False,
                    "status": "EXECUTOR_NO_ORDER_METHOD",
                    "broker": "coinbase",
                    "symbol": symbol,
                }

            return {
                "ok": True,
                "status": "SENT",
                "broker": "coinbase",
                "symbol": symbol,
                "side": side,
                "units": units,
                "order_type": order_type,
                "order_id": getattr(result, "order_id", None) or "COINBASE-LIVE",
                "raw": result,
            }

        except Exception as exc:
            return {
                "ok": False,
                "status": "ERROR",
                "broker": "coinbase",
                "symbol": symbol,
                "error": str(exc),
            }

    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        return {
            "ok": False,
            "status": "NOT_IMPLEMENTED",
            "broker": "coinbase",
            "order_id": order_id,
        }

    def disconnect(self) -> None:
        self.connected = False
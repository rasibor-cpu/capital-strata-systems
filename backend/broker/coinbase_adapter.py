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

    PCNRASS SAFE RULES
    ------------------
    - paper mode never places live orders
    - paper mode must still initialize as connected for dashboard/paper testing
    - live mode only delegates to CoinbaseExecutor if execution is explicitly available
    - no silent paper fallback when live execution is requested
    """

    def __init__(
        self,
        broker_name: str = "coinbase",
        mode: str = "paper",
        credentials: Optional[Dict[str, Any]] = None,
        paper_mode: Optional[bool] = None,
        **kwargs: Any,
    ) -> None:
        self.broker_name = broker_name

        if paper_mode is True:
            self.mode = "paper"
        elif paper_mode is False:
            self.mode = "live"
        else:
            self.mode = str(mode or "paper").lower()

        self.paper_mode = self.mode != "live"
        self.credentials = credentials or {}
        self.extra = kwargs
        self.connected = False
        self.executor = None

    def connect(self) -> bool:
        """
        In paper mode, mark Coinbase as safely connected without requiring
        CoinbaseExecutor or live credentials.

        In live mode, attempt to load CoinbaseExecutor.
        """
        if self.paper_mode:
            self.connected = True
            self.executor = None
            print("[COINBASE ADAPTER] Paper mode connected safely")
            return True

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
        if self.paper_mode:
            return True
        return self.executor is not None or bool(self.credentials)

    def is_live_mode(self) -> bool:
        return self.mode == "live"

    def supports_asset_class(self, asset_class: str) -> bool:
        return str(asset_class or "").lower() in {"crypto", "spot", "coinbase"}

    def get_account_info(self) -> Dict[str, Any]:
        return {
            "broker": "coinbase",
            "mode": self.mode,
            "paper_mode": self.paper_mode,
            "connected": self.connected,
        }

    def get_positions(self):
        return []

    def get_orders(self):
        return []

    def get_price(self, symbol: str) -> Dict[str, Any]:
        """
        Safe price helper for paper dashboard compatibility.
        Live price fetching should be implemented through the real Coinbase executor
        or a dedicated market-data adapter later.
        """
        return {
            "ok": True,
            "broker": "coinbase",
            "symbol": symbol,
            "price": 100.0,
            "mode": self.mode,
            "source": "paper_reference_price" if self.paper_mode else "fallback_reference_price",
        }

    def place_market_buy(
        self,
        product_id: Optional[str] = None,
        size_usd: Optional[float] = None,
        symbol: Optional[str] = None,
        quantity: Optional[float] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Dashboard-compatible Coinbase buy method.

        The current dashboard calls:
            place_market_buy(product_id=symbol, size_usd=...)
        """
        resolved_symbol = product_id or symbol or kwargs.get("product") or kwargs.get("instrument")
        resolved_units = quantity or kwargs.get("units") or kwargs.get("qty") or size_usd or 1.0

        return self.place_order(
            symbol=resolved_symbol,
            units=resolved_units,
            side="BUY",
            order_type="market",
            size_usd=size_usd,
            **kwargs,
        )

    def place_market_sell(
        self,
        product_id: Optional[str] = None,
        size_usd: Optional[float] = None,
        symbol: Optional[str] = None,
        quantity: Optional[float] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        resolved_symbol = product_id or symbol or kwargs.get("product") or kwargs.get("instrument")
        resolved_units = quantity or kwargs.get("units") or kwargs.get("qty") or size_usd or 1.0

        return self.place_order(
            symbol=resolved_symbol,
            units=resolved_units,
            side="SELL",
            order_type="market",
            size_usd=size_usd,
            **kwargs,
        )

    def place_order(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        """
        Accepts either:
        - place_order(symbol="BTC-USD", units=1, side="BUY")
        - place_order(OrderRequest(...))
        """

        symbol = kwargs.get("symbol")
        units = kwargs.get("units") or kwargs.get("quantity") or kwargs.get("qty") or kwargs.get("size_usd") or 1
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

        if self.paper_mode:
            self.connected = True
            return {
                "ok": True,
                "success": True,
                "status": "paper_filled",
                "order_status": "paper_filled",
                "broker": "coinbase",
                "symbol": symbol,
                "product_id": symbol,
                "side": side,
                "units": units,
                "order_type": order_type,
                "order_id": f"PAPER-COINBASE-{symbol}",
                "success_response": {
                    "order_id": f"PAPER-COINBASE-{symbol}",
                    "product_id": symbol,
                    "side": side,
                    "filled_size": units,
                },
                "message": "Coinbase paper route simulated safely; no live order sent.",
            }

        if self.executor is None:
            self.connect()

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
                "success": True,
                "status": "sent",
                "broker": "coinbase",
                "symbol": symbol,
                "product_id": symbol,
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

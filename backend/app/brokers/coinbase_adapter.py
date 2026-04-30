from __future__ import annotations

from typing import Any, Dict, Optional


class CoinbaseAdapter:
    """
    CSS Coinbase Adapter — PCNRASS SAFE LIVE BALANCE VERSION.
    Additive live-balance support; order execution behavior preserved.
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
            "has_executor": self.executor is not None,
            "supports_live_balance": True,
        }

    def _extract_balance_from_accounts(self, accounts: Any) -> Optional[float]:
        if not isinstance(accounts, list):
            return None
        total = 0.0
        for acct in accounts:
            if isinstance(acct, dict):
                for key in ("available_balance", "balance", "hold", "cash", "value", "amount"):
                    val = acct.get(key)
                    if isinstance(val, dict):
                        val = val.get("value") or val.get("amount")
                    try:
                        total += float(val or 0.0)
                    except Exception:
                        pass
            else:
                for attr in ("available_balance", "balance", "hold", "cash", "value", "amount"):
                    try:
                        val = getattr(acct, attr)
                    except Exception:
                        continue
                    if isinstance(val, dict):
                        val = val.get("value") or val.get("amount")
                    try:
                        total += float(val or 0.0)
                    except Exception:
                        pass
        return total if total > 0 else None

    def _extract_balance_from_payload(self, payload: Any) -> Optional[float]:
        if payload is None:
            return None
        if isinstance(payload, (int, float)):
            return float(payload) if float(payload) > 0 else None
        if isinstance(payload, dict):
            for key in ("balance", "cash", "equity", "available", "total", "portfolio_balance", "account_balance", "available_balance"):
                val = payload.get(key)
                if isinstance(val, dict):
                    val = val.get("value") or val.get("amount")
                try:
                    if val is not None and float(val) > 0:
                        return float(val)
                except Exception:
                    pass
            accounts = payload.get("accounts") or payload.get("data") or payload.get("results")
            if isinstance(accounts, list):
                return self._extract_balance_from_accounts(accounts)
        if isinstance(payload, list):
            return self._extract_balance_from_accounts(payload)
        for attr in ("balance", "cash", "equity", "available", "total", "portfolio_balance", "account_balance", "available_balance", "accounts"):
            try:
                val = getattr(payload, attr)
            except Exception:
                continue
            if isinstance(val, list):
                found = self._extract_balance_from_accounts(val)
                if found is not None:
                    return found
            if isinstance(val, dict):
                val = val.get("value") or val.get("amount") or val.get("balance")
            try:
                if val is not None and float(val) > 0:
                    return float(val)
            except Exception:
                pass
        return None

    def get_live_balance(self) -> Dict[str, Any]:
        """
        Phase 3B-3 read-only live balance retrieval.
        No orders are placed here.
        """
        if self.paper_mode:
            return {"ok": False, "balance": None, "source": "paper_mode_no_live_balance", "broker": "coinbase", "mode": self.mode}

        if self.executor is None:
            self.connect()

        if self.executor is None:
            return {"ok": False, "balance": None, "source": "executor_unavailable", "broker": "coinbase", "mode": self.mode}

        for method_name in ("get_live_balance", "get_balance", "get_account_balance", "fetch_balance", "get_portfolio_balance", "get_accounts", "list_accounts", "get_account_info"):
            method = getattr(self.executor, method_name, None)
            if not callable(method):
                continue
            try:
                result = method()
                balance = self._extract_balance_from_payload(result)
                if balance is not None and balance > 0:
                    return {"ok": True, "balance": float(balance), "source": f"executor.{method_name}", "broker": "coinbase", "mode": self.mode}
            except Exception:
                continue

        for client_attr in ("client", "coinbase_client", "advanced_client", "rest_client", "api_client"):
            client = getattr(self.executor, client_attr, None)
            if client is None:
                continue
            for method_name in ("get_accounts", "list_accounts", "get_account", "get_portfolio", "get_portfolios"):
                method = getattr(client, method_name, None)
                if not callable(method):
                    continue
                try:
                    result = method()
                    balance = self._extract_balance_from_payload(result)
                    if balance is not None and balance > 0:
                        return {"ok": True, "balance": float(balance), "source": f"executor.{client_attr}.{method_name}", "broker": "coinbase", "mode": self.mode}
                except Exception:
                    continue

        return {"ok": False, "balance": None, "source": "no_supported_balance_method_returned_value", "broker": "coinbase", "mode": self.mode, "executor_type": type(self.executor).__name__}

    def get_balance(self) -> Dict[str, Any]:
        return self.get_live_balance()

    def get_account_balance(self) -> Dict[str, Any]:
        return self.get_live_balance()

    def get_portfolio_balance(self) -> Dict[str, Any]:
        return self.get_live_balance()

    def get_positions(self):
        return []

    def get_orders(self):
        return []

    def get_price(self, symbol: str) -> Dict[str, Any]:
        return {"ok": True, "broker": "coinbase", "symbol": symbol, "price": 100.0, "mode": self.mode, "source": "paper_reference_price" if self.paper_mode else "fallback_reference_price"}

    def place_market_buy(self, product_id: Optional[str] = None, size_usd: Optional[float] = None, symbol: Optional[str] = None, quantity: Optional[float] = None, **kwargs: Any) -> Dict[str, Any]:
        resolved_symbol = product_id or symbol or kwargs.get("product") or kwargs.get("instrument")
        resolved_units = quantity or kwargs.get("units") or kwargs.get("qty") or size_usd or 1.0
        return self.place_order(symbol=resolved_symbol, units=resolved_units, side="BUY", order_type="market", size_usd=size_usd, **kwargs)

    def place_market_sell(self, product_id: Optional[str] = None, size_usd: Optional[float] = None, symbol: Optional[str] = None, quantity: Optional[float] = None, **kwargs: Any) -> Dict[str, Any]:
        resolved_symbol = product_id or symbol or kwargs.get("product") or kwargs.get("instrument")
        resolved_units = quantity or kwargs.get("units") or kwargs.get("qty") or size_usd or 1.0
        return self.place_order(symbol=resolved_symbol, units=resolved_units, side="SELL", order_type="market", size_usd=size_usd, **kwargs)

    def place_order(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
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
            return {"ok": False, "status": "REJECTED", "error": "Missing symbol", "broker": "coinbase"}

        if self.paper_mode:
            self.connected = True
            return {
                "ok": True, "success": True, "status": "paper_filled", "order_status": "paper_filled",
                "broker": "coinbase", "symbol": symbol, "product_id": symbol, "side": side,
                "units": units, "order_type": order_type, "order_id": f"PAPER-COINBASE-{symbol}",
                "success_response": {"order_id": f"PAPER-COINBASE-{symbol}", "product_id": symbol, "side": side, "filled_size": units},
                "message": "Coinbase paper route simulated safely; no live order sent.",
            }

        if self.executor is None:
            self.connect()

        if self.executor is None:
            return {"ok": False, "status": "NO_EXECUTOR", "broker": "coinbase", "symbol": symbol, "error": "CoinbaseExecutor unavailable"}

        try:
            if hasattr(self.executor, "create_order"):
                result = self.executor.create_order(symbol=symbol, side=side, quantity=units, order_type=order_type)
            elif hasattr(self.executor, "place_order"):
                result = self.executor.place_order(symbol=symbol, side=side, quantity=units, order_type=order_type)
            else:
                return {"ok": False, "status": "EXECUTOR_NO_ORDER_METHOD", "broker": "coinbase", "symbol": symbol}

            return {
                "ok": True, "success": True, "status": "sent", "broker": "coinbase", "symbol": symbol,
                "product_id": symbol, "side": side, "units": units, "order_type": order_type,
                "order_id": getattr(result, "order_id", None) or "COINBASE-LIVE", "raw": result,
            }
        except Exception as exc:
            return {"ok": False, "status": "ERROR", "broker": "coinbase", "symbol": symbol, "error": str(exc)}

    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        return {"ok": False, "status": "NOT_IMPLEMENTED", "broker": "coinbase", "order_id": order_id}

    def disconnect(self) -> None:
        self.connected = False

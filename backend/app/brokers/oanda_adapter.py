"""
OANDA Adapter — REA Capital Trading Engine

Goals:
- Small, reliable surface area used by smoke tests and guarded runners.
- Fail-closed: missing creds => is_configured() == False, request methods raise.
- Provide stable methods:
    - get_account_summary()
    - get_open_positions()
    - get_open_trades()
    - place_order(...)
    - close_trade(...)
    - close_position(...)
"""

from __future__ import annotations

import os
import json
import time
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional, List

import requests


@dataclass(frozen=True)
class OrderRequest:
    """
    Canonical order request object for guarded execution.

    symbol: OANDA instrument e.g. "EUR_USD"
    side: "BUY" or "SELL"
    units: absolute units (int). Adapter converts SELL to negative units.
    order_type: "MARKET" for now
    """
    symbol: str
    side: str = "BUY"
    units: int = 1
    order_type: str = "MARKET"


class OandaAdapter:
    def __init__(self) -> None:
        self.api_key = (os.getenv("OANDA_API_KEY") or "").strip()
        self.account_id = (os.getenv("OANDA_ACCOUNT_ID") or "").strip()
        self.base_url = (os.getenv("OANDA_BASE_URL") or "").strip().rstrip("/")
        self.env = (os.getenv("OANDA_ENV") or "").strip().lower()
        self.allow_live_trades = os.getenv("OANDA_ENABLE_LIVE_TRADING", "0").strip().lower() in ("1", "true", "yes", "on")
        
        self.health_state = "GREEN"
        self.consecutive_failures = 0
        self.margin_rejection_lock = False

    # -------------------------
    # configuration
    # -------------------------
    def is_configured(self) -> bool:
        return bool(self.api_key and self.account_id and self.base_url)

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _request_json(self, method: str, path: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if not self.is_configured():
            raise RuntimeError("OANDA not configured: set OANDA_API_KEY, OANDA_ACCOUNT_ID and OANDA_BASE_URL.")

        if self.margin_rejection_lock and method.upper() in ("POST", "PUT"):
            # Block new orders if margin rejected
            return {"ok": False, "status": None, "data": None, "error": "margin_rejection_lock_active"}

        url = f"{self.base_url}/{path.lstrip('/')}"
        
        max_retries = 3
        backoff_factor = 1.0
        
        for attempt in range(max_retries + 1):
            try:
                resp = requests.request(
                    method=method.upper(),
                    url=url,
                    headers=self._headers(),
                    json=payload,
                    timeout=20,
                )
                
                # Check for 429 Rate Limit
                if resp.status_code == 429:
                    if attempt < max_retries:
                        time.sleep(backoff_factor * (2 ** attempt))
                        continue
                    else:
                        self._record_failure()
                        return {"ok": False, "status": 429, "data": None, "error": "rate_limit_exhausted"}
                
                # Check for other errors
                ok = 200 <= (resp.status_code or 0) < 300
                data: Any = None
                try:
                    data = resp.json()
                except Exception:
                    data = resp.text

                # Check for margin rejection (usually 400 with specific message in OANDA)
                if resp.status_code == 400 and data and isinstance(data, dict):
                    err_msg = str(data.get("errorMessage", "")).upper()
                    if "INSUFFICIENT" in err_msg or "MARGIN" in err_msg:
                        self.margin_rejection_lock = True
                        self._record_failure()
                        logging.warning("[OANDA ADAPTER] Margin rejection detected. Order submissions locked.")
                        return {"ok": False, "status": 400, "data": data, "error": "insufficient_margin"}

                if not ok:
                    if attempt < max_retries and resp.status_code >= 500:
                        time.sleep(backoff_factor * (2 ** attempt))
                        continue
                    
                    self._record_failure()
                    return {"ok": False, "status": resp.status_code, "data": data, "error": f"http_{resp.status_code}"}

                self._record_success()
                return {"ok": True, "status": resp.status_code, "data": data, "error": None}

            except requests.exceptions.RequestException as e:
                if attempt < max_retries:
                    time.sleep(backoff_factor * (2 ** attempt))
                    continue
                self._record_failure()
                return {"ok": False, "status": None, "data": None, "error": f"request_error: {e}"}

        self._record_failure()
        return {"ok": False, "status": None, "data": None, "error": "max_retries_exhausted"}

    def _record_success(self):
        self.consecutive_failures = 0
        self.health_state = "GREEN"

    def _record_failure(self):
        self.consecutive_failures += 1
        if self.consecutive_failures >= 5:
            self.health_state = "RED"
        elif self.consecutive_failures >= 2:
            self.health_state = "DEGRADED"

    # -------------------------
    # read endpoints
    # -------------------------
    def get_account_summary(self) -> Dict[str, Any]:
        return self._request_json("GET", f"v3/accounts/{self.account_id}/summary")

    def get_open_positions(self) -> Dict[str, Any]:
        # returns list of positions (may be empty)
        return self._request_json("GET", f"v3/accounts/{self.account_id}/openPositions")

    def get_open_trades(self) -> Dict[str, Any]:
        return self._request_json("GET", f"v3/accounts/{self.account_id}/openTrades")

    # -------------------------
    # trade/order endpoints
    # -------------------------
    def _allow_live_order_execution(self) -> bool:
        return self.allow_live_trades

    def place_order(
        self,
        order: Optional[OrderRequest] = None,
        symbol: Optional[str] = None,
        side: str = "BUY",
        units: int = 1,
        order_type: str = "MARKET",
        price_bound: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Accept either:
          - place_order(OrderRequest(...))
          - place_order(symbol="EUR_USD", units=1, side="BUY")
        """
        if order is not None:
            symbol = order.symbol
            side = order.side
            units = order.units
            order_type = order.order_type

        symbol_final = (symbol or "").strip()
        if not symbol_final:
            return {"ok": False, "status": None, "data": None, "error": "missing_symbol"}

        if not self._allow_live_order_execution():
            return {"ok": False, "status": None, "data": None, "error": "live_execution_blocked_by_firewall"}

        side_u = (side or "BUY").upper().strip()
        if side_u not in ("BUY", "SELL"):
            return {"ok": False, "status": None, "data": None, "error": "invalid_side"}

        units_i = int(units)
        if units_i <= 0:
            return {"ok": False, "status": None, "data": None, "error": "invalid_units"}

        signed_units = units_i if side_u == "BUY" else -units_i

        otype = (order_type or "MARKET").upper().strip()
        if otype != "MARKET":
            return {"ok": False, "status": None, "data": None, "error": "unsupported_order_type"}

        payload = {
            "order": {
                "type": "MARKET",
                "instrument": symbol_final,
                "units": str(signed_units),
                "timeInForce": "FOK",
                "positionFill": "DEFAULT",
            }
        }
        
        if price_bound is not None:
            payload["order"]["priceBound"] = str(price_bound)

        return self._request_json("POST", f"v3/accounts/{self.account_id}/orders", payload)

    def close_trade(self, trade_id: str) -> Dict[str, Any]:
        tid = (trade_id or "").strip()
        if not tid:
            return {"ok": False, "status": None, "data": None, "error": "missing_trade_id"}
        return self._request_json("PUT", f"v3/accounts/{self.account_id}/trades/{tid}/close")

    def close_position(self, instrument: str, long_units: str = "ALL", short_units: str = "ALL") -> Dict[str, Any]:
        instr = (instrument or "").strip()
        if not instr:
            return {"ok": False, "status": None, "data": None, "error": "missing_instrument"}
        payload = {"longUnits": long_units, "shortUnits": short_units}
        return self._request_json("PUT", f"v3/accounts/{self.account_id}/positions/{instr}/close", payload)

    # -------------------------
    # small helpers for guarded runner
    # -------------------------
    @staticmethod
    def extract_balance_nav(summary_resp: Dict[str, Any]) -> Dict[str, Optional[float]]:
        """
        Works on:
          GET /summary response => {"account": {"balance": "...", "NAV": "..."}}
        """
        try:
            acc = (summary_resp.get("data") or {}).get("account") or {}
            bal = float(acc.get("balance")) if acc.get("balance") is not None else None
            nav = float(acc.get("NAV")) if acc.get("NAV") is not None else None
            return {"balance": bal, "nav": nav}
        except Exception:
            return {"balance": None, "nav": None}

"""
OANDA Adapter — REA Capital Trading Engine
-----------------------------------------

Goals:
- Minimal but robust OANDA REST adapter for Practice/Live.
- Fail-safe: missing creds => not configured.
- Structured responses with status + error snippets to avoid "None" mysteries.
- Supports smoke tests + guarded execution micro-trade.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional, Union

try:
    from dotenv import load_dotenv  # type: ignore
except Exception:  # pragma: no cover
    load_dotenv = None  # type: ignore

try:
    import requests  # type: ignore
except Exception as e:  # pragma: no cover
    raise RuntimeError("Missing dependency: requests. Install with: pip install requests") from e


# -----------------------------
# Data contracts (lightweight)
# -----------------------------

@dataclass(frozen=True)
class OrderRequest:
    """
    Engine-level order intent. Keep it tiny and resilient.
    """
    symbol: str
    units: int
    side: str = "BUY"          # BUY / SELL
    order_type: str = "MARKET" # MARKET only for now (micro-test)


# -----------------------------
# Adapter
# -----------------------------

class OandaAdapter:
    def __init__(self) -> None:
        # Load .env if python-dotenv exists
        if load_dotenv is not None:
            load_dotenv()

        self.api_key = (os.getenv("OANDA_API_KEY") or "").strip()
        self.account_id = (os.getenv("OANDA_ACCOUNT_ID") or "").strip()

        # IMPORTANT:
        # - Your .env currently uses practice: https://api-fxpractice.oanda.com
        # - OANDA API paths include /v3/...
        raw_base = (os.getenv("OANDA_BASE_URL") or "").strip().rstrip("/")
        self.base_url = raw_base

        # Optional (nice for printing / future routing)
        self.env = (os.getenv("OANDA_ENV") or "").strip().upper()  # PRACTICE / LIVE optional

        # Conservative request timeouts
        self.timeout_s = 20

    def name(self) -> str:
        return "oanda"

    def is_configured(self) -> bool:
        return bool(self.api_key and self.account_id and self.base_url)

    # -----------------------------
    # Internals
    # -----------------------------

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _url(self, path: str) -> str:
        # Ensure path begins with /
        p = path if path.startswith("/") else f"/{path}"
        return f"{self.base_url}{p}"

    def _request_json(self, method: str, path: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if not self.is_configured():
            raise RuntimeError("OANDA not configured: set OANDA_API_KEY, OANDA_ACCOUNT_ID and OANDA_BASE_URL.")

        url = self._url(path)
        try:
            resp = requests.request(
                method=method.upper(),
                url=url,
                headers=self._headers(),
                data=None if payload is None else json.dumps(payload),
                timeout=self.timeout_s,
            )
        except Exception as e:
            return {
                "ok": False,
                "status": None,
                "data": None,
                "error": f"request_failed: {e}",
                "url": url,
                "method": method.upper(),
            }

        # Best-effort JSON
        try:
            data = resp.json()
        except Exception:
            data = None

        ok = 200 <= resp.status_code < 300
        err_snip = None
        if not ok:
            # Provide a small snippet for debugging (avoid dumping huge blobs)
            if isinstance(data, dict):
                err_snip = data.get("errorMessage") or data.get("message") or str(data)[:300]
            else:
                err_snip = (resp.text or "")[:300] if resp.text is not None else None

        return {
            "ok": ok,
            "status": resp.status_code,
            "data": data,
            "error": err_snip,
            "url": url,
            "method": method.upper(),
        }

    # -----------------------------
    # Public API used by engine/tests
    # -----------------------------

    def list_accounts(self) -> Dict[str, Any]:
        # GET /v3/accounts
        return self._request_json("GET", "/v3/accounts")

    def get_account_summary(self) -> Dict[str, Any]:
        # GET /v3/accounts/{accountID}/summary
        res = self._request_json("GET", f"/v3/accounts/{self.account_id}/summary")
        if not res.get("ok"):
            return res

        data = res.get("data") or {}
        acct = data.get("account") if isinstance(data, dict) else None
        if not isinstance(acct, dict):
            # Keep structured response but flag parsing issue
            res["ok"] = False
            res["error"] = "parse_error: response missing 'account' dict"
            return res

        # OANDA returns balance & NAV as strings
        balance = acct.get("balance")
        nav = acct.get("NAV") or acct.get("nav")  # belt & suspenders

        res["summary"] = {
            "balance": balance,
            "NAV": nav,
            "currency": acct.get("currency"),
            "id": acct.get("id"),
        }
        return res

    def get_open_positions(self) -> Dict[str, Any]:
        # GET /v3/accounts/{accountID}/openPositions
        return self._request_json("GET", f"/v3/accounts/{self.account_id}/openPositions")

    def get_position_for_instrument(self, symbol: str) -> Dict[str, Any]:
        sym = (symbol or "").strip()
        if not sym:
            return {"ok": False, "status": None, "data": None, "error": "invalid_symbol"}
        # GET /v3/accounts/{accountID}/positions/{instrument}
        return self._request_json("GET", f"/v3/accounts/{self.account_id}/positions/{sym}")

    def place_order(self, req_or_symbol: Union[OrderRequest, str], units: Optional[int] = None) -> Dict[str, Any]:
        """
        Accepts:
          - OrderRequest(symbol="EUR_USD", units=1, side="BUY"/"SELL")
          - symbol string + units (int). Side defaults BUY for units>0, SELL for units<0.

        For now: MARKET only.
        """
        # Normalize
        if isinstance(req_or_symbol, OrderRequest):
            symbol = (req_or_symbol.symbol or "").strip()
            u = int(req_or_symbol.units)
            side = (req_or_symbol.side or "BUY").upper()
            order_type = (req_or_symbol.order_type or "MARKET").upper()
        else:
            symbol = (req_or_symbol or "").strip()
            if units is None:
                return {"ok": False, "status": None, "data": None, "error": "units_required_when_symbol_string"}
            u = int(units)
            side = "BUY" if u >= 0 else "SELL"
            order_type = "MARKET"

        if not symbol:
            return {"ok": False, "status": None, "data": None, "error": "invalid_symbol"}

        if order_type != "MARKET":
            return {"ok": False, "status": None, "data": None, "error": f"unsupported_order_type:{order_type}"}

        # OANDA: units sign indicates direction (positive=buy, negative=sell)
        final_units = abs(u)
        if side == "SELL":
            final_units = -final_units

        payload = {
            "order": {
                "type": "MARKET",
                "instrument": symbol,
                "units": str(final_units),
                "timeInForce": "FOK",
                "positionFill": "DEFAULT",
            }
        }

        # POST /v3/accounts/{accountID}/orders
        return self._request_json("POST", f"/v3/accounts/{self.account_id}/orders", payload)

    def close_trade(self, trade_id: Union[str, int]) -> Dict[str, Any]:
        tid = str(trade_id).strip()
        if not tid:
            return {"ok": False, "status": None, "data": None, "error": "invalid_trade_id"}
        # PUT /v3/accounts/{accountID}/trades/{tradeID}/close
        return self._request_json("PUT", f"/v3/accounts/{self.account_id}/trades/{tid}/close", {})

    def close_position(self, symbol: str) -> Dict[str, Any]:
        sym = (symbol or "").strip()
        if not sym:
            return {"ok": False, "status": None, "data": None, "error": "invalid_symbol"}
        # PUT /v3/accounts/{accountID}/positions/{instrument}/close
        # Close long and short if present
        payload = {"longUnits": "ALL", "shortUnits": "ALL"}
        return self._request_json("PUT", f"/v3/accounts/{self.account_id}/positions/{sym}/close", payload)

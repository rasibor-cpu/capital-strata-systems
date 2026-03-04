"""
Coinbase Executor (LIVE-SAFE) — Capital Strata Systems (CSS)

Design goals:
- DRY_RUN by default (never places real trades unless explicitly armed + live mode).
- Hard safety gate:
    - TRADE_MODE must be LIVE
    - LIVE_TRADING_ARMED must be YES
- Optional notional cap to prevent accidental large orders.

Env vars:
- COINBASE_KEY_JSON   (default: coinbase_key.json)
- COINBASE_ENV        (default: live)   [we only allow live in this module]
- TRADE_MODE          (DRY_RUN | PAPER | LIVE)  default: DRY_RUN
- LIVE_TRADING_ARMED  (YES | NO)        default: NO
- MAX_LIVE_QUOTE      (default: 5)      maximum quote amount allowed for LIVE orders (e.g., 5 USDC)
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _env(name: str, default: str = "") -> str:
    v = os.getenv(name)
    return default if v is None else str(v).strip()


def _env_upper(name: str, default: str = "") -> str:
    return _env(name, default).upper()


def _as_float(s: str, default: float) -> float:
    try:
        return float(s)
    except Exception:
        return default


@dataclass(frozen=True)
class OrderIntent:
    product_id: str              # e.g. "BTC-USDC"
    side: str                    # "BUY" or "SELL"
    order_type: str              # "MARKET" or "LIMIT"
    quote_size: Optional[str] = None     # MARKET buy by quote_size
    base_size: Optional[str] = None      # MARKET sell by base_size; LIMIT uses base_size
    limit_price: Optional[str] = None    # required for LIMIT
    client_order_id: Optional[str] = None


class CoinbaseExecutor:
    """
    A thin execution layer for Coinbase Advanced Trade using the installed Coinbase SDK.

    IMPORTANT:
    - This module is execution-only (no strategy).
    - It refuses LIVE orders unless explicitly armed.
    """

    def __init__(self) -> None:
        self.coinbase_env = _env("COINBASE_ENV", "live").lower()
        self.trade_mode = _env_upper("TRADE_MODE", "DRY_RUN")
        self.armed = _env_upper("LIVE_TRADING_ARMED", "NO") == "YES"

        self.key_json_path = Path(_env("COINBASE_KEY_JSON", "coinbase_key.json")).resolve()

        # Hard cap on LIVE order quote amount (prevents accidents)
        self.max_live_quote = _as_float(_env("MAX_LIVE_QUOTE", "5"), 5.0)

        if self.coinbase_env != "live":
            raise RuntimeError("CoinbaseExecutor only supports COINBASE_ENV=live (for safety).")

        if not self.key_json_path.exists():
            raise RuntimeError(f"Missing Coinbase key JSON file: {self.key_json_path}")

        self._client = self._init_client()

    def _init_client(self):
        """
        Initializes Coinbase RESTClient from the local key JSON file.
        Supports common field names found in downloaded key files.
        """
        try:
            from coinbase.rest import RESTClient  # type: ignore
        except Exception as e:
            raise RuntimeError(f"Coinbase SDK not available. Ensure 'coinbase' is installed in venv. Root error: {e}")

        with self.key_json_path.open("r", encoding="utf-8") as f:
            key_data = json.load(f)

        api_key = key_data.get("name") or key_data.get("apiKey") or key_data.get("api_key")
        api_secret = key_data.get("privateKey") or key_data.get("private_key") or key_data.get("secret")

        if not api_key or not api_secret:
            raise RuntimeError("Key JSON missing required fields. Expected 'name' and 'privateKey'.")

        return RESTClient(api_key=api_key, api_secret=api_secret)

    # -----------------------------
    # Helpers: guardrails
    # -----------------------------

    def _live_allowed(self) -> bool:
        return self.trade_mode == "LIVE" and self.armed

    def _assert_live_allowed(self) -> None:
        if not self._live_allowed():
            raise RuntimeError("LIVE order blocked: require TRADE_MODE=LIVE and LIVE_TRADING_ARMED=YES")

    def _new_client_order_id(self) -> str:
        return f"CSS-{uuid.uuid4().hex[:24]}"

    # -----------------------------
    # Coinbase API wrappers
    # -----------------------------

    def get_key_permissions(self) -> Dict[str, Any]:
        """
        Calls GET /api/v3/brokerage/key_permissions
        """
        return self._call("GET", "/api/v3/brokerage/key_permissions", data=None)

    def get_accounts(self) -> Dict[str, Any]:
        """
        Uses your SDK’s standard accounts endpoint if present.
        Falls back to direct call if needed.
        """
        # Try SDK helper method first if it exists (some versions expose .get_accounts()).
        if hasattr(self._client, "get_accounts"):
            return self._client.get_accounts()  # type: ignore
        return self._call("GET", "/api/v3/brokerage/accounts", data=None)

    def create_order(self, intent: OrderIntent) -> Dict[str, Any]:
        """
        Creates an order (LIVE-SAFE).

        MARKET:
          - BUY requires quote_size
          - SELL typically uses base_size (supported here)

        LIMIT:
          - requires base_size + limit_price
        """
        side = intent.side.strip().upper()
        order_type = intent.order_type.strip().upper()
        product_id = intent.product_id.strip().upper()

        if side not in {"BUY", "SELL"}:
            raise ValueError("side must be BUY or SELL")
        if order_type not in {"MARKET", "LIMIT"}:
            raise ValueError("order_type must be MARKET or LIMIT")

        client_order_id = intent.client_order_id or self._new_client_order_id()

        payload: Dict[str, Any] = {
            "client_order_id": client_order_id,
            "product_id": product_id,
            "side": side,
        }

        if order_type == "MARKET":
            # Coinbase Advanced Trade market configuration naming differs across examples/SDK versions.
            # The SDK generally accepts the official REST payload under "order_configuration".
            cfg: Dict[str, Any] = {"market_market_ioc": {}}
            mm = cfg["market_market_ioc"]

            if side == "BUY":
                if not intent.quote_size:
                    raise ValueError("MARKET BUY requires quote_size")
                mm["quote_size"] = str(intent.quote_size)

                # LIVE cap enforcement (quote currency)
                if self._live_allowed():
                    q = _as_float(str(intent.quote_size), 0.0)
                    if q > self.max_live_quote:
                        raise RuntimeError(
                            f"LIVE order blocked by MAX_LIVE_QUOTE cap: {q} > {self.max_live_quote}"
                        )

            else:  # SELL
                if not intent.base_size:
                    raise ValueError("MARKET SELL requires base_size")
                mm["base_size"] = str(intent.base_size)

            payload["order_configuration"] = cfg

        else:  # LIMIT
            if not intent.base_size or not intent.limit_price:
                raise ValueError("LIMIT requires base_size and limit_price")

            payload["order_configuration"] = {
                "limit_limit_gtc": {
                    "base_size": str(intent.base_size),
                    "limit_price": str(intent.limit_price),
                }
            }

        # DRY_RUN / PAPER: never send a real order
        if not self._live_allowed():
            return {
                "ts_utc": _utc_iso(),
                "dry_run": True,
                "mode": self.trade_mode,
                "armed": self.armed,
                "payload": payload,
            }

        # LIVE: hard gate
        self._assert_live_allowed()

        # Try SDK helper first if present
        if hasattr(self._client, "create_order"):
            return self._client.create_order(**payload)  # type: ignore

        # Otherwise call REST directly
        return self._call("POST", "/api/v3/brokerage/orders", data=payload)

    # -----------------------------
    # Low-level call compatibility
    # -----------------------------

    def _call(self, method: str, path: str, data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Uses the most compatible low-level method available on the installed SDK client.
        """
        client = self._client

        # Some SDK versions expose .request(method, path, **kwargs)
        if hasattr(client, "request"):
            kwargs = {}
            if data is not None:
                kwargs["data"] = data
            return client.request(method, path, **kwargs)  # type: ignore

        # Some SDK versions expose .get/.post convenience methods
        m = method.upper()
        if m == "GET" and hasattr(client, "get"):
            return client.get(path)  # type: ignore
        if m == "POST" and hasattr(client, "post"):
            return client.post(path, data=data)  # type: ignore

        raise RuntimeError("Unsupported Coinbase SDK client interface (no request/get/post found).")
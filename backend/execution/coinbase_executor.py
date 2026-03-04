"""
Coinbase Executor (LIVE-SAFE) — Capital Strata Systems (CSS)

Key fix:
- Coinbase SDK may return rich response objects (e.g., CreateOrderResponse).
- This module now NORMALIZES all responses to plain Python dicts so callers can safely use .get()

Safety gates:
- DRY_RUN by default
- LIVE requires:
    TRADE_MODE=LIVE
    LIVE_TRADING_ARMED=YES
- Optional max notional cap for LIVE orders:
    MAX_LIVE_QUOTE (default 5.0)
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
        return float(str(s).strip())
    except Exception:
        return default


def _to_plain_dict(obj: Any) -> Dict[str, Any]:
    """
    Normalize Coinbase SDK responses to plain dict.

    Handles:
    - dict already
    - pydantic/dataclass-like: model_dump(), dict(), __dict__
    - custom SDK response objects: to_dict()
    - JSON-serializable fallback
    """
    if obj is None:
        return {}

    if isinstance(obj, dict):
        return obj

    # Common in pydantic v2
    if hasattr(obj, "model_dump"):
        try:
            return obj.model_dump()  # type: ignore
        except Exception:
            pass

    # Common in pydantic v1 / other libs
    if hasattr(obj, "dict"):
        try:
            return obj.dict()  # type: ignore
        except Exception:
            pass

    # Some SDKs provide to_dict
    if hasattr(obj, "to_dict"):
        try:
            return obj.to_dict()  # type: ignore
        except Exception:
            pass

    # Dataclass / plain object
    if hasattr(obj, "__dict__"):
        try:
            # filter out private attrs
            d = {k: v for k, v in obj.__dict__.items() if not str(k).startswith("_")}
            # ensure it's JSON-safe where possible
            return json.loads(json.dumps(d, default=str))
        except Exception:
            pass

    # Last resort: attempt JSON roundtrip
    try:
        return json.loads(json.dumps(obj, default=str))
    except Exception:
        return {"_raw": str(obj)}


@dataclass(frozen=True)
class OrderIntent:
    product_id: str              # e.g. "BTC-USDC"
    side: str                    # "BUY" or "SELL"
    order_type: str              # "MARKET" or "LIMIT"
    quote_size: Optional[str] = None     # MARKET BUY by quote_size
    base_size: Optional[str] = None      # MARKET SELL by base_size; LIMIT uses base_size
    limit_price: Optional[str] = None    # required for LIMIT
    client_order_id: Optional[str] = None


class CoinbaseExecutor:
    """
    Execution layer for Coinbase Advanced Trade.
    Always returns dict responses.
    """

    def __init__(self) -> None:
        self.coinbase_env = _env("COINBASE_ENV", "live").lower()
        self.trade_mode = _env_upper("TRADE_MODE", "DRY_RUN")
        self.armed = _env_upper("LIVE_TRADING_ARMED", "NO") == "YES"

        self.key_json_path = Path(_env("COINBASE_KEY_JSON", "coinbase_key.json")).resolve()

        # Hard cap on LIVE order quote notional
        self.max_live_quote = _as_float(_env("MAX_LIVE_QUOTE", "5.0"), 5.0)

        if self.coinbase_env != "live":
            raise RuntimeError("CoinbaseExecutor only supports COINBASE_ENV=live (safety).")

        if not self.key_json_path.exists():
            raise RuntimeError(f"Missing Coinbase key JSON file: {self.key_json_path}")

        self._client = self._init_client()

    def _init_client(self):
        try:
            from coinbase.rest import RESTClient  # type: ignore
        except Exception as e:
            raise RuntimeError(
                f"Coinbase SDK not available. Ensure 'coinbase' is installed in venv. Root error: {e}"
            )

        with self.key_json_path.open("r", encoding="utf-8") as f:
            key_data = json.load(f)

        api_key = key_data.get("name") or key_data.get("apiKey") or key_data.get("api_key")
        api_secret = key_data.get("privateKey") or key_data.get("private_key") or key_data.get("secret")

        if not api_key or not api_secret:
            raise RuntimeError("Key JSON missing required fields. Expected 'name' and 'privateKey'.")

        return RESTClient(api_key=api_key, api_secret=api_secret)

    # -----------------------------
    # Safety gate helpers
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
        return _to_plain_dict(self._call("GET", "/api/v3/brokerage/key_permissions", data=None))

    def get_accounts(self) -> Dict[str, Any]:
        if hasattr(self._client, "get_accounts"):
            return _to_plain_dict(self._client.get_accounts())  # type: ignore
        return _to_plain_dict(self._call("GET", "/api/v3/brokerage/accounts", data=None))

    def create_order(self, intent: OrderIntent) -> Dict[str, Any]:
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
            cfg: Dict[str, Any] = {"market_market_ioc": {}}
            mm = cfg["market_market_ioc"]

            if side == "BUY":
                if not intent.quote_size:
                    raise ValueError("MARKET BUY requires quote_size")
                mm["quote_size"] = str(intent.quote_size)

                # LIVE notional cap
                if self._live_allowed():
                    q = _as_float(str(intent.quote_size), 0.0)
                    if q > self.max_live_quote:
                        raise RuntimeError(f"LIVE blocked by MAX_LIVE_QUOTE cap: {q} > {self.max_live_quote}")

            else:  # SELL
                if not intent.base_size:
                    raise ValueError("MARKET SELL requires base_size")
                mm["base_size"] = str(intent.base_size)

            payload["order_configuration"] = cfg

        else:  # LIMIT
            if not intent.base_size or not intent.limit_price:
                raise ValueError("LIMIT requires base_size and limit_price")
            payload["order_configuration"] = {
                "limit_limit_gtc": {"base_size": str(intent.base_size), "limit_price": str(intent.limit_price)}
            }

        # DRY_RUN / PAPER: never send
        if not self._live_allowed():
            return {
                "ts_utc": _utc_iso(),
                "dry_run": True,
                "mode": self.trade_mode,
                "armed": self.armed,
                "payload": payload,
            }

        # LIVE gate
        self._assert_live_allowed()

        # Try SDK helper if present
        if hasattr(self._client, "create_order"):
            resp = self._client.create_order(**payload)  # type: ignore
            d = _to_plain_dict(resp)
            d.setdefault("ts_utc", _utc_iso())
            d.setdefault("dry_run", False)
            d.setdefault("mode", self.trade_mode)
            d.setdefault("armed", self.armed)
            d.setdefault("payload", payload)
            return d

        # Fallback REST direct
        resp = self._call("POST", "/api/v3/brokerage/orders", data=payload)
        d = _to_plain_dict(resp)
        d.setdefault("ts_utc", _utc_iso())
        d.setdefault("dry_run", False)
        d.setdefault("mode", self.trade_mode)
        d.setdefault("armed", self.armed)
        d.setdefault("payload", payload)
        return d

    # -----------------------------
    # Low-level call compatibility
    # -----------------------------

    def _call(self, method: str, path: str, data: Optional[Dict[str, Any]]) -> Any:
        client = self._client

        if hasattr(client, "request"):
            kwargs = {}
            if data is not None:
                kwargs["data"] = data
            return client.request(method, path, **kwargs)  # type: ignore

        m = method.upper()
        if m == "GET" and hasattr(client, "get"):
            return client.get(path)  # type: ignore
        if m == "POST" and hasattr(client, "post"):
            return client.post(path, data=data)  # type: ignore

        raise RuntimeError("Unsupported Coinbase SDK client interface (no request/get/post found).")
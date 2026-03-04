from __future__ import annotations

import glob
import json
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from coinbase.rest import RESTClient


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _env(name: str, default: str) -> str:
    v = os.getenv(name)
    return default if v is None else str(v).strip()


def _as_int(s: str, default: int) -> int:
    try:
        return int(str(s).strip())
    except Exception:
        return default


def _pick_key_file() -> Path:
    explicit = _env("COINBASE_KEY_JSON", "")
    if explicit:
        p = Path(explicit).expanduser().resolve()
        if p.exists():
            return p
        raise FileNotFoundError(f"COINBASE_KEY_JSON path not found: {p}")

    p1 = Path("coinbase_key.json").resolve()
    if p1.exists():
        return p1

    matches = [Path(m).resolve() for m in glob.glob("cdp_api_key*.json")]
    if matches:
        matches.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return matches[0]

    raise FileNotFoundError(
        "No Coinbase key JSON found. Expected COINBASE_KEY_JSON env var OR coinbase_key.json OR cdp_api_key*.json in repo root."
    )


def _to_plain_dict(obj: Any) -> Dict[str, Any]:
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "model_dump"):
        try:
            return obj.model_dump()  # type: ignore
        except Exception:
            pass
    if hasattr(obj, "dict"):
        try:
            return obj.dict()  # type: ignore
        except Exception:
            pass
    if hasattr(obj, "to_dict"):
        try:
            return obj.to_dict()  # type: ignore
        except Exception:
            pass
    if hasattr(obj, "__dict__"):
        try:
            return {k: v for k, v in obj.__dict__.items() if not str(k).startswith("_")}
        except Exception:
            pass
    return {"_raw": str(obj)}


def _safe_float(x: Any) -> Optional[float]:
    try:
        return float(x)
    except Exception:
        return None


@dataclass(frozen=True)
class OrderIntent:
    product_id: str
    side: str              # BUY/SELL
    order_type: str        # MARKET/LIMIT
    quote_size: Optional[str] = None
    base_size: Optional[str] = None
    limit_price: Optional[str] = None
    client_order_id: Optional[str] = None


class CoinbaseExecutor:
    """
    Coinbase Advanced Trade executor.
    """

    def __init__(self) -> None:
        self.trade_mode = _env("TRADE_MODE", "DRY_RUN").upper()
        self.armed = _env("LIVE_TRADING_ARMED", "NO").upper() == "YES"
        self.key_json_path = _pick_key_file()
        self._client = self._init_client()

    def _init_client(self) -> RESTClient:
        data = json.loads(self.key_json_path.read_text(encoding="utf-8"))

        api_key = data.get("name") or data.get("apiKey") or data.get("api_key")
        api_secret = data.get("privateKey") or data.get("private_key") or data.get("secret")

        if not api_key or not api_secret:
            raise RuntimeError(
                f"Key JSON missing fields. Expected 'name' and 'privateKey'. File: {self.key_json_path}"
            )

        return RESTClient(api_key=api_key, api_secret=api_secret)

    def _new_client_order_id(self) -> str:
        return f"CSS-{uuid.uuid4().hex[:24]}"

    def _live_allowed(self) -> bool:
        return self.trade_mode == "LIVE" and self.armed

    # -----------------------------
    # Market data
    # -----------------------------

    def get_best_bid_ask(self, product_id: str, limit: int = 1) -> Optional[Dict[str, float]]:
        """
        Uses Advanced Trade product book endpoint (top-of-book).
        Returns {"bid": float, "ask": float} or None.
        """
        try:
            book = _to_plain_dict(self._client.get_product_book(product_id=product_id, limit=limit))  # type: ignore
            pricebook = book.get("pricebook") or {}
            bids = pricebook.get("bids") or []
            asks = pricebook.get("asks") or []

            if not bids or not asks:
                return None

            bid = _safe_float(bids[0].get("price") if isinstance(bids[0], dict) else None)
            ask = _safe_float(asks[0].get("price") if isinstance(asks[0], dict) else None)

            if bid is None or ask is None:
                return None

            return {"bid": float(bid), "ask": float(ask)}

        except Exception:
            return None

    def get_candles(self, product_id: str, granularity: str) -> Dict[str, Any]:
        """
        Coinbase SDK requires start/end. We send UNIX epoch seconds which the API accepts reliably.

        Env override:
          CANDLES_LOOKBACK_HOURS (default 24)
        """
        lookback_hours = _as_int(_env("CANDLES_LOOKBACK_HOURS", "24"), 24)

        end_dt = datetime.now(timezone.utc)
        start_dt = end_dt - timedelta(hours=lookback_hours)

        # UNIX seconds (ints)
        start = int(start_dt.timestamp())
        end = int(end_dt.timestamp())

        resp = self._client.get_candles(  # type: ignore
            product_id=product_id,
            start=start,
            end=end,
            granularity=granularity,
        )
        return _to_plain_dict(resp)

    # -----------------------------
    # Orders
    # -----------------------------

    def create_order(self, intent: OrderIntent) -> Dict[str, Any]:
        client_order_id = intent.client_order_id or self._new_client_order_id()

        payload: Dict[str, Any] = {
            "client_order_id": client_order_id,
            "product_id": intent.product_id,
            "side": intent.side.upper(),
        }

        order_type = intent.order_type.upper()
        if order_type == "MARKET":
            cfg: Dict[str, Any] = {"market_market_ioc": {}}
            mm = cfg["market_market_ioc"]

            if payload["side"] == "BUY":
                if not intent.quote_size:
                    raise ValueError("MARKET BUY requires quote_size")
                mm["quote_size"] = str(intent.quote_size)
            else:
                if not intent.base_size:
                    raise ValueError("MARKET SELL requires base_size")
                mm["base_size"] = str(intent.base_size)

            payload["order_configuration"] = cfg

        elif order_type == "LIMIT":
            if not intent.base_size or not intent.limit_price:
                raise ValueError("LIMIT requires base_size and limit_price")
            payload["order_configuration"] = {
                "limit_limit_gtc": {"base_size": str(intent.base_size), "limit_price": str(intent.limit_price)}
            }
        else:
            raise ValueError("order_type must be MARKET or LIMIT")

        if not self._live_allowed():
            return {
                "ts_utc": _utc_iso(),
                "dry_run": True,
                "mode": self.trade_mode,
                "armed": self.armed,
                "payload": payload,
                "key_file": str(self.key_json_path),
            }

        resp = self._client.create_order(**payload)  # type: ignore
        d = _to_plain_dict(resp)
        d.setdefault("ts_utc", _utc_iso())
        d.setdefault("dry_run", False)
        d.setdefault("mode", self.trade_mode)
        d.setdefault("armed", self.armed)
        d.setdefault("payload", payload)
        d.setdefault("key_file", str(self.key_json_path))
        return d
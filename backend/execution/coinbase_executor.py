from __future__ import annotations

import glob
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

try:
    from coinbase.rest import RESTClient  # type: ignore
except Exception:  # pragma: no cover
    RESTClient = None  # type: ignore


# -----------------------------
# Order intent (tolerant container)
# -----------------------------

class OrderIntent:
    """
    Strategy passes an OrderIntent into executor.create_order(intent).

    This is intentionally tolerant: strategy may include extra kwargs
    (order_type, limit_price, etc.). Executor should not crash.
    """

    def __init__(
        self,
        product_id: str,
        side: str,
        quote_size: Any,
        client_order_id: Optional[str] = None,
        take_profit_pct: float = 0.0,
        stop_loss_pct: float = 0.0,
        order_type: str = "MARKET",
        limit_price: Optional[Any] = None,
        **extra: Any,
    ) -> None:
        self.product_id = str(product_id)
        self.side = str(side).upper()
        self.quote_size = quote_size
        self.client_order_id = client_order_id
        self.take_profit_pct = float(take_profit_pct or 0.0)
        self.stop_loss_pct = float(stop_loss_pct or 0.0)
        self.order_type = str(order_type).upper() if order_type else "MARKET"
        self.limit_price = limit_price
        self.extra: Dict[str, Any] = dict(extra)

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "product_id": self.product_id,
            "side": self.side,
            "quote_size": self.quote_size,
            "client_order_id": self.client_order_id,
            "take_profit_pct": self.take_profit_pct,
            "stop_loss_pct": self.stop_loss_pct,
            "order_type": self.order_type,
            "limit_price": self.limit_price,
        }
        d.update(self.extra)
        return d


# -----------------------------
# Helpers
# -----------------------------

def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _granularity_to_seconds(granularity: str) -> int:
    g = str(granularity).upper().strip()
    mapping = {
        "ONE_MINUTE": 60,
        "FIVE_MINUTE": 300,
        "FIFTEEN_MINUTE": 900,
        "THIRTY_MINUTE": 1800,
        "ONE_HOUR": 3600,
        "TWO_HOUR": 7200,
        "SIX_HOUR": 21600,
        "ONE_DAY": 86400,
    }
    if g.isdigit():
        return int(g)
    return mapping.get(g, 900)


def _coalesce(*vals: Any) -> Any:
    for v in vals:
        if v is not None:
            return v
    return None


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        if v is None:
            return default
        return float(v)
    except Exception:
        return default


def _new_id(prefix: str = "PAPER") -> str:
    # stable-enough unique id for paper fills
    return f"{prefix}-{int(time.time()*1000)}"


# -----------------------------
# Coinbase Executor
# -----------------------------

class CoinbaseExecutor:
    """
    Coinbase executor used by the engine.

    Supports:
      - auto-load CDP key json (so no env reset needed)
      - get_best_bid_ask
      - get_candles (epoch seconds)
      - create_order (PAPER fill simulation)

    NOTE:
      In PAPER mode, create_order() does NOT hit Coinbase.
      The engine's higher layers should manage TP/SL and logging.
    """

    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None) -> None:
        if RESTClient is None:
            raise RuntimeError(
                "Coinbase RESTClient import failed. Confirm coinbase-advanced-py is installed in this venv."
            )

        api_key = api_key or os.getenv("COINBASE_API_KEY")
        api_secret = api_secret or os.getenv("COINBASE_API_SECRET")

        if not api_key or not api_secret:
            api_key, api_secret = self._auto_load_from_cdp_json()

        if not api_key or not api_secret:
            raise RuntimeError(
                "Missing COINBASE_API_KEY / COINBASE_API_SECRET (and could not auto-load from Downloads)."
            )

        self.client = RESTClient(api_key=api_key, api_secret=api_secret)

    # ---------- Auto "login" / key loading ----------

    def _auto_load_from_cdp_json(self) -> Tuple[Optional[str], Optional[str]]:
        home = os.path.expanduser("~")
        downloads = os.path.join(home, "Downloads")

        patterns = [
            os.path.join(downloads, "cdp_api_key*.json"),
            os.path.join(downloads, "cdp_api-key*.json"),
        ]

        candidates: List[str] = []
        for p in patterns:
            candidates.extend(glob.glob(p))

        if not candidates:
            return None, None

        candidates.sort(key=lambda fp: os.path.getmtime(fp), reverse=True)
        keyfile = candidates[0]

        try:
            import json

            with open(keyfile, "r", encoding="utf-8") as f:
                j = json.load(f)

            api_key = _coalesce(j.get("name"), j.get("apiKey"), j.get("key"), j.get("client_id"))
            api_secret = _coalesce(j.get("privateKey"), j.get("apiSecret"), j.get("secret"), j.get("private_key"))

            if api_key:
                os.environ["COINBASE_API_KEY"] = str(api_key)
            if api_secret:
                os.environ["COINBASE_API_SECRET"] = str(api_secret)

            return (str(api_key) if api_key else None, str(api_secret) if api_secret else None)
        except Exception:
            return None, None

    # ---------- Market Data ----------

    def get_best_bid_ask(self, product_id: str) -> Dict[str, float]:
        try:
            fn = getattr(self.client, "get_best_bid_ask", None)
            if callable(fn):
                resp = fn(product_ids=[product_id])
                data = resp if isinstance(resp, dict) else resp.to_dict()

                pb = None
                if isinstance(data, dict):
                    pb = _coalesce(
                        data.get("pricebooks"),
                        data.get("data", {}).get("pricebooks") if isinstance(data.get("data"), dict) else None,
                        data.get("response", {}).get("pricebooks") if isinstance(data.get("response"), dict) else None,
                    )
                if isinstance(pb, list) and pb and isinstance(pb[0], dict):
                    book = pb[0]
                    bids = book.get("bids") or []
                    asks = book.get("asks") or []
                    bid = _safe_float(bids[0].get("price")) if bids and isinstance(bids[0], dict) else 0.0
                    ask = _safe_float(asks[0].get("price")) if asks and isinstance(asks[0], dict) else 0.0
                    if bid > 0 and ask > 0:
                        return {"bid": bid, "ask": ask}
        except Exception:
            pass

        try:
            fn2 = getattr(self.client, "get_product", None)
            if callable(fn2):
                resp2 = fn2(product_id)
                data2 = resp2 if isinstance(resp2, dict) else resp2.to_dict()
                if isinstance(data2, dict):
                    d = data2.get("product") if isinstance(data2.get("product"), dict) else data2
                    bid = _safe_float(_coalesce(d.get("best_bid"), d.get("bid")))
                    ask = _safe_float(_coalesce(d.get("best_ask"), d.get("ask")))
                    if bid > 0 and ask > 0:
                        return {"bid": bid, "ask": ask}
        except Exception:
            pass

        return {"bid": 0.0, "ask": 0.0}

    def get_candles(self, product_id: str, granularity: str, limit: int = 300) -> List[Dict[str, Any]]:
        gran_sec = _granularity_to_seconds(granularity)

        end_dt = _utc_now().replace(microsecond=0)
        start_dt = end_dt - timedelta(seconds=gran_sec * limit)

        start_epoch = int(start_dt.timestamp())
        end_epoch = int(end_dt.timestamp())

        resp = self.client.get_candles(
            product_id=product_id,
            start=start_epoch,
            end=end_epoch,
            granularity=granularity,
        )
        data = resp if isinstance(resp, dict) else resp.to_dict()
        return self._normalize_candles(data)

    def _normalize_candles(self, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        candles = None
        if isinstance(payload, dict):
            if isinstance(payload.get("candles"), list):
                candles = payload["candles"]
            elif isinstance(payload.get("data"), dict) and isinstance(payload["data"].get("candles"), list):
                candles = payload["data"]["candles"]
            elif isinstance(payload.get("response"), dict) and isinstance(payload["response"].get("candles"), list):
                candles = payload["response"]["candles"]

        if candles is None:
            return []

        out: List[Dict[str, Any]] = []
        for c in candles:
            if not isinstance(c, dict):
                continue
            out.append(
                {
                    "start": c.get("start") or c.get("time") or c.get("timestamp"),
                    "open": _safe_float(c.get("open")),
                    "high": _safe_float(c.get("high")),
                    "low": _safe_float(c.get("low")),
                    "close": _safe_float(c.get("close")),
                    "volume": _safe_float(c.get("volume")),
                }
            )

        out.sort(key=lambda x: str(x.get("start") or ""))
        return out

    # ---------- Trading ----------

    def create_order(self, intent: Any) -> Dict[str, Any]:
        """
        PAPER mode: simulate an immediate fill at mid price.

        The engine handles TP/SL and logging elsewhere, so we just return a
        normalized "order" object with fill price and size.
        """
        # Allow either our OrderIntent or a dict-like object
        if hasattr(intent, "to_dict"):
            d = intent.to_dict()
        elif isinstance(intent, dict):
            d = intent
        else:
            # best effort object->dict
            d = {k: getattr(intent, k) for k in dir(intent) if not k.startswith("_")}

        product_id = str(d.get("product_id"))
        side = str(d.get("side", "")).upper()
        quote_size = _safe_float(d.get("quote_size"), 0.0)

        # price: mid of best bid/ask
        bba = self.get_best_bid_ask(product_id)
        bid = _safe_float(bba.get("bid"), 0.0)
        ask = _safe_float(bba.get("ask"), 0.0)
        mid = (bid + ask) / 2.0 if (bid > 0 and ask > 0) else max(bid, ask, 0.0)

        # For spot: base_size ≈ quote_size / price (if price known)
        base_size = (quote_size / mid) if (mid > 0 and quote_size > 0) else 0.0

        order_id = _new_id("PAPER")
        fill_time = _utc_now().isoformat()

        return {
            "id": order_id,
            "status": "FILLED",
            "product_id": product_id,
            "side": side,
            "order_type": str(d.get("order_type", "MARKET")),
            "quote_size": quote_size,
            "base_size": base_size,
            "fill_price": mid,
            "fill_time": fill_time,
            "client_order_id": d.get("client_order_id"),
            "take_profit_pct": _safe_float(d.get("take_profit_pct"), 0.0),
            "stop_loss_pct": _safe_float(d.get("stop_loss_pct"), 0.0),
            "raw_intent": d,
        }
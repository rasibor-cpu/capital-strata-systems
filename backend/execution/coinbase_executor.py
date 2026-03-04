from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

try:
    from coinbase.rest import RESTClient  # pip: coinbase-advanced-py
except Exception as e:  # pragma: no cover
    RESTClient = None  # type: ignore
    _IMPORT_ERR = e
else:
    _IMPORT_ERR = None


@dataclass(frozen=True)
class OrderIntent:
    product_id: str
    side: str                # "BUY" / "SELL"
    order_type: str          # "MARKET"
    quote_size: Optional[str] = None  # BUY market
    base_size: Optional[str] = None   # SELL market


def _env(name: str, default: str) -> str:
    v = os.getenv(name)
    return default if v is None else str(v).strip()


def _to_dict(x: Any) -> Any:
    if isinstance(x, dict):
        return x
    for attr in ("to_dict", "dict", "model_dump"):
        if hasattr(x, attr):
            try:
                return getattr(x, attr)()
            except Exception:
                pass
    return {"_raw": str(x)}


def _load_keyfile(path: str) -> Dict[str, str]:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Coinbase key file not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        d = json.load(f)
    if not isinstance(d, dict):
        raise ValueError("Coinbase key file is not a JSON object")
    name = str(d.get("name", "")).strip()
    pk = str(d.get("privateKey", "")).strip()
    if not name or not pk:
        raise ValueError("Coinbase key file missing 'name' and/or 'privateKey'")
    return {"name": name, "privateKey": pk}


class CoinbaseExecutor:
    """
    Coinbase Advanced Trade gateway used by strategy_loop.

    Must provide:
      - get_best_bid_ask(product_id, limit=1) -> {"bid":float,"ask":float} | None
      - get_candles(product_id, granularity, start=None, end=None, limit=300) -> dict
      - create_order(OrderIntent) -> dict (paper-safe unless LIVE + ARMED)
    """

    def __init__(self) -> None:
        if RESTClient is None:
            raise RuntimeError(
                "Coinbase SDK not available. Install 'coinbase-advanced-py'. "
                f"Root error: {_IMPORT_ERR}"
            )

        key_file = _env("COINBASE_KEY_FILE", "coinbase_key.json")
        creds = _load_keyfile(key_file)
        self._client = RESTClient(api_key=creds["name"], api_secret=creds["privateKey"])

    def get_best_bid_ask(self, product_id: str, limit: int = 1) -> Optional[Dict[str, float]]:
        """
        Robust parsing across Coinbase response shapes.
        """
        try:
            resp = self._client.get_best_bid_ask(product_id=product_id, limit=limit)
            d = _to_dict(resp)

            # Shape A: {"pricebooks":[{"bids":[{"price":..}], "asks":[{"price":..}]}]}
            if isinstance(d.get("pricebooks"), list) and d["pricebooks"]:
                pb = d["pricebooks"][0]
                bids = pb.get("bids", [])
                asks = pb.get("asks", [])
                if bids and asks:
                    return {"bid": float(bids[0]["price"]), "ask": float(asks[0]["price"])}

            # Shape B: {"pricebook":{"bids":[...], "asks":[...]}}
            pb = d.get("pricebook")
            if isinstance(pb, dict):
                bids = pb.get("bids", [])
                asks = pb.get("asks", [])
                if bids and asks:
                    return {"bid": float(bids[0]["price"]), "ask": float(asks[0]["price"])}

            # Shape C: {"bids":[...], "asks":[...]}
            bids = d.get("bids", [])
            asks = d.get("asks", [])
            if bids and asks:
                return {"bid": float(bids[0]["price"]), "ask": float(asks[0]["price"])}

            # Shape D: {"best_bid":"..","best_ask":".."}
            if "best_bid" in d and "best_ask" in d:
                return {"bid": float(d["best_bid"]), "ask": float(d["best_ask"])}

            return None
        except Exception as e:
            print("BBA_ERROR:", str(e))
            return None

    def get_candles(
        self,
        product_id: str,
        granularity: str,
        start: Optional[str] = None,
        end: Optional[str] = None,
        limit: int = 300,
    ) -> Dict[str, Any]:
        """
        Supports both start/end range and limit-only fallback.
        """
        if start and end:
            try:
                resp = self._client.get_candles(
                    product_id=product_id,
                    start=start,
                    end=end,
                    granularity=granularity,
                )
                return _to_dict(resp)
            except TypeError:
                # SDK variant fallback
                resp = self._client.get_candles(product_id, start, end, granularity)
                return _to_dict(resp)
            except Exception:
                # fall through to limit
                pass

        resp = self._client.get_candles(product_id=product_id, granularity=granularity, limit=limit)
        return _to_dict(resp)

    def _mode(self) -> str:
        return _env("TRADE_MODE", "DRY_RUN").upper()

    def _armed(self) -> bool:
        return _env("LIVE_TRADING_ARMED", "NO").upper() == "YES"

    def create_order(self, intent: OrderIntent) -> Dict[str, Any]:
        """
        DRY_RUN + PAPER: never send to broker.
        LIVE: sends only if ARMED.
        """
        mode = self._mode()
        armed = self._armed()

        payload: Dict[str, Any] = {
            "client_order_id": f"CSS-{int(time.time()*1000)}",
            "product_id": intent.product_id,
            "side": intent.side.upper(),
            "order_configuration": {"market_market_ioc": {}},
        }

        if intent.side.upper() == "BUY":
            if not intent.quote_size:
                raise ValueError("BUY requires quote_size")
            payload["order_configuration"]["market_market_ioc"]["quote_size"] = str(intent.quote_size)
        else:
            if not intent.base_size:
                raise ValueError("SELL requires base_size")
            payload["order_configuration"]["market_market_ioc"]["base_size"] = str(intent.base_size)

        if mode in ("DRY_RUN", "PAPER"):
            return {"mode": mode, "armed": armed, "dry_run": True, "payload": payload}

        if not armed:
            return {"mode": mode, "armed": armed, "dry_run": True, "blocked": True, "reason": "LIVE not armed", "payload": payload}

        resp = self._client.create_order(**payload)
        return {"mode": mode, "armed": armed, "dry_run": False, "payload": payload, "success_response": _to_dict(resp)}
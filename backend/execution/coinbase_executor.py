from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

# Coinbase Advanced Trade SDK (pip: coinbase-advanced-py)
try:
    from coinbase.rest import RESTClient  # type: ignore
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
    quote_size: Optional[str] = None  # for BUY market (quote currency)
    base_size: Optional[str] = None   # for SELL market (base currency)


def _env(name: str, default: str) -> str:
    v = os.getenv(name)
    return default if v is None else str(v).strip()


def _load_coinbase_keyfile(path: str) -> Dict[str, str]:
    """
    Coinbase CDP key file typically contains:
      {
        "name": "organizations/.../apiKeys/.....",
        "privateKey": "-----BEGIN EC PRIVATE KEY-----\n...\n-----END EC PRIVATE KEY-----\n"
      }
    """
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


def _to_dict(x: Any) -> Any:
    """
    Normalize SDK responses to dict where possible (without crashing).
    """
    if isinstance(x, dict):
        return x
    # coinbase-advanced-py often returns pydantic models
    for attr in ("to_dict", "dict", "model_dump"):
        if hasattr(x, attr):
            try:
                fn = getattr(x, attr)
                return fn()
            except Exception:
                pass
    # last resort: string
    try:
        return {"_raw": str(x)}
    except Exception:
        return {"_raw": "<unserializable>"}


class CoinbaseExecutor:
    """
    Order + market data gateway for Coinbase Advanced Trade.
    Supports:
      - get_best_bid_ask(product_id, limit=1)
      - get_candles(product_id, granularity, start=None, end=None, limit=300)
      - create_order(intent)
    """

    def __init__(self) -> None:
        if RESTClient is None:
            raise RuntimeError(
                "Coinbase SDK not available. Install 'coinbase-advanced-py'. "
                f"Root error: {_IMPORT_ERR}"
            )

        # Prefer your persisted filename in repo root
        key_file = _env("COINBASE_KEY_FILE", "coinbase_key.json")
        creds = _load_coinbase_keyfile(key_file)

        # coinbase-advanced-py RESTClient expects api_key + api_secret (private key)
        self._client = RESTClient(api_key=creds["name"], api_secret=creds["privateKey"])

    # ----------------------------
    # Market data
    # ----------------------------
    def get_best_bid_ask(self, product_id: str, limit: int = 1) -> Optional[Dict[str, float]]:
        """
        Returns: {"bid": float, "ask": float} or None
        """
        # SDK method name used in your earlier code path
        resp = self._client.get_best_bid_ask(product_id=product_id, limit=limit)
        d = _to_dict(resp)

        # Common shapes:
        # 1) {"pricebook":{"bids":[{"price":"..."},...], "asks":[{"price":"..."}]}}
        # 2) {"bids":[{"price":"..."}], "asks":[{"price":"..."}]}
        pb = d.get("pricebook", d)

        bids = pb.get("bids", [])
        asks = pb.get("asks", [])

        if not bids or not asks:
            return None

        try:
            bid = float(bids[0].get("price"))
            ask = float(asks[0].get("price"))
            return {"bid": bid, "ask": ask}
        except Exception:
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
        FIX: Accepts start/end (ISO8601) so strategy_loop can pass them.
        If SDK signature differs, we fall back to limit-only.
        Returns a dict with key "candles": list[...]
        """
        # Prefer start/end if supplied (Coinbase endpoint requires both in many cases)
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
                # SDK variant: might want start/end positional or different names
                try:
                    resp = self._client.get_candles(product_id, start, end, granularity)
                    return _to_dict(resp)
                except Exception:
                    pass
            except Exception:
                # fall through to limit-only attempt
                pass

        # Fallback: limit-only (older/internal signature)
        resp = self._client.get_candles(product_id=product_id, granularity=granularity, limit=limit)
        return _to_dict(resp)

    # ----------------------------
    # Orders
    # ----------------------------
    def _mode(self) -> str:
        return _env("TRADE_MODE", "DRY_RUN").upper()

    def _armed(self) -> bool:
        return _env("LIVE_TRADING_ARMED", "NO").upper() == "YES"

    def create_order(self, intent: OrderIntent) -> Dict[str, Any]:
        """
        DRY_RUN: no order sent, returns payload only.
        PAPER:   send order as "paper" (we still DO NOT want live execution); returns payload only.
        LIVE:    sends live order ONLY if LIVE_TRADING_ARMED=YES.
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

        # Safety: DRY_RUN and PAPER never hit live broker
        if mode in ("DRY_RUN", "PAPER"):
            return {
                "ts_utc": _env("UTC_NOW", ""),
                "mode": mode,
                "armed": armed,
                "dry_run": True,
                "payload": payload,
            }

        # LIVE mode
        if not armed:
            return {
                "ts_utc": _env("UTC_NOW", ""),
                "mode": mode,
                "armed": armed,
                "dry_run": True,
                "blocked": True,
                "reason": "LIVE not armed",
                "payload": payload,
            }

        # Live send
        resp = self._client.create_order(**payload)
        return {
            "ts_utc": _env("UTC_NOW", ""),
            "mode": mode,
            "armed": armed,
            "dry_run": False,
            "payload": payload,
            "success_response": _to_dict(resp),
        }
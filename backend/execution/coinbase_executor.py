from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, List


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
    side: str                 # "BUY" / "SELL"
    order_type: str           # "MARKET"
    quote_size: Optional[str] = None     # BUY market
    base_size: Optional[str] = None      # SELL market


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


def _utc_rfc3339(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _flatten_once(x: Any) -> Any:
    # Coinbase responses sometimes show list-of-list-of-dict
    # This flattens one level if needed.
    if isinstance(x, list) and len(x) == 1 and isinstance(x[0], list):
        return x[0]
    return x


def _first_dict(x: Any) -> Optional[Dict[str, Any]]:
    x = _flatten_once(x)
    if isinstance(x, list) and x:
        if isinstance(x[0], dict):
            return x[0]
    return None


class CoinbaseExecutor:
    """
    Coinbase Advanced Trade gateway used by strategy_loop.
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

    # -------------------------------------------------
    # BEST BID / ASK
    # -------------------------------------------------

    def get_best_bid_ask(self, product_id: str, limit: int = 1) -> Optional[Dict[str, float]]:
        """
        FIXED:
        - Coinbase is returning MANY pricebooks; we must select the one matching product_id.
        - Handle nested list shapes for pricebooks/bids/asks.
        """
        try:
            resp = self._client.get_best_bid_ask(product_id=product_id, limit=limit)
            d = _to_dict(resp)

            if _env("DEBUG_BBA", "0") == "1":
                print("DEBUG_BBA_RAW:", d)

            # Normalize pricebooks to a list[dict]
            raw_pricebooks = d.get("pricebooks", [])
            raw_pricebooks = _flatten_once(raw_pricebooks)

            pricebooks: List[Dict[str, Any]] = []
            if isinstance(raw_pricebooks, list):
                for item in raw_pricebooks:
                    if isinstance(item, dict):
                        pricebooks.append(item)
                    elif isinstance(item, list) and item and isinstance(item[0], dict):
                        # list-of-dict wrapped
                        pricebooks.append(item[0])

            # If response is a single pricebook dict
            if not pricebooks:
                pb_single = d.get("pricebook")
                if isinstance(pb_single, dict):
                    pricebooks = [pb_single]

            if not pricebooks:
                return None

            # Select the matching product_id pricebook
            want = product_id.upper()
            pb = None
            for p in pricebooks:
                pid = str(p.get("product_id", "")).upper()
                if pid == want:
                    pb = p
                    break

            # If still not found, we must NOT use random first book (it causes mid=0.01 nonsense)
            if pb is None:
                return None

            bids = _flatten_once(pb.get("bids", []))
            asks = _flatten_once(pb.get("asks", []))

            b0 = _first_dict(bids)
            a0 = _first_dict(asks)
            if not b0 or not a0:
                return None

            bid = float(b0.get("price"))
            ask = float(a0.get("price"))

            if bid <= 0 or ask <= 0 or ask < bid:
                return None

            # sanity: reject absurdly tiny mids for USD/USDC pairs
            mid = (bid + ask) / 2.0
            if mid < 1.0 and ("-USD" in want or "-USDC" in want):
                return None

            return {"bid": bid, "ask": ask}

        except Exception as e:
            print("BBA_ERROR:", str(e))
            return None

    # -------------------------------------------------
    # CANDLES
    # -------------------------------------------------

    def get_candles(
        self,
        product_id: str,
        granularity: str,
        start: Optional[str] = None,
        end: Optional[str] = None,
        limit: int = 300,
    ) -> Dict[str, Any]:
        """
        Coinbase candles often REQUIRE start/end. Auto-generate if missing.
        """
        if not end:
            end_dt = datetime.now(timezone.utc)
            end = _utc_rfc3339(end_dt)
        else:
            end_dt = None

        if not start:
            g = granularity.upper()
            minutes_per = 15
            if "ONE_MINUTE" in g:
                minutes_per = 1
            elif "FIVE_MINUTE" in g:
                minutes_per = 5
            elif "FIFTEEN_MINUTE" in g:
                minutes_per = 15
            elif "THIRTY_MINUTE" in g:
                minutes_per = 30
            elif "ONE_HOUR" in g or "SIXTY_MINUTE" in g:
                minutes_per = 60
            elif "TWO_HOUR" in g:
                minutes_per = 120
            elif "FOUR_HOUR" in g:
                minutes_per = 240
            elif "ONE_DAY" in g or "DAILY" in g:
                minutes_per = 1440

            if end_dt is None:
                end_dt = datetime.now(timezone.utc)

            lookback_minutes = max(60, min(limit * minutes_per, 60 * 24 * 20))
            start_dt = end_dt - timedelta(minutes=lookback_minutes)
            start = _utc_rfc3339(start_dt)

        try:
            resp = self._client.get_candles(
                product_id=product_id,
                start=start,
                end=end,
                granularity=granularity,
            )
            return _to_dict(resp)
        except TypeError:
            resp = self._client.get_candles(product_id, start, end, granularity)
            return _to_dict(resp)
        except Exception as e:
            print("CANDLE_ERROR:", str(e))
            print("CANDLE_DEBUG:", {"product_id": product_id, "granularity": granularity, "start": start, "end": end})
            return {"candles": []}

    # -------------------------------------------------
    # ORDER CREATION
    # -------------------------------------------------

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
            return {
                "mode": mode,
                "armed": armed,
                "dry_run": True,
                "blocked": True,
                "reason": "LIVE not armed",
                "payload": payload,
            }

        resp = self._client.create_order(**payload)
        return {"mode": mode, "armed": armed, "dry_run": False, "payload": payload, "success_response": _to_dict(resp)}
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
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
    # Coinbase typically accepts RFC3339 / ISO-8601
    # e.g. 2026-03-04T17:34:35Z
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class CoinbaseExecutor:
    """
    Coinbase Advanced Trade gateway used by strategy_loop.

    Provides:
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

    # -------------------------------------------------
    # BEST BID / ASK
    # -------------------------------------------------

    def get_best_bid_ask(self, product_id: str, limit: int = 1) -> Optional[Dict[str, float]]:
        """
        Robust parsing across Coinbase response shapes, plus sanity checks.
        If the parsed values look wrong, we return None (strategy will skip tick).
        """
        try:
            resp = self._client.get_best_bid_ask(product_id=product_id, limit=limit)
            d = _to_dict(resp)

            def _extract_bid_ask(bids: Any, asks: Any) -> Optional[Dict[str, float]]:
                if not isinstance(bids, list) or not isinstance(asks, list) or not bids or not asks:
                    return None
                try:
                    bid = float(bids[0].get("price"))  # type: ignore[union-attr]
                    ask = float(asks[0].get("price"))  # type: ignore[union-attr]
                except Exception:
                    return None

                # sanity
                if bid <= 0 or ask <= 0 or ask < bid:
                    return None

                mid = (bid + ask) / 2.0
                # If mid is absurdly tiny for a crypto USD pair, treat as invalid parse
                if mid < 1.0 and ("-USD" in product_id or "-USDC" in product_id):
                    return None

                return {"bid": bid, "ask": ask}

            # Shape A: {"pricebooks":[{"bids":[{"price":..}], "asks":[{"price":..}]}]}
            if isinstance(d.get("pricebooks"), list) and d["pricebooks"]:
                pb = d["pricebooks"][0]
                out = _extract_bid_ask(pb.get("bids"), pb.get("asks"))
                if out:
                    return out

            # Shape B: {"pricebook":{"bids":[...], "asks":[...]}}
            pb = d.get("pricebook")
            if isinstance(pb, dict):
                out = _extract_bid_ask(pb.get("bids"), pb.get("asks"))
                if out:
                    return out

            # Shape C: {"bids":[...], "asks":[...]}
            out = _extract_bid_ask(d.get("bids"), d.get("asks"))
            if out:
                return out

            # Shape D: {"best_bid":"..","best_ask":".."}
            if "best_bid" in d and "best_ask" in d:
                try:
                    bid = float(d["best_bid"])
                    ask = float(d["best_ask"])
                    if bid > 0 and ask > 0 and ask >= bid:
                        mid = (bid + ask) / 2.0
                        if not (mid < 1.0 and ("-USD" in product_id or "-USDC" in product_id)):
                            return {"bid": bid, "ask": ask}
                except Exception:
                    pass

            if _env("DEBUG_BBA", "0") == "1":
                print("DEBUG_BBA_RAW:", d)

            return None
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
        Coinbase candles often REQUIRE start/end. We auto-generate a valid window if missing.

        - end defaults to "now" UTC RFC3339
        - start defaults to end - lookback window (based on limit & granularity)
        """
        # If caller didn't provide start/end, generate them.
        if not end:
            end_dt = datetime.now(timezone.utc)
            end = _utc_rfc3339(end_dt)
        else:
            # try to keep; strategy may pass in already-correct ISO string
            end_dt = None

        if not start:
            # conservative lookback based on granularity
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
                # if end was provided as string, approximate now for lookback
                end_dt = datetime.now(timezone.utc)

            lookback_minutes = max(60, min(limit * minutes_per, 60 * 24 * 20))  # cap ~20 days
            start_dt = end_dt - timedelta(minutes=lookback_minutes)
            start = _utc_rfc3339(start_dt)

        # Call SDK with start/end (primary)
        try:
            resp = self._client.get_candles(
                product_id=product_id,
                start=start,
                end=end,
                granularity=granularity,
            )
            return _to_dict(resp)
        except TypeError:
            # Some SDK variants use positional order
            resp = self._client.get_candles(product_id, start, end, granularity)
            return _to_dict(resp)
        except Exception as e:
            # If Coinbase rejects timestamps, print them once for diagnosis
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
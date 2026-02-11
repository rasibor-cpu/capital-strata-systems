
"""
OANDA PRACTICE: one micro trade + immediate close
- Places a MARKET order for EUR_USD (1 unit)
- Attempts to detect fill + tradeID
- Immediately closes the trade if opened
- Prints clean, audit-friendly output (no secrets)
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
import urllib.error
from typing import Any, Dict, Optional

try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None


def _load_env() -> None:
    if load_dotenv is not None:
        load_dotenv()


def _get_env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _headers(api_key: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def _request_json(method: str, url: str, headers: Dict[str, str], payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return {"ok": True, "status": getattr(resp, "status", None), "json": json.loads(raw) if raw else {}, "raw": raw}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace") if hasattr(e, "read") else ""
        j = {}
        try:
            j = json.loads(body) if body else {}
        except Exception:
            j = {}
        return {"ok": False, "status": e.code, "json": j, "raw": body}
    except Exception as e:
        return {"ok": False, "status": None, "json": {}, "raw": str(e)}


def _pick_trade_id_from_order_response(j: Dict[str, Any]) -> Optional[str]:
    """
    OANDA order responses can include:
      - orderFillTransaction (filled immediately)
      - orderCreateTransaction (created, maybe pending)
    If filled, tradeOpened may exist with tradeID.
    """
    tx = j.get("orderFillTransaction") or j.get("orderFillTransaction", {})
    if isinstance(tx, dict):
        # tradeOpened: {"tradeID": "...", ...}
        to = tx.get("tradeOpened")
        if isinstance(to, dict) and to.get("tradeID"):
            return str(to["tradeID"])
        # Some responses have "tradesOpened": [ {"tradeID": "..."} ]
        tos = tx.get("tradesOpened")
        if isinstance(tos, list) and tos:
            for item in tos:
                if isinstance(item, dict) and item.get("tradeID"):
                    return str(item["tradeID"])
    return None


def main() -> int:
    _load_env()

    base = _get_env("OANDA_BASE_URL", "https://api-fxpractice.oanda.com")
    api_key = _get_env("OANDA_API_KEY", "")
    account_id = _get_env("OANDA_ACCOUNT_ID", "")

    print("=" * 78)
    print("OANDA PRACTICE — MICRO TRADE SMOKE TEST")
    print("=" * 78)
    print(f"Base URL      : {base}")
    print(f"Account ID set: {'YES' if bool(account_id) else 'NO'}")
    print(f"API key set   : {'YES' if bool(api_key) else 'NO'}")
    print("-" * 78)

    if not (base and api_key and account_id):
        print("ERROR: Missing OANDA_BASE_URL or OANDA_API_KEY or OANDA_ACCOUNT_ID in .env")
        return 2

    h = _headers(api_key)

    # 1) Quick auth sanity: GET /v3/accounts
    url_accounts = f"{base}/v3/accounts"
    r = _request_json("GET", url_accounts, h)
    print(f"Auth check GET /v3/accounts -> ok={r['ok']} status={r['status']}")
    if not r["ok"]:
        print("ERROR body (truncated):")
        print((r["raw"] or "")[:800])
        return 3

    # 2) Place MARKET order (1 unit) on EUR_USD
    url_order = f"{base}/v3/accounts/{account_id}/orders"
    payload = {
        "order": {
            "type": "MARKET",
            "instrument": "EUR_USD",
            "units": "1",              # micro test
            "timeInForce": "FOK",
            "positionFill": "DEFAULT",
        }
    }

    print("-" * 78)
    print("Placing MARKET order: EUR_USD units=1")
    r2 = _request_json("POST", url_order, h, payload)
    print(f"POST /orders -> ok={r2['ok']} status={r2['status']}")

    if not r2["ok"]:
        print("ORDER ERROR body (truncated):")
        print((r2["raw"] or "")[:1200])
        return 4

    j = r2["json"] if isinstance(r2["json"], dict) else {}
    # Pull useful IDs
    order_id = None
    if isinstance(j.get("orderCreateTransaction"), dict) and j["orderCreateTransaction"].get("id"):
        order_id = str(j["orderCreateTransaction"]["id"])
    if isinstance(j.get("orderFillTransaction"), dict) and j["orderFillTransaction"].get("orderID"):
        order_id = str(j["orderFillTransaction"]["orderID"])

    trade_id = _pick_trade_id_from_order_response(j)

    print("-" * 78)
    print("Order result summary")
    print(f"Order ID : {order_id}")
    print(f"Trade ID : {trade_id}")
    print("-" * 78)

    # 3) If trade opened, close it immediately
    if trade_id:
        url_close = f"{base}/v3/accounts/{account_id}/trades/{trade_id}/close"
        print(f"Closing tradeID={trade_id} ...")
        r3 = _request_json("PUT", url_close, h, payload={})
        print(f"PUT /trades/{trade_id}/close -> ok={r3['ok']} status={r3['status']}")
        if not r3["ok"]:
            print("CLOSE ERROR body (truncated):")
            print((r3["raw"] or "")[:1200])
            return 5
        print("CLOSE: OK")
        return 0

    # If not filled immediately, cancel the order (safe cleanup)
    if order_id:
        url_cancel = f"{base}/v3/accounts/{account_id}/orders/{order_id}/cancel"
        print(f"Order not filled immediately. Cancelling orderID={order_id} ...")
        r4 = _request_json("PUT", url_cancel, h, payload={})
        print(f"PUT /orders/{order_id}/cancel -> ok={r4['ok']} status={r4['status']}")
        if not r4["ok"]:
            print("CANCEL ERROR body (truncated):")
            print((r4["raw"] or "")[:1200])
            return 6
        print("CANCEL: OK")
        return 0

    print("NOTE: No tradeID and no orderID detected. Printing raw response (truncated):")
    print((r2["raw"] or "")[:1200])
    return 7


if __name__ == "__main__":
    raise SystemExit(main())

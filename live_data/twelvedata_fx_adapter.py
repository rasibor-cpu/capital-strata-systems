import os
import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import List, Dict, Any


BASE_URL = "https://api.twelvedata.com/time_series"


def _require_api_key() -> str:
    key = (os.getenv("TWELVEDATA_API_KEY") or "").strip()
    if not key:
        raise RuntimeError(
            "Missing TWELVEDATA_API_KEY in environment. "
            "Set it first, e.g.: set TWELVEDATA_API_KEY=YOUR_KEY"
        )
    return key


def _http_get_json(url: str, timeout: int = 20) -> Dict[str, Any]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "REA-Trading-Engine/1.0",
            "Accept": "application/json",
        },
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    try:
        return json.loads(raw)
    except Exception:
        return {"_parse_error": True, "_raw": raw[:2000]}


def _pair_to_symbol(pair: str) -> str:
    # Twelve Data expects EUR/USD form (usually OK). We normalize.
    p = (pair or "").strip().upper()
    if "/" not in p and len(p) == 6:
        p = p[:3] + "/" + p[3:]
    return p


def fetch_fx_1m(pair: str, limit: int = 300) -> List[Dict[str, Any]]:
    """
    Returns rows in REA CSV schema:
      {timestamp (iso8601Z), pair, bid, ask, mid}
    Twelve Data free tier commonly provides FX mid; bid/ask may not be present.
    We set bid=ask=mid when only mid is available (still fine for replay harness).
    """
    api_key = _require_api_key()
    symbol = _pair_to_symbol(pair)

    params = {
        "symbol": symbol,
        "interval": "1min",
        "outputsize": str(max(10, int(limit))),
        "apikey": api_key,
        "format": "JSON",
    }
    url = BASE_URL + "?" + urllib.parse.urlencode(params)

    data = _http_get_json(url)

    # Twelve Data error format
    if isinstance(data, dict) and data.get("status") == "error":
        msg = data.get("message") or "Unknown Twelve Data error"
        code = data.get("code")
        raise RuntimeError(f"TwelveData error for {symbol}: {msg} (code={code})")

    values = (data or {}).get("values") or []
    if not isinstance(values, list):
        values = []

    rows: List[Dict[str, Any]] = []

    # values often come newest-first; we convert to oldest-first
    for v in reversed(values):
        # Typical fields: datetime, open, high, low, close
        dt_str = (v.get("datetime") or "").strip()
        close_str = v.get("close")

        if not dt_str:
            continue

        # dt_str usually like: "2026-02-02 18:04:00"
        # Convert to ISO8601Z
        try:
            dt = datetime.fromisoformat(dt_str.replace(" ", "T"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            dt_iso = dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        except Exception:
            # If parsing fails, skip
            continue

        try:
            mid = float(str(close_str).replace(",", ""))
        except Exception:
            continue

        rows.append(
            {
                "timestamp": dt_iso,
                "pair": symbol,
                "bid": mid,
                "ask": mid,
                "mid": mid,
            }
        )

    return rows

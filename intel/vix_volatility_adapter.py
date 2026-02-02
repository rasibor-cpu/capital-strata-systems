"""
VIX / Volatility Adapter (Hardened, Free)
----------------------------------------
Purpose:
- Fetch a volatility proxy (VIX) and normalize into IntelEnvelope-ready dict.
- Free sources only, with fallback.
- Deterministic, fail-safe.

Sources:
1) Yahoo quote endpoint (best-effort)
2) Stooq CSV (reliable fallback)

Output:
- dict (IntelEnvelope-ready) or None
"""

from __future__ import annotations

import datetime as dt
import json
import urllib.request
import urllib.error
from typing import Optional, Tuple


# -----------------------------
# CONFIG
# -----------------------------
DEFAULT_TIMEOUT = 10

YAHOO_VIX_URL = "https://query1.finance.yahoo.com/v7/finance/quote?symbols=%5EVIX"
# Stooq uses different symbols; VIX index often available as ^VIX via Yahoo but on Stooq:
# Common Stooq VIX symbol is "vix" or "^vix" isn't used; stooq uses "vix" for CBOE VIX.
STOOQ_VIX_CSV = "https://stooq.com/q/l/?s=vix&i=d"  # CSV: Date,Open,High,Low,Close,Volume


VIX_LOW = 15.0
VIX_HIGH = 25.0


# -----------------------------
# HTTP helpers
# -----------------------------
def _http_get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "REA-Intel/1.0"})
    with urllib.request.urlopen(req, timeout=DEFAULT_TIMEOUT) as resp:
        return resp.read()


def _try_yahoo() -> Tuple[Optional[float], str]:
    try:
        raw = _http_get(YAHOO_VIX_URL)
        payload = json.loads(raw)
        res = payload.get("quoteResponse", {}).get("result", [])
        if not res:
            return None, "yahoo_no_result"
        price = res[0].get("regularMarketPrice")
        if price is None:
            return None, "yahoo_no_price"
        return float(price), "yahoo_ok"
    except Exception as e:
        return None, f"yahoo_fail:{type(e).__name__}"


def _try_stooq() -> Tuple[Optional[float], str]:
    try:
        raw = _http_get(STOOQ_VIX_CSV).decode("utf-8", errors="replace").strip()
        lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
        if len(lines) < 2:
            return None, "stooq_no_data"
        # header: Date,Open,High,Low,Close,Volume
        last = lines[-1].split(",")
        if len(last) < 5:
            return None, "stooq_bad_row"
        close = last[4]
        if close in ("", "N/A", "-"):
            return None, "stooq_no_close"
        return float(close), "stooq_ok"
    except Exception as e:
        return None, f"stooq_fail:{type(e).__name__}"


# -----------------------------
# Interpretation
# -----------------------------
def _clamp01(x: float) -> float:
    if x < 0.0:
        return 0.0
    if x > 1.0:
        return 1.0
    return round(x, 3)


def _interpret_vix(vix: float) -> Tuple[str, float]:
    # returns (direction, pressure)
    if vix >= VIX_HIGH:
        # Scale above high threshold
        p = 0.65 + (vix - VIX_HIGH) / 30.0
        return "risk_off", _clamp01(p)
    if vix <= VIX_LOW:
        # Low vol: modest risk-on
        p = 0.20 - (VIX_LOW - vix) / 40.0
        return "risk_on", _clamp01(max(p, 0.05))
    return "neutral", 0.35


# -----------------------------
# Public API
# -----------------------------
def fetch_vix_volatility() -> Tuple[Optional[dict], str]:
    """
    Returns (envelope_dict_or_None, status_string)
    """
    vix, status = _try_yahoo()
    source = "yahoo"

    if vix is None:
        vix, status2 = _try_stooq()
        if vix is not None:
            status = f"{status}|{status2}"
            source = "stooq"
        else:
            return None, f"{status}|{status2}"

    direction, pressure = _interpret_vix(vix)

    env = {
        "ts_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "source": source,
        "signal_class": "volatility",
        "regime_dimension": "risk",
        "pressure": pressure,
        "confidence": 0.85,
        "direction": direction,
        "raw_ref": "VIX",
        "meta": {
            "vix_level": vix,
            "fetch_status": status,
            "source_quality": "free",
        },
    }
    return env, status


# -----------------------------
# CLI test
# -----------------------------
if __name__ == "__main__":
    env, status = fetch_vix_volatility()
    if env:
        print("VIX_VOLATILITY_OK")
        print(env)
        print("STATUS:", status)
    else:
        print("VIX_VOLATILITY_FAILED")
        print("STATUS:", status)

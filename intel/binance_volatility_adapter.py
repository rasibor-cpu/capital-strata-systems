"""
Crypto Volatility Adapter (Binance/Binance.US/Coinbase fallback)
---------------------------------------------------------------
Purpose:
- Compute realized crypto volatility (1m closes) and emit IntelEnvelope
- Handle region blocks (Binance 451) gracefully
- No keys required

Run (module mode):
  python -m intel.binance_volatility_adapter
"""

from __future__ import annotations

import json
import math
import urllib.request
import urllib.error
from datetime import datetime, timezone
from typing import List, Tuple, Optional

from intel.intel_envelope import IntelEnvelope


# -----------------------------
# Venues (free, public)
# -----------------------------
BINANCE_GLOBAL = "https://api.binance.com/api/v3/klines?symbol={symbol}&interval=1m&limit={limit}"
BINANCE_US     = "https://api.binance.us/api/v3/klines?symbol={symbol}&interval=1m&limit={limit}"

# Coinbase Exchange candles: granularity=60 (1m). Latest first.
COINBASE = "https://api.exchange.coinbase.com/products/{product}/candles?granularity=60&limit={limit}"


DEFAULT_TIMEOUT = 10


def _http_get_json(url: str, headers: Optional[dict] = None) -> object:
    req = urllib.request.Request(
        url,
        headers=headers or {"User-Agent": "REA-Intel/1.0"},
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=DEFAULT_TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def _realized_vol(prices: List[float]) -> float:
    # sqrt(mean(r^2)) of log returns (simple, stable)
    rets = []
    for i in range(1, len(prices)):
        p0, p1 = prices[i - 1], prices[i]
        if p0 > 0 and p1 > 0:
            rets.append(math.log(p1 / p0))
    if not rets:
        return 0.0
    msq = sum(r * r for r in rets) / len(rets)
    return math.sqrt(msq)


def _normalize_pressure(vol: float, scale: float = 40.0) -> float:
    # Crypto realized vol tends to be small per-minute; scale to [0..1]
    p = vol * scale
    if p < 0:
        p = 0.0
    if p > 1:
        p = 1.0
    return round(p, 3)


def _fetch_klines_binance(url_tmpl: str, symbol: str, limit: int) -> List[float]:
    url = url_tmpl.format(symbol=symbol, limit=limit)
    data = _http_get_json(url)
    # Binance kline row: [open_time, open, high, low, close, volume, ...]
    closes = [float(k[4]) for k in data]
    return closes


def _fetch_candles_coinbase(product: str, limit: int) -> List[float]:
    url = COINBASE.format(product=product, limit=limit)
    # Coinbase returns: [time, low, high, open, close, volume] newest-first
    data = _http_get_json(url, headers={"User-Agent": "REA-Intel/1.0", "Accept": "application/json"})
    closes = [float(c[4]) for c in reversed(data)]  # oldest->newest
    return closes


def compute_crypto_volatility(symbol: str = "BTCUSDT", limit: int = 120) -> Tuple[Optional[IntelEnvelope], str]:
    """
    Returns (IntelEnvelope or None, status)
    """
    # 1) Try Binance.US (often works in US)
    try:
        closes = _fetch_klines_binance(BINANCE_US, symbol, limit)
        vol = _realized_vol(closes)
        pressure = _normalize_pressure(vol)

        env = IntelEnvelope.create(
            provider="binance_us",
            intel_type="market",
            signal_class="volatility",
            instrument_scope="CRYPTO",
            raw={"venue": "binance_us", "symbol": symbol, "bars": len(closes), "realized_vol": vol},
            confidence=0.90,
            severity=pressure,
        )
        return env, "binance_us_ok"
    except Exception as e:
        status1 = f"binance_us_fail:{type(e).__name__}"

    # 2) Try Binance Global (may 451)
    try:
        closes = _fetch_klines_binance(BINANCE_GLOBAL, symbol, limit)
        vol = _realized_vol(closes)
        pressure = _normalize_pressure(vol)

        env = IntelEnvelope.create(
            provider="binance",
            intel_type="market",
            signal_class="volatility",
            instrument_scope="CRYPTO",
            raw={"venue": "binance", "symbol": symbol, "bars": len(closes), "realized_vol": vol},
            confidence=0.90,
            severity=pressure,
        )
        return env, f"{status1}|binance_ok"
    except Exception as e:
        status2 = f"binance_fail:{type(e).__name__}"

    # 3) Fallback: Coinbase Exchange (BTC-USD)
    try:
        # Map symbol to product
        product = "BTC-USD" if symbol.upper().startswith("BTC") else "ETH-USD"
        closes = _fetch_candles_coinbase(product, limit)
        vol = _realized_vol(closes)
        pressure = _normalize_pressure(vol)

        env = IntelEnvelope.create(
            provider="coinbase",
            intel_type="market",
            signal_class="volatility",
            instrument_scope="CRYPTO",
            raw={"venue": "coinbase", "product": product, "bars": len(closes), "realized_vol": vol},
            confidence=0.88,
            severity=pressure,
        )
        return env, f"{status1}|{status2}|coinbase_ok"
    except Exception as e:
        status3 = f"coinbase_fail:{type(e).__name__}"
        return None, f"{status1}|{status2}|{status3}"


# -----------------------------
# CLI test
# -----------------------------
if __name__ == "__main__":
    env, status = compute_crypto_volatility("BTCUSDT", 120)
    print("CRYPTO_VOL_STATUS:", status)
    if env:
        print("CRYPTO_VOL_OK")
        print(env)
    else:
        print("CRYPTO_VOL_FAILED")

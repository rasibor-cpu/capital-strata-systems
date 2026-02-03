"""
Crypto Volatility Adapter (Binance.US / Binance / Coinbase fallback)
--------------------------------------------------------------------
Exports:
- compute_crypto_volatility(...) -> (IntelEnvelope|None, status)
- fetch_crypto_volatility_safe() -> List[IntelEnvelope]  (collector contract)

Run:
  python -m intel.binance_volatility_adapter
"""

from __future__ import annotations

import json
import math
import urllib.request
from datetime import datetime, timezone
from typing import List, Tuple, Optional

from intel.intel_envelope import IntelEnvelope

BINANCE_GLOBAL = "https://api.binance.com/api/v3/klines?symbol={symbol}&interval=1m&limit={limit}"
BINANCE_US     = "https://api.binance.us/api/v3/klines?symbol={symbol}&interval=1m&limit={limit}"
COINBASE       = "https://api.exchange.coinbase.com/products/{product}/candles?granularity=60&limit={limit}"

DEFAULT_TIMEOUT = 10


def _http_get_json(url: str, headers: Optional[dict] = None):
    req = urllib.request.Request(
        url,
        headers=headers or {"User-Agent": "REA-Intel/1.0", "Accept": "application/json"},
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=DEFAULT_TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def _realized_vol(prices: List[float]) -> float:
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
    p = vol * scale
    if p < 0.0:
        p = 0.0
    if p > 1.0:
        p = 1.0
    return round(p, 3)


def _fetch_klines_binance(url_tmpl: str, symbol: str, limit: int) -> List[float]:
    data = _http_get_json(url_tmpl.format(symbol=symbol, limit=limit))
    return [float(k[4]) for k in data]  # close


def _fetch_candles_coinbase(product: str, limit: int) -> List[float]:
    data = _http_get_json(
        COINBASE.format(product=product, limit=limit),
        headers={"User-Agent": "REA-Intel/1.0", "Accept": "application/json"},
    )
    # Coinbase candles newest-first: [time, low, high, open, close, volume]
    closes = [float(c[4]) for c in reversed(data)]
    return closes


def compute_crypto_volatility(symbol: str = "BTCUSDT", limit: int = 120) -> Tuple[Optional[IntelEnvelope], str]:
    # 1) Binance.US
    try:
        closes = _fetch_klines_binance(BINANCE_US, symbol, limit)
        vol = _realized_vol(closes)
        env = IntelEnvelope.create(
            provider="binance_us",
            intel_type="market",
            signal_class="volatility",
            instrument_scope="CRYPTO",
            raw={"venue": "binance_us", "symbol": symbol, "bars": len(closes), "realized_vol": vol},
            confidence=0.90,
            severity=_normalize_pressure(vol),
            rea_instrument=None,
        )
        return env, "binance_us_ok"
    except Exception as e:
        status1 = f"binance_us_fail:{type(e).__name__}"

    # 2) Binance global
    try:
        closes = _fetch_klines_binance(BINANCE_GLOBAL, symbol, limit)
        vol = _realized_vol(closes)
        env = IntelEnvelope.create(
            provider="binance",
            intel_type="market",
            signal_class="volatility",
            instrument_scope="CRYPTO",
            raw={"venue": "binance", "symbol": symbol, "bars": len(closes), "realized_vol": vol},
            confidence=0.90,
            severity=_normalize_pressure(vol),
            rea_instrument=None,
        )
        return env, f"{status1}|binance_ok"
    except Exception as e:
        status2 = f"binance_fail:{type(e).__name__}"

    # 3) Coinbase fallback
    try:
        product = "BTC-USD" if symbol.upper().startswith("BTC") else "ETH-USD"
        closes = _fetch_candles_coinbase(product, limit)
        vol = _realized_vol(closes)
        env = IntelEnvelope.create(
            provider="coinbase",
            intel_type="market",
            signal_class="volatility",
            instrument_scope="CRYPTO",
            raw={"venue": "coinbase", "product": product, "bars": len(closes), "realized_vol": vol},
            confidence=0.88,
            severity=_normalize_pressure(vol),
            rea_instrument=None,
        )
        return env, f"{status1}|{status2}|coinbase_ok"
    except Exception as e:
        status3 = f"coinbase_fail:{type(e).__name__}"
        return None, f"{status1}|{status2}|{status3}"


def fetch_crypto_volatility_safe() -> List[IntelEnvelope]:
    """
    Collector contract: returns [] on failure, never raises.
    """
    try:
        env, status = compute_crypto_volatility("BTCUSDT", 120)
        if env is None:
            return []
        # annotate status inside raw
        env_raw = dict(env.raw)
        env_raw["fetch_status"] = status
        return [
            IntelEnvelope.create(
                provider=env.provider,
                intel_type=env.intel_type,
                signal_class=env.signal_class,
                instrument_scope=env.instrument_scope,
                raw=env_raw,
                confidence=env.confidence,
                severity=env.severity,
                rea_instrument=None,
            )
        ]
    except Exception:
        return []


if __name__ == "__main__":
    envs = fetch_crypto_volatility_safe()
    print(f"CRYPTO_VOL_SAFE_OK: {len(envs)}")
    for e in envs:
        print(e)

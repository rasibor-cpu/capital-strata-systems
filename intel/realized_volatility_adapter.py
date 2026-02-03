"""
Realized Volatility Adapter (FREE, ALWAYS-ON)
--------------------------------------------
Exports:
- compute_vol_signal(...)                 (utility)
- fetch_realized_volatility_safe()        (collector contract)

This adapter computes realized volatility from a provided close series.
In collector-safe mode, it runs a DEMO placeholder unless you wire real closes.
"""

from __future__ import annotations

from datetime import datetime, timezone
import math
from typing import List, Dict

from intel.intel_envelope import IntelEnvelope


def _log_returns(prices: List[float]) -> List[float]:
    rets = []
    for i in range(1, len(prices)):
        p0, p1 = prices[i - 1], prices[i]
        if p0 > 0 and p1 > 0:
            rets.append(math.log(p1 / p0))
    return rets


def _stddev(values: List[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    var = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
    return math.sqrt(var)


def realized_volatility(closes: List[float], periods_per_year: int = 252) -> float:
    rets = _log_returns(closes)
    if not rets:
        return 0.0
    daily_std = _stddev(rets)
    return daily_std * math.sqrt(periods_per_year)


def compute_vol_signal(
    symbol: str,
    closes: List[float],
    window: int = 20,
    periods_per_year: int = 252,
    source: str = "internal_prices",
) -> Dict:
    if len(closes) < window + 1:
        return {
            "status": "insufficient_data",
            "symbol": symbol,
            "window": window,
        }

    window_closes = closes[-(window + 1):]
    vol = realized_volatility(window_closes, periods_per_year)

    # Deterministic pressure bands
    if vol < 0.10:
        pressure = 0.20
        direction = "risk_on"
    elif vol < 0.20:
        pressure = 0.40
        direction = "neutral"
    elif vol < 0.35:
        pressure = 0.65
        direction = "risk_rising"
    else:
        pressure = 0.85
        direction = "risk_off"

    return {
        "ts_utc": datetime.now(timezone.utc).isoformat(),
        "provider": source,
        "symbol": symbol,
        "window": window,
        "realized_vol": round(vol, 6),
        "pressure": round(pressure, 3),
        "confidence": 0.90,
        "direction": direction,
    }


def fetch_realized_volatility_safe() -> List[IntelEnvelope]:
    """
    Collector-safe wrapper.
    For now: DEMO mode using a tiny synthetic series (always works).
    Later: wire real closes from your data pipeline and replace the demo.
    """
    try:
        demo_prices = [
            100, 101, 102, 101.5, 100.8, 99.9, 100.3, 101.2, 102.8,
            103.1, 102.4, 101.9, 101.7, 102.5, 103.4, 104.2, 103.9,
            104.6, 105.1, 104.7, 104.9, 105.4, 105.2
        ]

        sig = compute_vol_signal("DEMO", demo_prices, window=20, periods_per_year=252)

        if sig.get("status") == "insufficient_data":
            return []

        env = IntelEnvelope.create(
            provider=sig.get("provider", "internal_prices"),
            intel_type="market",
            signal_class="volatility",
            instrument_scope="GLOBAL",
            raw={
                "symbol": sig["symbol"],
                "window": sig["window"],
                "realized_vol": sig["realized_vol"],
                "direction": sig["direction"],
            },
            confidence=float(sig.get("confidence", 0.9)),
            severity=float(sig.get("pressure", 0.0)),
            rea_instrument=None,
        )
        return [env]
    except Exception:
        return []


if __name__ == "__main__":
    envs = fetch_realized_volatility_safe()
    print(f"REALIZED_VOL_SAFE_OK: {len(envs)}")
    for e in envs:
        print(e)

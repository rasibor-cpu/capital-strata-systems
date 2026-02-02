"""
Realized Volatility Adapter (FREE, SOURCE-AGNOSTIC)

Computes historical / realized volatility from price series you already ingest.
Designed to be the PRIMARY volatility signal when VIX is unavailable.

Outputs IntelEnvelope-compatible dicts (later wrapped by IntelEnvelope.create).
"""

from __future__ import annotations
from datetime import datetime, timezone
import math
from typing import List, Dict, Optional


def _log_returns(prices: List[float]) -> List[float]:
    rets = []
    for i in range(1, len(prices)):
        if prices[i - 1] <= 0 or prices[i] <= 0:
            continue
        rets.append(math.log(prices[i] / prices[i - 1]))
    return rets


def _stddev(values: List[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    var = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
    return math.sqrt(var)


def realized_volatility(
    closes: List[float],
    periods_per_year: int = 252,
) -> float:
    """
    Annualized realized volatility using log returns.
    """
    rets = _log_returns(closes)
    if not rets:
        return 0.0
    daily_std = _stddev(rets)
    return daily_std * math.sqrt(periods_per_year)


def compute_vol_signal(
    symbol: str,
    closes: List[float],
    window: int,
    periods_per_year: int = 252,
    source: str = "internal_prices",
) -> Dict:
    """
    Returns a normalized volatility signal dict.
    """
    if len(closes) < window + 1:
        return {
            "ts_utc": datetime.now(timezone.utc).isoformat(),
            "source": source,
            "signal_class": "volatility",
            "regime_dimension": "risk",
            "pressure": 0.0,
            "confidence": 0.0,
            "direction": "neutral",
            "meta": {
                "symbol": symbol,
                "window": window,
                "status": "insufficient_data",
            },
        }

    window_closes = closes[-(window + 1):]
    vol = realized_volatility(window_closes, periods_per_year)

    # Normalize pressure (heuristic bands; conservative)
    if vol < 0.10:
        pressure = 0.2
        direction = "risk_on"
    elif vol < 0.20:
        pressure = 0.4
        direction = "neutral"
    elif vol < 0.35:
        pressure = 0.65
        direction = "risk_rising"
    else:
        pressure = 0.85
        direction = "risk_off"

    return {
        "ts_utc": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "signal_class": "volatility",
        "regime_dimension": "risk",
        "pressure": round(pressure, 3),
        "confidence": 0.9,
        "direction": direction,
        "meta": {
            "symbol": symbol,
            "window": window,
            "realized_vol": round(vol, 4),
            "method": "log_returns_annualized",
        },
    }


def demo():
    # Minimal sanity demo with synthetic prices
    prices = [
        100, 101, 102, 101.5, 100.8, 99.9, 100.3,
        101.2, 102.8, 103.1, 102.4, 101.9, 101.7,
        102.5, 103.4, 104.2, 103.9, 104.6, 105.1,
    ]
    sig20 = compute_vol_signal("DEMO", prices, window=20)
    sig60 = compute_vol_signal("DEMO", prices, window=60)
    print("VOL_20_OK", sig20)
    print("VOL_60_OK", sig60)


if __name__ == "__main__":
    demo()

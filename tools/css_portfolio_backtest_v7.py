"""
Capital Strata Systems (CSS)
Portfolio Backtest Engine v7 (FIXED)
- VWAP + Trend + RSI + Adaptive Trigger (all in BPS units)
- Market testing policy: crypto=180d, others=365d
- Adds diagnostics counters so we can see why entries are blocked

Run:
  python tools\\css_portfolio_backtest_v7.py
"""

from __future__ import annotations

import json
import statistics
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

import requests

COINBASE = "https://api.exchange.coinbase.com"

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUT = PROJECT_ROOT / "audit_logs" / "backtests"
OUT.mkdir(parents=True, exist_ok=True)

# -------- MARKET CONFIG --------
MARKET_CONFIG = {
    "crypto": {"rsi_period": 9, "rsi_entry": 45, "trigger_mult": 0.9, "test_days": 180},
    "fx": {"rsi_period": 14, "rsi_entry": 40, "trigger_mult": 1.0, "test_days": 365},
    "equities": {"rsi_period": 14, "rsi_entry": 40, "trigger_mult": 1.1, "test_days": 365},
    "futures": {"rsi_period": 12, "rsi_entry": 42, "trigger_mult": 1.0, "test_days": 365},
}

MARKET_TYPE = "crypto"  # later: fx/equities/futures


@dataclass
class Candle:
    ts: int
    close: float
    volume: float


def iso(t: datetime) -> str:
    return t.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def fetch(product: str, granularity: int, start: datetime, end: datetime) -> List[Candle]:
    url = f"{COINBASE}/products/{product}/candles"

    candles: List[Candle] = []
    step = granularity * 200
    cursor = start

    session = requests.Session()
    session.headers.update({"User-Agent": "CSS-Backtest/1.0"})

    while cursor < end:
        chunk = min(cursor + timedelta(seconds=step), end)
        params = {"start": iso(cursor), "end": iso(chunk), "granularity": str(granularity)}
        r = session.get(url, params=params, timeout=30)
        if r.status_code != 200:
            raise RuntimeError(f"{product} candles failed {r.status_code}: {(r.text or '')[:300]}")

        for row in r.json():
            ts, low, high, open_, close, vol = row
            candles.append(Candle(int(ts), float(close), float(vol)))

        cursor = chunk
        time.sleep(0.12)

    uniq = {c.ts: c for c in candles}
    return sorted(uniq.values(), key=lambda x: x.ts)


def vwap(window: List[Candle]) -> Optional[float]:
    pv = 0.0
    vol = 0.0
    for c in window:
        pv += c.close * c.volume
        vol += c.volume
    return (pv / vol) if vol > 0 else None


def ma(values: List[float], n: int) -> Optional[float]:
    if len(values) < n:
        return None
    return sum(values[-n:]) / n


def slope(values: List[float], n: int) -> float:
    if len(values) < n:
        return 0.0
    return values[-1] - values[-n]


def rsi(values: List[float], period: int) -> Optional[float]:
    if len(values) < period + 1:
        return None

    gains = 0.0
    losses = 0.0

    for i in range(-period, 0):
        change = values[i] - values[i - 1]
        if change > 0:
            gains += change
        else:
            losses += abs(change)

    avg_gain = gains / period
    avg_loss = losses / period

    if avg_loss == 0:
        return 100.0

    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def stdev_price(values: List[float], period: int = 20) -> Optional[float]:
    if len(values) < period:
        return None
    return statistics.stdev(values[-period:])


def volatility_bps(values: List[float], price: float, period: int = 20) -> Optional[float]:
    """
    Convert rolling stdev in price-units into bps units:
      vol_bps = (stdev_price / price) * 10000
    """
    sd = stdev_price(values, period)
    if sd is None or price <= 0:
        return None
    return (sd / price) * 10000.0


def backtest_asset(product: str, capital: float, granularity: int) -> Dict:
    cfg = MARKET_CONFIG[MARKET_TYPE]
    days = int(cfg["test_days"])

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)

    candles = fetch(product, granularity, start, end)
    closes: List[float] = []

    lookback = 20
    ma_len = 50

    # bps rules
    stop_bps = 70.0
    take_bps = 80.0

    cash = float(capital)
    position = None  # dict(entry, size, i)
    trades: List[float] = []

    # diagnostics counters
    diag = {
        "bars": 0,
        "eligible_bars": 0,
        "blocked_trend": 0,
        "blocked_slope": 0,
        "blocked_rsi": 0,
        "blocked_trigger": 0,
        "entries": 0,
        "exits": 0,
    }

    rsi_period = int(cfg["rsi_period"])
    rsi_entry = float(cfg["rsi_entry"])
    trigger_mult = float(cfg["trigger_mult"])

    for i, c in enumerate(candles):
        diag["bars"] += 1
        price = c.close
        closes.append(price)

        if i < ma_len or i < lookback:
            continue

        trend = ma(closes, ma_len)
        if trend is None:
            continue
        trend_strength = slope(closes, 10)

        vw = vwap(candles[i - lookback : i])
        if vw is None or vw <= 0:
            continue

        spread_bps = ((price - vw) / vw) * 10000.0

        vbps = volatility_bps(closes, price, 20)
        if vbps is None:
            continue

        trigger_bps = vbps * trigger_mult
        r = rsi(closes, rsi_period)

        diag["eligible_bars"] += 1

        # ----- ENTRY
        if position is None:
            if price <= trend:
                diag["blocked_trend"] += 1
                continue
            if trend_strength <= 0:
                diag["blocked_slope"] += 1
                continue
            if r is None or r >= rsi_entry:
                diag["blocked_rsi"] += 1
                continue
            if spread_bps >= -trigger_bps:
                diag["blocked_trigger"] += 1
                continue

            # Enter: allocate 10% of this sub-capital per trade
            size_usd = min(cash, capital * 0.10)
            if size_usd < 10.0:
                continue

            size_asset = size_usd / price
            cash -= size_usd
            position = {"entry": price, "size": size_asset, "i": i}
            diag["entries"] += 1
            continue

        # ----- EXIT
        entry = float(position["entry"])
        move_bps = ((price - entry) / entry) * 10000.0

        if move_bps >= take_bps or move_bps <= -stop_bps or price >= vw:
            pnl = (price - entry) * float(position["size"])
            cash += float(position["size"]) * price
            trades.append(pnl)
            position = None
            diag["exits"] += 1

    equity = cash
    if position is not None:
        equity += float(position["size"]) * float(candles[-1].close)

    wins = sum(1 for t in trades if t > 0)
    losses = len(trades) - wins

    return {
        "product": product,
        "test_days": days,
        "granularity": granularity,
        "trades": len(trades),
        "wins": wins,
        "losses": losses,
        "win_rate": (wins / len(trades)) if trades else 0.0,
        "pnl": round(equity - capital, 2),
        "final_equity": round(equity, 2),
        "diagnostics": diag,
        "params": {
            "market_type": MARKET_TYPE,
            "rsi_period": rsi_period,
            "rsi_entry": rsi_entry,
            "trigger_mult": trigger_mult,
            "stop_bps": stop_bps,
            "take_bps": take_bps,
            "lookback": lookback,
            "ma_len": ma_len,
        },
    }


def run_portfolio() -> Dict:
    capital = 1000.0
    alloc = {"BTC-USD": 0.5, "ETH-USD": 0.3, "SOL-USD": 0.2}

    results = []
    for asset, w in alloc.items():
        results.append(backtest_asset(asset, capital * w, 3600))  # 1H candles

    portfolio_equity = sum(r["final_equity"] for r in results)
    return {
        "assets": results,
        "portfolio_equity": round(portfolio_equity, 2),
        "portfolio_pnl": round(portfolio_equity - capital, 2),
    }


def main() -> None:
    result = run_portfolio()

    print("\nCSS PORTFOLIO BACKTEST v7 (FIXED)\n")
    for a in result["assets"]:
        print(
            {
                "product": a["product"],
                "trades": a["trades"],
                "wins": a["wins"],
                "losses": a["losses"],
                "pnl": a["pnl"],
                "final_equity": a["final_equity"],
            }
        )
        print(" diagnostics:", a["diagnostics"])
        print(" params:", a["params"])
        print("")

    print("Portfolio Equity:", result["portfolio_equity"])
    print("Portfolio PnL:", result["portfolio_pnl"])

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    f = OUT / f"portfolio_backtest_v7_{stamp}.json"
    f.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print("\nSaved:", f)


if __name__ == "__main__":
    main()
"""
Capital Strata Systems (CSS)
Execution Realism Backtest v29b (FIXED)

Fixes from v29:
- Uses realistic fee defaults (bps, not 0.6% per side by default)
- Preserves v25 mechanics: TP1 partial + trailing stop + cooldown
- Applies spread/slippage on BOTH entry and exit
- Closes open position at end (mark-to-market with exit friction)
- Adds optional volatility widening (spread/slippage scale with ATR%)

Research/backtest only.
"""

from __future__ import annotations

import json
import random
import statistics
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests

COINBASE = "https://api.exchange.coinbase.com"

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUT = PROJECT_ROOT / "audit_logs" / "backtests"
OUT.mkdir(parents=True, exist_ok=True)

PRODUCTS = ["BTC-USD", "ETH-USD", "SOL-USD"]

CFG = {
    "test_days": 180,
    "granularity": 900,  # 15m

    # v25 logic
    "ema_fast": 20,
    "ema_slow": 50,
    "slope_lookback": 8,
    "min_slope_pct": 0.0013,

    "atr_window": 20,
    "atr_stop_mult": 2.0,
    "trail_atr_mult": 3.5,
    "min_atr_pct": 0.004,

    "cooldown": 10,
    "position_size": 0.05,

    # REALISTIC friction defaults (bps-ish)
    # NOTE: v29 used 0.006 (0.6%) which is usually too punitive.
    "fee_rate": 0.0006,      # 0.06% per side default
    "base_spread": 0.0002,   # 2 bps
    "base_slip": 0.0003,     # 3 bps

    # Optional volatility widening
    "use_vol_widening": True,
    "vol_widen_mult": 1.8,   # friction multiplier when ATR% high

    # Take profit partials
    "tp1_r": 2.0,
    "tp1_frac": 0.5,

    # deterministic runs
    "seed": 42,
}

START_EQUITY = 1000.0


@dataclass
class Candle:
    ts: int
    low: float
    high: float
    open: float
    close: float
    volume: float


def _iso(t: datetime) -> str:
    return t.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def fetch(product: str, start: datetime, end: datetime, gran: int) -> List[Candle]:
    url = f"{COINBASE}/products/{product}/candles"
    candles: List[Candle] = []

    step = gran * 200
    cursor = start

    while cursor < end:
        chunk = min(cursor + timedelta(seconds=step), end)
        params = {"start": _iso(cursor), "end": _iso(chunk), "granularity": gran}
        r = requests.get(url, params=params)

        if r.status_code != 200:
            raise RuntimeError(f"{product} request failed {r.status_code}: {r.text[:200]}")

        for row in r.json():
            ts, low, high, open_, close, vol = row
            candles.append(Candle(int(ts), float(low), float(high), float(open_), float(close), float(vol)))

        cursor = chunk
        time.sleep(0.12)

    uniq = {c.ts: c for c in candles}
    return sorted(uniq.values(), key=lambda x: x.ts)


def ema(values: List[float], period: int) -> Optional[float]:
    if len(values) < period:
        return None
    k = 2 / (period + 1)
    e = values[0]
    for v in values:
        e = v * k + e * (1 - k)
    return e


def atr(candles: List[Candle]) -> Optional[float]:
    if len(candles) < 2:
        return None
    trs = []
    prev = candles[0].close
    for c in candles[1:]:
        tr = max(c.high - c.low, abs(c.high - prev), abs(c.low - prev))
        trs.append(tr)
        prev = c.close
    return statistics.mean(trs) if trs else None


def friction_mult(atr_pct: float) -> float:
    """
    Optional widening: when ATR% is high, widen spread/slippage.
    Simple rule: if atr_pct >= 1.0%, multiply friction.
    """
    if not CFG["use_vol_widening"]:
        return 1.0
    return CFG["vol_widen_mult"] if atr_pct >= 0.010 else 1.0


def exec_price(mid: float, is_buy: bool, atr_pct: float) -> float:
    """
    Apply spread + random slippage around mid.
    Buy pays above mid; sell receives below mid.
    """
    m = friction_mult(atr_pct)
    spread = CFG["base_spread"] * m
    slip = (CFG["base_slip"] * m) * random.random()

    if is_buy:
        return mid * (1.0 + spread + slip)
    return mid * (1.0 - spread - slip)


def run(product: str) -> Dict[str, float]:
    random.seed(CFG["seed"])

    capital = float(START_EQUITY)
    cash = capital

    position = None
    cooldown = 0
    in_pullback = False

    realized_pnls: List[float] = []

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=CFG["test_days"])
    candles = fetch(product, start, end, CFG["granularity"])

    closes: List[float] = []
    warm = max(CFG["ema_slow"], CFG["atr_window"]) + CFG["slope_lookback"] + 5

    for i, c in enumerate(candles):
        closes.append(c.close)
        mid = c.close

        if i < warm:
            continue

        if cooldown > 0:
            cooldown -= 1

        ema20 = ema(closes[-CFG["ema_fast"] :], CFG["ema_fast"])
        ema50 = ema(closes[-CFG["ema_slow"] :], CFG["ema_slow"])
        ema50_prev = ema(
            closes[-CFG["ema_slow"] - CFG["slope_lookback"] : -CFG["slope_lookback"]],
            CFG["ema_slow"],
        )
        if ema20 is None or ema50 is None or ema50_prev is None:
            continue

        slope = (ema50 - ema50_prev) / mid
        if slope < CFG["min_slope_pct"]:
            continue

        atr_val = atr(candles[i - CFG["atr_window"] : i + 1])
        if atr_val is None:
            continue

        atr_pct = atr_val / mid
        if atr_pct < CFG["min_atr_pct"]:
            continue

        uptrend = mid > ema50

        # pullback detection
        if uptrend and mid <= ema20:
            in_pullback = True

        # ENTRY (use exec_price)
        if position is None and cooldown == 0 and in_pullback and mid > ema20:
            entry = exec_price(mid, is_buy=True, atr_pct=atr_pct)
            size_usd = cash * CFG["position_size"]
            if size_usd <= 0:
                in_pullback = False
                continue

            size = size_usd / entry
            fee_in = size_usd * CFG["fee_rate"]
            cash -= (size_usd + fee_in)

            stop = entry - (CFG["atr_stop_mult"] * atr_val)
            r = entry - stop

            position = {
                "entry": entry,
                "size": size,
                "stop": stop,
                "peak": entry,
                "r": r,
                "tp1_done": False,
            }
            in_pullback = False

        # MANAGE
        if position is not None:
            # peak tracking on mid
            if mid > position["peak"]:
                position["peak"] = mid

            # trailing stop anchored on peak mid
            trail = position["peak"] - (CFG["trail_atr_mult"] * atr_val)
            if trail > position["stop"]:
                position["stop"] = trail

            # TP1 target (price level). Use candle HIGH for trigger, but execute with friction.
            tp1_level = position["entry"] + (CFG["tp1_r"] * position["r"])

            if (not position["tp1_done"]) and c.high >= tp1_level:
                sell = position["size"] * CFG["tp1_frac"]
                if sell > 0:
                    exit_px = exec_price(tp1_level, is_buy=False, atr_pct=atr_pct)
                    gross = sell * exit_px
                    fee_out = gross * CFG["fee_rate"]
                    pnl = (exit_px - position["entry"]) * sell - fee_out
                    realized_pnls.append(float(pnl))
                    cash += gross - fee_out
                    position["size"] -= sell
                    position["tp1_done"] = True

            # STOP trigger: use candle LOW, execute at stop level with friction.
            if c.low <= position["stop"]:
                exit_px = exec_price(position["stop"], is_buy=False, atr_pct=atr_pct)
                sell = position["size"]
                gross = sell * exit_px
                fee_out = gross * CFG["fee_rate"]
                pnl = (exit_px - position["entry"]) * sell - fee_out
                realized_pnls.append(float(pnl))
                cash += gross - fee_out
                position = None
                cooldown = CFG["cooldown"]

    # Mark-to-market (close last position with friction at final mid)
    if position is not None:
        mid = candles[-1].close
        atr_val = atr(candles[-CFG["atr_window"] :])
        atr_pct = (atr_val / mid) if atr_val else 0.0
        exit_px = exec_price(mid, is_buy=False, atr_pct=atr_pct)
        sell = position["size"]
        gross = sell * exit_px
        fee_out = gross * CFG["fee_rate"]
        pnl = (exit_px - position["entry"]) * sell - fee_out
        realized_pnls.append(float(pnl))
        cash += gross - fee_out
        position = None

    equity = cash
    wins = sum(1 for x in realized_pnls if x > 0)
    losses = sum(1 for x in realized_pnls if x <= 0)

    return {
        "product": product,
        "realizations": int(len(realized_pnls)),
        "wins": int(wins),
        "losses": int(losses),
        "win_rate": round((wins / len(realized_pnls)) * 100, 2) if realized_pnls else 0.0,
        "final_equity": round(equity, 2),
        "pnl": round(equity - capital, 2),
    }


def main() -> None:
    print("\nCSS EXECUTION REALISM TEST v29b (FIXED)\n")
    results = []
    portfolio = 0.0

    for p in PRODUCTS:
        r = run(p)
        results.append(r)
        portfolio += float(r["pnl"])
        print(r)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = OUT / f"execution_realism_v29b_{stamp}.json"
    out.write_text(json.dumps({"cfg": CFG, "results": results, "portfolio_pnl": round(portfolio, 2)}, indent=2))
    print("\nPortfolio PnL:", round(portfolio, 2))
    print("Saved:", out)


if __name__ == "__main__":
    main()
"""
Capital Strata Systems (CSS)
Monte Carlo Stress Test v28 — Trend Pullback (Multi-Asset)

What it does:
1) Re-runs the v25 Trend Pullback engine for BTC/ETH/SOL (last 180 days, 15m)
2) Records EACH realized trade PnL (partials + final exits)
3) Runs Monte Carlo resampling (default 10,000 simulations) of trade order
4) Reports:
   - PnL percentiles (P5/P50/P95)
   - Max Drawdown percentiles
   - Risk-of-ruin proxy: % sims with equity < (start * ruin_threshold)

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
    "fee_rate": 0.0006,
    "tp1_r": 2.0,
    "tp1_frac": 0.5,
}

MC = {
    "sims": 10_000,
    "seed": 42,
    "start_equity": 1000.0,
    "ruin_threshold": 0.80,  # ruin if equity drops below 80% of start
}


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


def run_v25_collect_trades(product: str) -> Tuple[Dict[str, float], List[float]]:
    """
    Runs the v25 trend pullback logic and returns:
      summary metrics + list of realized trade pnls (each partial and final exit is one realization)
    """
    capital = float(MC["start_equity"])
    cash = capital

    position = None
    cooldown = 0
    in_pullback = False

    trade_pnls: List[float] = []

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=CFG["test_days"])
    candles = fetch(product, start, end, CFG["granularity"])

    closes: List[float] = []
    warm = max(CFG["ema_slow"], CFG["atr_window"]) + CFG["slope_lookback"] + 5

    for i, c in enumerate(candles):
        closes.append(c.close)
        price = c.close

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

        slope = (ema50 - ema50_prev) / price
        if slope < CFG["min_slope_pct"]:
            continue

        atr_val = atr(candles[i - CFG["atr_window"] : i + 1])
        if atr_val is None:
            continue
        if (atr_val / price) < CFG["min_atr_pct"]:
            continue

        uptrend = price > ema50

        # pullback detection (state)
        if uptrend and price <= ema20:
            in_pullback = True

        # entry
        if position is None and cooldown == 0 and in_pullback and price > ema20:
            size_usd = cash * CFG["position_size"]
            if size_usd <= 0:
                in_pullback = False
                continue

            fee_in = size_usd * CFG["fee_rate"]
            cash -= (size_usd + fee_in)

            size = size_usd / price
            stop = price - (CFG["atr_stop_mult"] * atr_val)
            r = price - stop

            position = {"entry": price, "size": size, "stop": stop, "peak": price, "r": r, "tp1_done": False}
            in_pullback = False

        # manage
        if position is not None:
            if price > position["peak"]:
                position["peak"] = price

            trail = position["peak"] - (CFG["trail_atr_mult"] * atr_val)
            if trail > position["stop"]:
                position["stop"] = trail

            tp1 = position["entry"] + (CFG["tp1_r"] * position["r"])

            # TP1 uses intrabar high
            if (not position["tp1_done"]) and c.high >= tp1:
                sell = position["size"] * CFG["tp1_frac"]
                if sell > 0:
                    val = sell * tp1
                    fee_out = val * CFG["fee_rate"]
                    pnl = (tp1 - position["entry"]) * sell - fee_out
                    trade_pnls.append(float(pnl))
                    cash += val - fee_out
                    position["size"] -= sell
                    position["tp1_done"] = True

            # stop uses intrabar low
            if c.low <= position["stop"]:
                exitp = position["stop"]
                sell = position["size"]
                val = sell * exitp
                fee_out = val * CFG["fee_rate"]
                pnl = (exitp - position["entry"]) * sell - fee_out
                trade_pnls.append(float(pnl))
                cash += val - fee_out
                position = None
                cooldown = CFG["cooldown"]

    equity = cash
    if position is not None:
        equity += position["size"] * candles[-1].close

    wins = sum(1 for t in trade_pnls if t > 0)
    losses = sum(1 for t in trade_pnls if t <= 0)

    summary = {
        "product": product,
        "realizations": int(len(trade_pnls)),
        "wins": int(wins),
        "losses": int(losses),
        "win_rate": round((wins / len(trade_pnls)) * 100, 2) if trade_pnls else 0.0,
        "final_equity": round(equity, 2),
        "pnl": round(equity - capital, 2),
    }
    return summary, trade_pnls


def max_drawdown(equity_curve: List[float]) -> float:
    peak = equity_curve[0]
    max_dd = 0.0
    for x in equity_curve[1:]:
        if x > peak:
            peak = x
        dd = (peak - x)
        if dd > max_dd:
            max_dd = dd
    return max_dd


def percentile(xs: List[float], p: float) -> float:
    if not xs:
        return 0.0
    ys = sorted(xs)
    k = (len(ys) - 1) * p
    f = int(k)
    c = min(f + 1, len(ys) - 1)
    if f == c:
        return float(ys[f])
    return float(ys[f] + (ys[c] - ys[f]) * (k - f))


def run_monte_carlo(trade_pnls: List[float]) -> Dict[str, float]:
    sims = int(MC["sims"])
    start_eq = float(MC["start_equity"])
    ruin_level = start_eq * float(MC["ruin_threshold"])

    pnls = []
    dds = []
    ruin_hits = 0

    n = len(trade_pnls)
    if n == 0:
        return {
            "sims": sims,
            "n_trades": 0,
            "pnl_p5": 0.0,
            "pnl_p50": 0.0,
            "pnl_p95": 0.0,
            "dd_p5": 0.0,
            "dd_p50": 0.0,
            "dd_p95": 0.0,
            "ruin_rate": 0.0,
        }

    for _ in range(sims):
        eq = start_eq
        curve = [eq]

        # resample with replacement
        for _i in range(n):
            eq += random.choice(trade_pnls)
            curve.append(eq)

        pnl = eq - start_eq
        dd = max_drawdown(curve)

        pnls.append(pnl)
        dds.append(dd)

        if min(curve) < ruin_level:
            ruin_hits += 1

    return {
        "sims": sims,
        "n_trades": n,
        "pnl_p5": round(percentile(pnls, 0.05), 2),
        "pnl_p50": round(percentile(pnls, 0.50), 2),
        "pnl_p95": round(percentile(pnls, 0.95), 2),
        "dd_p5": round(percentile(dds, 0.05), 2),
        "dd_p50": round(percentile(dds, 0.50), 2),
        "dd_p95": round(percentile(dds, 0.95), 2),
        "ruin_rate": round(ruin_hits / sims, 4),
        "ruin_level": round(ruin_level, 2),
    }


def main() -> None:
    random.seed(int(MC["seed"]))

    print("\nCSS MONTE CARLO v28 — TREND PULLBACK (MULTI-ASSET)\n")
    all_summaries = []
    all_trades: List[float] = []

    for p in PRODUCTS:
        summary, trades = run_v25_collect_trades(p)
        all_summaries.append(summary)
        all_trades.extend(trades)
        print(summary)

    mc = run_monte_carlo(all_trades)
    print("\nMONTE CARLO (PORTFOLIO RESAMPLES)\n")
    print(mc)

    payload = {
        "strategy": "montecarlo_trend_pullback_v28",
        "cfg": CFG,
        "mc": MC,
        "per_asset": all_summaries,
        "portfolio_trade_realizations": len(all_trades),
        "portfolio_trade_pnls_sample": all_trades[:50],  # small sample for debugging
        "mc_results": mc,
    }

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = OUT / f"montecarlo_trend_pullback_v28_{stamp}.json"
    out.write_text(json.dumps(payload, indent=2))
    print("\nSaved:", out)


if __name__ == "__main__":
    main()
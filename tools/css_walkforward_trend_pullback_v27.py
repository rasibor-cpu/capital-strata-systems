"""
Capital Strata Systems (CSS)
Walk-Forward Validation v27 — Trend Pullback (Multi-Asset)

Purpose:
- Avoid "one-shot" backtest bias by rolling train/test windows.
- For each cycle:
  1) Train on N days (optimize a small parameter grid)
  2) Test on next M days (use best train params)
- Repeat until data exhausted.

Default:
- Total span: last 180 days
- Train: 90 days
- Test: 30 days
- Assets: BTC-USD, ETH-USD, SOL-USD
- Timeframe: 15m

NOTE: Research/backtest only.
"""

from __future__ import annotations

import json
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

BASE_CFG = {
    "granularity": 900,  # 15m
    "ema_fast": 20,
    "ema_slow": 50,
    "slope_lookback": 8,
    "atr_window": 20,
    "atr_stop_mult": 2.0,
    "min_atr_pct": 0.004,
    "cooldown": 10,
    "position_size": 0.05,
    "fee_rate": 0.0006,
    "tp1_r": 2.0,
    "tp1_frac": 0.5,
}

# Small grid (train-only selection)
GRID = {
    "min_slope_pct": [0.0010, 0.0013, 0.0016],
    "trail_atr_mult": [3.0, 3.5, 4.0],
}

WF = {
    "total_days": 180,
    "train_days": 90,
    "test_days": 30,
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


def slice_by_time(candles: List[Candle], start_ts: int, end_ts: int) -> List[Candle]:
    return [c for c in candles if start_ts <= c.ts < end_ts]


def run_engine_on_candles(candles: List[Candle], cfg: Dict) -> Dict[str, float]:
    capital = 1000.0
    cash = capital
    position = None
    cooldown = 0
    trades: List[float] = []
    in_pullback = False

    closes: List[float] = []
    warm = max(cfg["ema_slow"], cfg["atr_window"]) + cfg["slope_lookback"] + 5

    for i, c in enumerate(candles):
        closes.append(c.close)
        price = c.close

        if i < warm:
            continue

        if cooldown > 0:
            cooldown -= 1

        ema20 = ema(closes[-cfg["ema_fast"] :], cfg["ema_fast"])
        ema50 = ema(closes[-cfg["ema_slow"] :], cfg["ema_slow"])
        ema50_prev = ema(
            closes[-cfg["ema_slow"] - cfg["slope_lookback"] : -cfg["slope_lookback"]],
            cfg["ema_slow"],
        )
        if ema20 is None or ema50 is None or ema50_prev is None:
            continue

        slope = (ema50 - ema50_prev) / price
        if slope < cfg["min_slope_pct"]:
            continue

        atr_val = atr(candles[i - cfg["atr_window"] : i + 1])
        if atr_val is None:
            continue
        if (atr_val / price) < cfg["min_atr_pct"]:
            continue

        uptrend = price > ema50

        if uptrend and price <= ema20:
            in_pullback = True

        if position is None and cooldown == 0 and in_pullback and price > ema20:
            size_usd = cash * cfg["position_size"]
            if size_usd <= 0:
                in_pullback = False
                continue
            fee_in = size_usd * cfg["fee_rate"]
            cash -= (size_usd + fee_in)

            size = size_usd / price
            stop = price - (cfg["atr_stop_mult"] * atr_val)
            r = price - stop

            position = {"entry": price, "size": size, "stop": stop, "peak": price, "r": r, "tp1_done": False}
            in_pullback = False

        if position is not None:
            if price > position["peak"]:
                position["peak"] = price

            trail = position["peak"] - (cfg["trail_atr_mult"] * atr_val)
            if trail > position["stop"]:
                position["stop"] = trail

            tp1 = position["entry"] + (cfg["tp1_r"] * position["r"])

            if (not position["tp1_done"]) and c.high >= tp1:
                sell = position["size"] * cfg["tp1_frac"]
                val = sell * tp1
                fee_out = val * cfg["fee_rate"]
                pnl = (tp1 - position["entry"]) * sell - fee_out
                trades.append(pnl)
                cash += val - fee_out
                position["size"] -= sell
                position["tp1_done"] = True

            if c.low <= position["stop"]:
                exitp = position["stop"]
                sell = position["size"]
                val = sell * exitp
                fee_out = val * cfg["fee_rate"]
                pnl = (exitp - position["entry"]) * sell - fee_out
                trades.append(pnl)
                cash += val - fee_out
                position = None
                cooldown = cfg["cooldown"]

    equity = cash
    if position is not None:
        equity += position["size"] * candles[-1].close

    wins = sum(1 for t in trades if t > 0)
    losses = sum(1 for t in trades if t <= 0)

    return {
        "trades": int(len(trades)),
        "wins": int(wins),
        "losses": int(losses),
        "win_rate": round((wins / len(trades)) * 100, 2) if trades else 0.0,
        "final_equity": round(equity, 2),
        "pnl": round(equity - capital, 2),
    }


def grid_candidates(base: Dict) -> List[Dict]:
    out = []
    for slope in GRID["min_slope_pct"]:
        for trail in GRID["trail_atr_mult"]:
            c = dict(base)
            c["min_slope_pct"] = slope
            c["trail_atr_mult"] = trail
            out.append(c)
    return out


def pick_best_on_train(train_candles: List[Candle], base: Dict) -> Tuple[Dict, Dict]:
    best_cfg = None
    best_res = None
    best_score = -1e18

    for cfg in grid_candidates(base):
        res = run_engine_on_candles(train_candles, cfg)
        # simple score: maximize pnl, break ties by fewer trades
        score = (res["pnl"] * 1000.0) - (res["trades"] * 0.1)
        if score > best_score:
            best_score = score
            best_cfg = cfg
            best_res = res

    assert best_cfg is not None and best_res is not None
    return best_cfg, best_res


def walk_forward(product: str, full_candles: List[Candle]) -> Dict:
    # define WF windows using timestamps (seconds)
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=WF["total_days"])

    start_ts = int(start.timestamp())
    end_ts = int(end.timestamp())

    train_sec = WF["train_days"] * 86400
    test_sec = WF["test_days"] * 86400

    cycles = []
    cursor = start_ts

    while True:
        train_start = cursor
        train_end = train_start + train_sec
        test_end = train_end + test_sec

        if test_end > end_ts:
            break

        train = slice_by_time(full_candles, train_start, train_end)
        test = slice_by_time(full_candles, train_end, test_end)

        if len(train) < 500 or len(test) < 200:
            cursor = train_end
            continue

        best_cfg, train_res = pick_best_on_train(train, BASE_CFG)
        test_res = run_engine_on_candles(test, best_cfg)

        cycles.append(
            {
                "train_range": [train_start, train_end],
                "test_range": [train_end, test_end],
                "best_params": {
                    "min_slope_pct": best_cfg["min_slope_pct"],
                    "trail_atr_mult": best_cfg["trail_atr_mult"],
                },
                "train": train_res,
                "test": test_res,
            }
        )

        cursor = train_end  # roll forward by one train window

    # aggregate test results
    total_test_pnl = round(sum(c["test"]["pnl"] for c in cycles), 2)
    total_test_trades = int(sum(c["test"]["trades"] for c in cycles))
    avg_test_pnl = round((total_test_pnl / len(cycles)), 2) if cycles else 0.0

    return {
        "product": product,
        "cycles": cycles,
        "wf_test_total_pnl": total_test_pnl,
        "wf_test_total_trades": total_test_trades,
        "wf_test_avg_pnl_per_cycle": avg_test_pnl,
        "cycle_count": len(cycles),
    }


def main() -> None:
    print("\nCSS WALK-FORWARD v27 — TREND PULLBACK (MULTI-ASSET)\n")

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=WF["total_days"])

    all_results = []
    portfolio_pnl = 0.0
    portfolio_trades = 0

    for p in PRODUCTS:
        candles = fetch(p, start, end, BASE_CFG["granularity"])
        r = walk_forward(p, candles)
        all_results.append(r)
        portfolio_pnl += float(r["wf_test_total_pnl"])
        portfolio_trades += int(r["wf_test_total_trades"])
        print(
            {
                "product": p,
                "cycle_count": r["cycle_count"],
                "wf_test_total_pnl": r["wf_test_total_pnl"],
                "wf_test_total_trades": r["wf_test_total_trades"],
                "wf_test_avg_pnl_per_cycle": r["wf_test_avg_pnl_per_cycle"],
            }
        )

    summary = {
        "strategy": "walkforward_trend_pullback_v27",
        "wf": WF,
        "base_cfg": BASE_CFG,
        "grid": GRID,
        "results": all_results,
        "portfolio_wf_test_total_pnl": round(portfolio_pnl, 2),
        "portfolio_wf_test_total_trades": int(portfolio_trades),
    }

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = OUT / f"walkforward_trend_pullback_v27_{stamp}.json"
    out.write_text(json.dumps(summary, indent=2))
    print("\nSaved:", out)


if __name__ == "__main__":
    main()
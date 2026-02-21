"""
5M Breakout Regime Analyzer (Pure Python, V2)

DIAGNOSTIC ONLY:
- Runs baseline breakout (cut, hold)
- Computes a rolling volatility SCORE = mean(abs(returns)) over last N
- Computes percentile of that vol SCORE across time
- Tags each trade with vol-score percentile at entry
- Prints regime distribution (bars + trades) and PnL by regime

No filtering. No sizing changes. No strategy changes.
"""

from __future__ import annotations
import sys, os, csv, argparse, statistics
from typing import List, Optional, Dict
from dataclasses import dataclass

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine.sim.paper_simulator import PaperSimulator
from engine.sim.metrics import metrics_from_simulator

SIGNAL_SCALE = 200.0
BASE_SIZE = 100_000

ROLL_RET_WINDOW = 5        # for signal/vol score
VOL_SCORE_WINDOW = 10      # slightly longer for regime stability


def load_close_series(path: str) -> List[float]:
    closes = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        first = next(reader)
        has_header = not first[0][:1].isdigit()

        if has_header:
            headers = [x.strip().lower() for x in first]
            idx = headers.index("close") if "close" in headers else 4
            for row in reader:
                closes.append(float(row[idx]))
        else:
            # assume OHLCV: timestamp,open,high,low,close,vol
            closes.append(float(first[4]))
            for row in reader:
                closes.append(float(row[4]))
    if len(closes) < 25:
        raise ValueError("Not enough rows.")
    return closes


def aggregate_5m(closes_1m: List[float]) -> List[float]:
    closes_5m: List[float] = []
    for i in range(0, len(closes_1m), 5):
        block = closes_1m[i:i+5]
        if len(block) == 5:
            closes_5m.append(block[-1])
    if len(closes_5m) < 12:
        raise ValueError("Not enough 5m bars.")
    return closes_5m


def momentum_sig(prev: float, px: float) -> float:
    ret = (px - prev) / prev if prev > 0 else 0.0
    x = ret * SIGNAL_SCALE
    return max(-1.0, min(1.0, x))


def percentile_rank(value: float, data: List[float]) -> float:
    if not data:
        return 0.0
    s = sorted(data)
    count = 0
    for x in s:
        if x <= value:
            count += 1
        else:
            break
    return 100.0 * count / len(s)


@dataclass
class TradeTag:
    direction: str
    entry_price: float
    exit_price: float
    vol_pct: float
    pnl: float


def run_analysis(closes_5m: List[float], cutoff: float, hold: int):
    sim = PaperSimulator(starting_equity=100_000.0)

    returns: List[float] = []
    vol_scores: List[float] = []          # rolling vol score per bar (aligned to bar index)
    vol_pcts: List[float] = []            # percentile per bar

    prev = closes_5m[0]

    open_trade: Optional[Dict] = None
    trades: List[TradeTag] = []

    # First pass: build vol_scores
    for i in range(1, len(closes_5m)):
        px = closes_5m[i]
        r = (px - prev) / prev if prev > 0 else 0.0
        returns.append(r)

        if len(returns) >= VOL_SCORE_WINDOW:
            score = statistics.mean([abs(x) for x in returns[-VOL_SCORE_WINDOW:]])
        else:
            score = 0.0
        vol_scores.append(score)

        prev = px

    # Second pass: compute percentile per bar using vol_scores history up to that point
    history: List[float] = []
    for score in vol_scores:
        history.append(score)
        vol_pcts.append(percentile_rank(score, history))

    # Trading pass
    prev = closes_5m[0]
    for i in range(1, len(closes_5m)):
        px = closes_5m[i]
        sig = momentum_sig(prev, px)

        # vol percentile aligned: vol_pcts index is (i-1)
        vol_pct = vol_pcts[i-1] if (i-1) < len(vol_pcts) else 0.0

        # EXIT
        if open_trade is not None:
            if i - open_trade["index"] >= hold:
                entry = open_trade["price"]
                direction = open_trade["direction"]
                exit_price = px

                pnl = (exit_price - entry) * BASE_SIZE if direction == "LONG" else (entry - exit_price) * BASE_SIZE

                sim.simulate_trade(
                    instrument="BREAKOUT_BASELINE",
                    direction=direction,
                    entry_price=entry,
                    exit_price=exit_price,
                    size=BASE_SIZE,
                )
                trades.append(TradeTag(direction, entry, exit_price, open_trade["vol_pct"], pnl))
                open_trade = None

        # ENTRY (no filtering)
        if open_trade is None:
            if sig > cutoff:
                open_trade = {"direction": "LONG", "price": px, "index": i, "vol_pct": vol_pct}
            elif sig < -cutoff:
                open_trade = {"direction": "SHORT", "price": px, "index": i, "vol_pct": vol_pct}

        prev = px

    report = metrics_from_simulator(sim)
    equity_end = sim.state.equity

    return report, equity_end, trades, vol_pcts


def bucket(pct: float) -> str:
    if pct > 70:
        return "HIGH_VOL"
    if pct >= 30:
        return "MID_VOL"
    return "LOW_VOL"


def summarize(trades: List[TradeTag]):
    out = {"HIGH_VOL": {"trades": 0, "pnl": 0.0},
           "MID_VOL": {"trades": 0, "pnl": 0.0},
           "LOW_VOL": {"trades": 0, "pnl": 0.0}}
    for t in trades:
        b = bucket(t.vol_pct)
        out[b]["trades"] += 1
        out[b]["pnl"] += t.pnl
    return out


def summarize_bars(vol_pcts: List[float]):
    out = {"HIGH_VOL": 0, "MID_VOL": 0, "LOW_VOL": 0}
    for p in vol_pcts:
        out[bucket(p)] += 1
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv_path")
    ap.add_argument("--cut", type=float, default=0.04)
    ap.add_argument("--hold", type=int, default=2)
    args = ap.parse_args()

    closes_1m = load_close_series(args.csv_path)
    closes_5m = aggregate_5m(closes_1m)

    report, equity_end, trades, vol_pcts = run_analysis(closes_5m, args.cut, args.hold)

    print("\n=== BREAKOUT REGIME ANALYSIS (V2) ===")
    print(f"cut={args.cut}  hold={args.hold}")
    print(f"Total trades: {report.trades}")
    print(f"Win%: {report.win_rate*100:.1f}")
    print(f"Expectancy: {report.expectancy:.4f}")
    print(f"MaxDD%: {report.max_drawdown_pct:.4f}")
    print(f"Equity_end: {equity_end:.2f}")

    print("\nBar Regime Distribution:")
    bd = summarize_bars(vol_pcts)
    for k in ["LOW_VOL", "MID_VOL", "HIGH_VOL"]:
        print(f"{k}: bars={bd[k]}")

    print("\nTrade Segment Performance:")
    seg = summarize(trades)
    for k in ["LOW_VOL", "MID_VOL", "HIGH_VOL"]:
        print(f"{k}: trades={seg[k]['trades']}  total_pnl={seg[k]['pnl']:.2f}")


if __name__ == "__main__":
    main()
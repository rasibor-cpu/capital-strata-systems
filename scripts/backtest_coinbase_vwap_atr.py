import argparse
import csv
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

from backend.strategy.vwap_mean_reversion import (
    VWAPConfig,
    compute_vwap_from_candles,
    should_buy_mean_reversion,
)

COINBASE_EXCHANGE_API = "https://api.exchange.coinbase.com"

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = PROJECT_ROOT / "data_cache" / "coinbase_candles"
OUT_DIR = PROJECT_ROOT / "audit_logs" / "backtests"


@dataclass
class Candle:
    ts: int
    low: float
    high: float
    open: float
    close: float
    volume: float


@dataclass
class Position:
    asset: str
    entry: float
    size_usd: float  # notional exposure in USD
    tp: float
    sl: float
    entry_ts: int


def _parse_dt(s: str) -> datetime:
    # Accept YYYY-MM-DD or full ISO
    if "T" in s:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)


def _to_iso_z(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def fetch_candles_chunk(
    product_id: str,
    start: datetime,
    end: datetime,
    granularity_sec: int,
    timeout: int = 25,
) -> List[Candle]:
    url = f"{COINBASE_EXCHANGE_API}/products/{product_id}/candles"
    params = {"start": _to_iso_z(start), "end": _to_iso_z(end), "granularity": granularity_sec}
    headers = {"User-Agent": "CSS-Backtest/1.1"}

    for attempt in range(8):
        r = requests.get(url, params=params, headers=headers, timeout=timeout)
        if r.status_code == 429:
            time.sleep(min(2 ** attempt, 10))
            continue
        r.raise_for_status()
        data = r.json()  # [[time, low, high, open, close, volume], ...]

        out: List[Candle] = []
        for row in data:
            out.append(
                Candle(
                    ts=int(row[0]),
                    low=float(row[1]),
                    high=float(row[2]),
                    open=float(row[3]),
                    close=float(row[4]),
                    volume=float(row[5]),
                )
            )
        out.sort(key=lambda x: x.ts)
        return out

    raise RuntimeError(f"Failed to fetch candles for {product_id} after retries.")


def fetch_candles_paged(
    product_id: str,
    start: datetime,
    end: datetime,
    granularity_sec: int,
) -> List[Candle]:
    """
    Coinbase Exchange returns max 300 candles per request.
    We page forward in <= 300 * granularity seconds windows.
    Cached to disk so reruns are fast.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_name = (
        f"{product_id}_{granularity_sec}_"
        f"{start.strftime('%Y%m%dT%H%M%S')}_{end.strftime('%Y%m%dT%H%M%S')}.json"
    ).replace("/", "-")
    cache_path = CACHE_DIR / cache_name

    if cache_path.exists():
        with open(cache_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        return [Candle(**c) for c in raw]

    max_span = timedelta(seconds=granularity_sec * 300)
    cur = start
    seen = set()
    all_c: List[Candle] = []

    while cur < end:
        nxt = min(cur + max_span, end)
        chunk = fetch_candles_chunk(product_id, cur, nxt, granularity_sec)

        for c in chunk:
            if c.ts not in seen:
                all_c.append(c)
                seen.add(c.ts)

        cur = nxt

    all_c.sort(key=lambda x: x.ts)

    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump([c.__dict__ for c in all_c], f, indent=2, sort_keys=True)

    return all_c


def atr(candles: List[Candle], period: int = 14) -> Optional[float]:
    if len(candles) < period + 1:
        return None
    trs: List[float] = []
    for i in range(1, len(candles)):
        h = candles[i].high
        l = candles[i].low
        pc = candles[i - 1].close
        tr = max(h - l, abs(h - pc), abs(l - pc))
        trs.append(tr)
    return sum(trs[-period:]) / period


def to_strategy_dicts(candles: List[Candle]) -> List[Dict[str, Any]]:
    # Your VWAP function expects dict-like candles.
    return [
        {"start": c.ts, "open": c.open, "high": c.high, "low": c.low, "close": c.close, "volume": c.volume}
        for c in candles
    ]


def _round2(x: float) -> float:
    return float(round(float(x), 2))


def _compute_exit_pnl_usd(entry: float, exit_px: float, notional_usd: float) -> float:
    """
    Correct PnL model: size_usd is NOTIONAL exposure.
    units = notional / entry
    pnl = units * (exit - entry)
    """
    if entry <= 0 or notional_usd <= 0:
        return 0.0
    units = notional_usd / entry
    return units * (exit_px - entry)


def _apply_costs(pnl_gross: float, fee_bps: float, slippage_bps: float, notional_usd: float) -> Tuple[float, float]:
    """
    Simple all-in cost model: cost is charged on notional, not on pnl.
    fee_bps and slippage_bps are basis points (1 bp = 0.01%).
    Returns: (pnl_net, costs_usd)
    """
    bps_total = max(0.0, float(fee_bps)) + max(0.0, float(slippage_bps))
    costs = (bps_total / 10000.0) * max(0.0, float(notional_usd))
    pnl_net = pnl_gross - costs
    return pnl_net, costs


def backtest(
    products: List[str],
    start: datetime,
    end: datetime,
    granularity_sec: int,
    vwap_window: int,
    atr_period: int,
    atr_sl_mult: float,
    atr_tp_mult: float,
    initial_equity: float,
    portfolio_risk: float,
    max_positions: int,
    max_leverage: float,
    fee_bps: float,
    slippage_bps: float,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    vcfg = VWAPConfig()

    series: Dict[str, List[Candle]] = {}
    for p in products:
        series[p] = fetch_candles_paged(p, start, end, granularity_sec)
        if len(series[p]) < (max(vwap_window, atr_period) + 20):
            raise RuntimeError(f"Not enough candles for {p}. Got {len(series[p])}.")

    # Common timestamp alignment
    common_ts = sorted(set.intersection(*[set(c.ts for c in series[p]) for p in products]))
    if not common_ts:
        raise RuntimeError("No overlapping timestamps across products.")

    equity = float(initial_equity)
    peak = float(initial_equity)

    positions: Dict[str, Optional[Position]] = {p: None for p in products}
    trades: List[Dict[str, Any]] = []
    curve: List[Dict[str, Any]] = []

    # Tracking for reconciliation
    realized_gross = 0.0
    realized_costs = 0.0
    realized_net = 0.0

    # Quick index maps to avoid O(n) scanning
    idx_map: Dict[str, Dict[int, int]] = {}
    for p in products:
        idx_map[p] = {c.ts: i for i, c in enumerate(series[p])}

    for t in common_ts:
        # EXIT first
        for p in products:
            pos = positions[p]
            if pos is None:
                continue

            i = idx_map[p][t]
            price = float(series[p][i].close)

            hit_tp = price >= pos.tp
            hit_sl = price <= pos.sl
            if hit_tp or hit_sl:
                pnl_gross = _compute_exit_pnl_usd(pos.entry, price, pos.size_usd)
                pnl_net, costs = _apply_costs(pnl_gross, fee_bps, slippage_bps, pos.size_usd)

                equity += pnl_net

                realized_gross += pnl_gross
                realized_costs += costs
                realized_net += pnl_net

                trades.append(
                    {
                        "ts": t,
                        "event": "TP" if hit_tp else "SL",
                        "asset": p,
                        "entry": pos.entry,
                        "exit": price,
                        "size_usd": pos.size_usd,
                        "tp": pos.tp,
                        "sl": pos.sl,
                        "pnl_gross": pnl_gross,
                        "costs": costs,
                        "pnl_net": pnl_net,
                        "equity_after": equity,
                    }
                )
                positions[p] = None

        # ENTRY next
        open_count = sum(1 for x in positions.values() if x is not None)
        slots = max_positions - open_count
        if slots > 0:
            # NOTE: portfolio_risk is per-step budget allocated across available slots
            risk_per_trade = (equity * portfolio_risk) / slots if slots > 0 else 0.0
            risk_per_trade = max(0.0, float(risk_per_trade))

            for p in products:
                if slots <= 0:
                    break
                if positions[p] is not None:
                    continue

                i = idx_map[p][t]
                if i < (max(vwap_window, atr_period) + 10):
                    continue

                # Build a window ending at i
                window = series[p][i - (vwap_window + 10) : i + 1]
                vwap_raw = compute_vwap_from_candles(to_strategy_dicts(window), vwap_window)
                if vwap_raw is None:
                    continue
                vwap = float(vwap_raw)

                price = float(series[p][i].close)
                spread_bps = ((price - vwap) / vwap) * 10000.0 if vwap else 0.0

                buy_ok, reason = should_buy_mean_reversion(price, vwap, spread_bps, vcfg)
                if not buy_ok:
                    continue

                a = atr(series[p][: i + 1], atr_period)
                if a is None or a <= 0:
                    continue

                stop_dist = a * atr_sl_mult
                if stop_dist <= 0:
                    continue

                # size_usd (NOTIONAL) so that stop loss approx equals risk_per_trade
                size_usd = (risk_per_trade * price / stop_dist) if stop_dist > 0 else 0.0
                size_usd = float(max(0.0, size_usd))

                # Leverage cap: total open notionals <= equity * max_leverage
                if max_leverage > 0:
                    open_notional = sum(pos2.size_usd for pos2 in positions.values() if pos2 is not None)
                    remaining_capacity = max(0.0, (equity * max_leverage) - open_notional)
                    if remaining_capacity <= 0:
                        continue
                    size_usd = min(size_usd, remaining_capacity)

                if size_usd <= 0:
                    continue

                tp = price + (a * atr_tp_mult)
                sl = price - (a * atr_sl_mult)

                positions[p] = Position(asset=p, entry=price, size_usd=size_usd, tp=tp, sl=sl, entry_ts=t)

                trades.append(
                    {
                        "ts": t,
                        "event": "ENTRY",
                        "asset": p,
                        "entry": price,
                        "size_usd": size_usd,
                        "vwap": vwap,
                        "spread_bps": spread_bps,
                        "atr": a,
                        "tp": tp,
                        "sl": sl,
                        "reason": reason,
                        "equity_after": equity,
                    }
                )

                slots -= 1

        peak = max(peak, equity)
        dd = ((equity - peak) / peak) * 100.0 if peak else 0.0
        curve.append(
            {
                "ts": t,
                "equity": equity,
                "peak": peak,
                "drawdown_pct": dd,
                "open_positions": sum(1 for x in positions.values() if x is not None),
            }
        )

    # Add a final reconciliation row (kept in-memory for summary)
    # equity_end = initial + realized_net (no other cashflows modeled)
    # We'll compute this in summary to sanity-check.
    return trades, curve


def save_outputs(
    run_id: str,
    trades: List[Dict[str, Any]],
    curve: List[Dict[str, Any]],
    initial_equity: float,
    fee_bps: float,
    slippage_bps: float,
) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / run_id
    out.mkdir(parents=True, exist_ok=True)

    with open(out / "trades.jsonl", "w", encoding="utf-8") as f:
        for row in trades:
            f.write(json.dumps(row) + "\n")

    with open(out / "equity_curve.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(curve[0].keys()))
        w.writeheader()
        for row in curve:
            w.writerow(row)

    exits = [x for x in trades if x.get("event") in ("TP", "SL")]
    wins = [x for x in exits if float(x.get("pnl_net", 0.0)) > 0]
    losses = [x for x in exits if float(x.get("pnl_net", 0.0)) <= 0]

    total_gross = sum(float(x.get("pnl_gross", 0.0)) for x in exits)
    total_costs = sum(float(x.get("costs", 0.0)) for x in exits)
    total_net = sum(float(x.get("pnl_net", 0.0)) for x in exits)

    final_equity = float(curve[-1]["equity"]) if curve else None
    expected_final = (float(initial_equity) + float(total_net)) if final_equity is not None else None
    recon_diff = (final_equity - expected_final) if (final_equity is not None and expected_final is not None) else None

    summary = {
        "run_id": run_id,
        "entries": sum(1 for x in trades if x.get("event") == "ENTRY"),
        "exits": len(exits),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": (len(wins) / len(exits)) if exits else 0.0,
        "total_pnl_gross": total_gross,
        "total_costs": total_costs,
        "total_pnl_net": total_net,
        "initial_equity": float(initial_equity),
        "final_equity": final_equity,
        "expected_final_equity": expected_final,
        "equity_reconciliation_diff": recon_diff,
        "equity_reconciliation_ok": (abs(recon_diff) < 1e-6) if recon_diff is not None else False,
        "max_drawdown_pct": min((float(r["drawdown_pct"]) for r in curve), default=0.0),
        "fee_bps": float(fee_bps),
        "slippage_bps": float(slippage_bps),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }

    with open(out / "summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, sort_keys=True)

    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="CSS Backtest: VWAP Mean Reversion + ATR TP/SL (Coinbase Exchange candles)")
    ap.add_argument("--products", default="BTC-USD,ETH-USD,SOL-USD")
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("--granularity", type=int, default=900)  # 15m
    ap.add_argument("--vwap_window", type=int, default=20)
    ap.add_argument("--atr_period", type=int, default=14)
    ap.add_argument("--atr_sl", type=float, default=1.5)
    ap.add_argument("--atr_tp", type=float, default=2.5)
    ap.add_argument("--initial_equity", type=float, default=146.0)
    ap.add_argument("--portfolio_risk", type=float, default=0.02)
    ap.add_argument("--max_positions", type=int, default=3)

    # NEW: realism + safety
    ap.add_argument("--max_leverage", type=float, default=2.0, help="Cap total open notional to equity * max_leverage")
    ap.add_argument("--fee_bps", type=float, default=0.0, help="Fee in bps charged on notional at exit (simple model)")
    ap.add_argument("--slippage_bps", type=float, default=0.0, help="Slippage in bps charged on notional at exit")

    args = ap.parse_args()

    products = [p.strip() for p in args.products.split(",") if p.strip()]
    start = _parse_dt(args.start)
    end = _parse_dt(args.end)

    run_id = f"cb_vwap_atr_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    print("\n" + "=" * 80)
    print("CSS BACKTEST — Coinbase Historical Candles (NO LIVE TRADING)")
    print("=" * 80)
    print("Run:", run_id)
    print("Products:", products)
    print("Range (UTC):", start.isoformat(), "->", end.isoformat())
    print("Granularity (sec):", args.granularity)
    print("VWAP window:", args.vwap_window, "| ATR period:", args.atr_period)
    print("ATR SL:", args.atr_sl, "| ATR TP:", args.atr_tp)
    print("Initial equity:", args.initial_equity, "| Portfolio risk:", args.portfolio_risk)
    print("Max positions:", args.max_positions)
    print("Max leverage:", args.max_leverage)
    print("Costs (bps): fee =", args.fee_bps, "| slippage =", args.slippage_bps)
    print("=" * 80)

    trades, curve = backtest(
        products=products,
        start=start,
        end=end,
        granularity_sec=args.granularity,
        vwap_window=args.vwap_window,
        atr_period=args.atr_period,
        atr_sl_mult=args.atr_sl,
        atr_tp_mult=args.atr_tp,
        initial_equity=args.initial_equity,
        portfolio_risk=args.portfolio_risk,
        max_positions=args.max_positions,
        max_leverage=args.max_leverage,
        fee_bps=args.fee_bps,
        slippage_bps=args.slippage_bps,
    )

    out = save_outputs(
        run_id=run_id,
        trades=trades,
        curve=curve,
        initial_equity=args.initial_equity,
        fee_bps=args.fee_bps,
        slippage_bps=args.slippage_bps,
    )

    with open(out / "summary.json", "r", encoding="utf-8") as f:
        s = json.load(f)

    print("\nSUMMARY")
    keys = [
        "entries",
        "exits",
        "wins",
        "losses",
        "win_rate",
        "total_pnl_gross",
        "total_costs",
        "total_pnl_net",
        "initial_equity",
        "final_equity",
        "expected_final_equity",
        "equity_reconciliation_diff",
        "equity_reconciliation_ok",
        "max_drawdown_pct",
    ]
    for k in keys:
        v = s.get(k)
        if isinstance(v, float):
            print(f"- {k}: {_round2(v)}")
        else:
            print(f"- {k}: {v}")

    print("\nSaved to:", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
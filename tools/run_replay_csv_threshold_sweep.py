"""
tools/run_replay_csv_threshold_sweep.py

Institutional Replay Runner (FULL PATH + Cost Shock Controls)
-------------------------------------------------------------
- Deterministic CSV replay (research-only)
- minsig gating
- institutional cost model (spread/slip/commission/impact)
- cost-shock multipliers via CLI
- writes trade_pnls + equity_curve to JSON for true drawdown analysis

SAFE: no broker calls.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import inspect
from datetime import datetime, timezone
from collections import deque
from typing import List, Dict, Any, Optional

from engine.strategy.signal_engine import SignalEngine
from engine.strategy.behaviour_mapper import get_profile_for_behaviour
from engine.performance.pnl_tracker import PnLTracker


# ============================================================
# INSTITUTIONAL COST MODEL (pips)
# ============================================================

class InstitutionalCostModel:
    pip_scale: float = 10000.0

    spread_pips_roundtrip: float = 0.4
    base_slip_pips_per_side: float = 0.1
    vol_slip_factor: float = 0.05
    commission_pips_roundtrip: float = 0.1
    impact_pips_per_side: float = 0.05

    def roundtrip_cost_pips(self, bar_range_pips: float) -> float:
        spread = self.spread_pips_roundtrip
        slip = (2 * self.base_slip_pips_per_side) + (self.vol_slip_factor * bar_range_pips)
        commission = self.commission_pips_roundtrip
        impact = 2 * self.impact_pips_per_side
        return spread + slip + commission + impact

    def as_dict(self) -> Dict[str, float]:
        return {
            "spread_pips_roundtrip": self.spread_pips_roundtrip,
            "base_slip_pips_per_side": self.base_slip_pips_per_side,
            "vol_slip_factor": self.vol_slip_factor,
            "commission_pips_roundtrip": self.commission_pips_roundtrip,
            "impact_pips_per_side": self.impact_pips_per_side,
        }


# ============================================================
# PnLTracker adapter (signature-introspected)
# ============================================================

def _tracker_init(starting_equity: float) -> PnLTracker:
    return PnLTracker(starting_equity)

def _safe_record_trade(tracker: PnLTracker, instrument: str, pnl_pips: float, ts: datetime, meta: Dict[str, Any]) -> None:
    if not hasattr(tracker, "record_trade"):
        return

    fn = getattr(tracker, "record_trade")
    sig = inspect.signature(fn)
    params = [p for p in sig.parameters.values() if p.name != "self"]

    # Prefer kwargs to prevent misbinding.
    name_map: Dict[str, Any] = {}

    def set_if_present(names, value):
        for n in names:
            if any(p.name == n for p in params):
                name_map[n] = value

    set_if_present(("instrument", "symbol", "pair"), instrument)
    set_if_present(("pnl", "pnl_pips", "net_pnl", "net_pnl_pips", "profit", "pl"), pnl_pips)
    set_if_present(("ts", "timestamp", "time", "dt", "datetime", "ts_utc"), ts)
    set_if_present(("meta", "metadata", "extra", "context"), meta)

    if name_map:
        try:
            fn(**name_map)
            return
        except TypeError:
            pass

    # Positional fallback (only if we can safely infer)
    def pick_value(pname: str):
        low = pname.lower()
        if "instr" in low or "symbol" in low or "pair" in low:
            return instrument
        if "pnl" in low or "profit" in low or low in ("pl",):
            return pnl_pips
        if "time" in low or low == "ts" or "date" in low or "dt" in low:
            return ts
        if "meta" in low or "extra" in low or "context" in low:
            return meta
        return None

    args = []
    for p in params:
        v = pick_value(p.name)
        if v is None and p.default is inspect._empty:
            raise TypeError(f"Cannot safely bind required param '{p.name}' in PnLTracker.record_trade")
        if v is not None:
            args.append(v)

    fn(*args)


def _safe_get_equity_curve(tracker: PnLTracker) -> Optional[List[float]]:
    for name in ("get_equity_curve", "equity_curve", "get_equity_path"):
        if hasattr(tracker, name):
            obj = getattr(tracker, name)
            try:
                curve = obj() if callable(obj) else obj
                if isinstance(curve, list) and curve:
                    return curve
            except TypeError:
                pass
    return None


# ============================================================
# MAIN
# ============================================================

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True)
    parser.add_argument("--instrument", required=True)
    parser.add_argument("--minsig", type=float, required=True)
    parser.add_argument("--behaviour", default="C")
    parser.add_argument("--ma-window", type=int, default=20)
    parser.add_argument("--starting-equity", type=float, default=1000.0)

    # Cost shock controls (institutional stress testing)
    parser.add_argument("--spread-mult", type=float, default=1.0)
    parser.add_argument("--base-slip-mult", type=float, default=1.0)
    parser.add_argument("--vol-slip-mult", type=float, default=1.0)
    parser.add_argument("--commission-mult", type=float, default=1.0)
    parser.add_argument("--impact-mult", type=float, default=1.0)

    args = parser.parse_args()

    profile = get_profile_for_behaviour(args.behaviour)
    engine = SignalEngine(profile)

    cost_model = InstitutionalCostModel()
    cost_model.spread_pips_roundtrip *= args.spread_mult
    cost_model.base_slip_pips_per_side *= args.base_slip_mult
    cost_model.vol_slip_factor *= args.vol_slip_mult
    cost_model.commission_pips_roundtrip *= args.commission_mult
    cost_model.impact_pips_per_side *= args.impact_mult

    tracker = _tracker_init(args.starting_equity)

    trade_pnls: List[float] = []
    equity_curve: List[float] = [args.starting_equity]
    equity = args.starting_equity

    window = deque(maxlen=max(2, args.ma_window))

    total_signals = 0
    threshold_blocks = 0
    trades = 0
    gross_pnl_pips = 0.0
    total_cost_pips = 0.0

    with open(args.csv, newline="") as f:
        reader = csv.DictReader(f)
        prev_price = None

        for row in reader:
            price = float(row["price"])
            ts_str = row.get("timestamp") or ""

            window.append(price)

            if prev_price is None:
                prev_price = price
                continue

            moving_avg = sum(window) / len(window)

            signal = engine.generate(
                instrument=args.instrument,
                price_now=price,
                price_prev=prev_price,
                moving_avg=moving_avg
            )

            total_signals += 1

            if signal.strength < args.minsig:
                threshold_blocks += 1
                prev_price = price
                continue

            if signal.direction not in ("BUY", "SELL"):
                prev_price = price
                continue

            if signal.direction == "BUY":
                gross = (price - prev_price) * cost_model.pip_scale
            else:
                gross = (prev_price - price) * cost_model.pip_scale

            bar_range_pips = abs(price - prev_price) * cost_model.pip_scale
            cost = cost_model.roundtrip_cost_pips(bar_range_pips)
            net = gross - cost

            trades += 1
            gross_pnl_pips += gross
            total_cost_pips += cost

            trade_pnls.append(net)
            equity += net
            equity_curve.append(equity)

            meta = {
                "instrument": args.instrument,
                "csv_ts": ts_str,
                "minsig": args.minsig,
                "cost_mults": {
                    "spread": args.spread_mult,
                    "base_slip": args.base_slip_mult,
                    "vol_slip": args.vol_slip_mult,
                    "commission": args.commission_mult,
                    "impact": args.impact_mult,
                }
            }
            ts = datetime.now(timezone.utc)
            _safe_record_trade(tracker, args.instrument, net, ts, meta)

            prev_price = price

    tracker_curve = _safe_get_equity_curve(tracker)
    if tracker_curve and len(tracker_curve) >= len(equity_curve):
        equity_curve = tracker_curve

    net_pnl_pips = gross_pnl_pips - total_cost_pips
    ending_equity = equity_curve[-1] if equity_curve else args.starting_equity

    summary: Dict[str, Any] = {
        "instrument": args.instrument,
        "pip_scale": cost_model.pip_scale,
        "bars_ma_window": args.ma_window,
        "min_signal_strength": args.minsig,
        "behaviour": args.behaviour,
        "profile_name": getattr(profile, "name", "UNKNOWN"),
        "total_signals": total_signals,
        "threshold_blocks": threshold_blocks,
        "trades": trades,
        "starting_equity": args.starting_equity,
        "ending_equity": ending_equity,
        "gross_pnl_pips": gross_pnl_pips,
        "total_cost_pips": total_cost_pips,
        "net_pnl_pips": net_pnl_pips,
        "trade_pnls": trade_pnls,
        "equity_curve": equity_curve,
        "cost_model": cost_model.as_dict(),
        "cost_multipliers": {
            "spread_mult": args.spread_mult,
            "base_slip_mult": args.base_slip_mult,
            "vol_slip_mult": args.vol_slip_mult,
            "commission_mult": args.commission_mult,
            "impact_mult": args.impact_mult,
        },
        "run_utc": datetime.now(timezone.utc).isoformat(),
    }

    os.makedirs("audit_logs/threshold_sweep", exist_ok=True)
    tag = f"minsig_{str(args.minsig).replace('.', '_')}_full"
    shock = f"sp{args.spread_mult}_bs{args.base_slip_mult}_vs{args.vol_slip_mult}_cm{args.commission_mult}_im{args.impact_mult}"
    out_path = f"audit_logs/threshold_sweep/{tag}_{shock}.json"

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print("\n=== CSS REPLAY SUMMARY (FULL PATH) ===")
    print(json.dumps({k: summary[k] for k in (
        "instrument","min_signal_strength","trades","starting_equity","ending_equity",
        "gross_pnl_pips","total_cost_pips","net_pnl_pips","threshold_blocks"
    )}, indent=2))
    print("Wrote:", out_path)


if __name__ == "__main__":
    main()
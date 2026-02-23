"""
tools/run_drawdown_stress_from_deciles.py

Drawdown Stress Test (SAFE) — Decile-Implied Monte Carlo
--------------------------------------------------------
Purpose:
- Consume a threshold sweep JSON (e.g., audit_logs/threshold_sweep/minsig_0.8.json)
- Use decile stats (trades, win_rate, avg_pnl_per_trade) to generate many synthetic
  trade paths consistent with the observed signal-quality structure.
- Compute max drawdown distribution and key tail percentiles.

Why this exists:
- Institutional governance requires tail-risk awareness BEFORE any live feed.
- This is NOT a broker sim. It is NOT an execution model. It is a statistical
  stress lens over the alpha-layer decile structure.

Assumptions (explicit):
- Within each decile, per-trade PnL is a two-point distribution:
    +M on "win", -M on "loss"
  where M is selected so that:
    E[PnL] = avg_pnl_per_trade given the decile win_rate
  (symmetric-magnitude assumption; conservative in some regimes, optimistic in others).
- Decile selection per trade is weighted by observed decile trade counts.

Outputs:
- Writes a JSON report to audit_logs/stress_tests/
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple


# -----------------------------
# Helpers
# -----------------------------

def _pct(values: List[float], p: float) -> float:
    if not values:
        return float("nan")
    vals = sorted(values)
    if p <= 0:
        return vals[0]
    if p >= 100:
        return vals[-1]
    k = (len(vals) - 1) * (p / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return vals[int(k)]
    return vals[f] + (vals[c] - vals[f]) * (k - f)


def _max_drawdown(equity_curve: List[float]) -> float:
    peak = -float("inf")
    max_dd = 0.0
    for x in equity_curve:
        if x > peak:
            peak = x
        if peak > 0:
            dd = (peak - x) / peak
            if dd > max_dd:
                max_dd = dd
    return max_dd


@dataclass(frozen=True)
class DecileModel:
    decile: int
    trades: int
    win_rate: float
    mean_pnl: float
    win_pnl: float
    loss_pnl: float


def _build_decile_models(sweep: Dict[str, Any]) -> Tuple[List[DecileModel], int, float]:
    deciles = sweep.get("decile_expectancy", [])
    if not deciles:
        raise ValueError("Input sweep JSON has no 'decile_expectancy' list.")

    total_trades = int(sweep.get("trades", 0))
    starting_equity = float(sweep.get("starting_equity", 1000.0))

    models: List[DecileModel] = []
    trade_sum = 0

    for d in deciles:
        decile_id = int(d.get("decile"))
        trades = int(d.get("trades", 0))
        win_rate = float(d.get("win_rate", 0.0))
        mean_pnl = float(d.get("avg_pnl_per_trade", 0.0))

        # Two-point symmetric magnitude model:
        # mean = p*(+M) + (1-p)*(-M) = (2p - 1) * M  =>  M = mean / (2p - 1)
        denom = (2.0 * win_rate) - 1.0

        # Guardrails to avoid blowups near 50% win rate
        if abs(denom) < 1e-6:
            # If win rate ~50%, use a small magnitude consistent with mean
            M = abs(mean_pnl) if abs(mean_pnl) > 0 else 0.0
        else:
            M = mean_pnl / denom

        M = abs(M)  # enforce symmetric magnitude

        # Construct win/loss pnl. If mean_pnl is negative, this model cannot match it
        # under symmetric magnitudes unless win_rate < 0.5. We preserve sign via:
        # - If mean_pnl >= 0: win=+M, loss=-M
        # - If mean_pnl < 0 : win=-M, loss=+M  (rare; indicates inversion)
        if mean_pnl >= 0:
            win_pnl = +M
            loss_pnl = -M
        else:
            win_pnl = -M
            loss_pnl = +M

        models.append(
            DecileModel(
                decile=decile_id,
                trades=trades,
                win_rate=win_rate,
                mean_pnl=mean_pnl,
                win_pnl=win_pnl,
                loss_pnl=loss_pnl,
            )
        )
        trade_sum += trades

    # If sweep "trades" differs from decile sum (minor rounding), use decile sum
    if total_trades <= 0:
        total_trades = trade_sum
    else:
        # pick the more consistent one
        if abs(total_trades - trade_sum) > max(10, int(0.01 * total_trades)):
            total_trades = trade_sum

    return models, total_trades, starting_equity


def _weighted_decile_choice(models: List[DecileModel]) -> List[Tuple[float, DecileModel]]:
    total = sum(m.trades for m in models)
    if total <= 0:
        raise ValueError("All deciles have zero trades.")
    cumulative: List[Tuple[float, DecileModel]] = []
    acc = 0.0
    for m in models:
        w = m.trades / total
        acc += w
        cumulative.append((acc, m))
    cumulative[-1] = (1.0, cumulative[-1][1])
    return cumulative


def _sample_decile(cum: List[Tuple[float, DecileModel]], rng: random.Random) -> DecileModel:
    r = rng.random()
    for cutoff, model in cum:
        if r <= cutoff:
            return model
    return cum[-1][1]


def run_simulation(models: List[DecileModel], n_trades: int, starting_equity: float, rng: random.Random) -> Dict[str, Any]:
    cum = _weighted_decile_choice(models)

    equity = starting_equity
    peak = starting_equity
    max_dd = 0.0

    # Track basic stats
    pnl_sum = 0.0
    wins = 0
    losses = 0

    for _ in range(n_trades):
        m = _sample_decile(cum, rng)
        is_win = (rng.random() < m.win_rate)
        pnl = m.win_pnl if is_win else m.loss_pnl

        equity += pnl
        pnl_sum += pnl

        if is_win:
            wins += 1
        else:
            losses += 1

        if equity > peak:
            peak = equity
        if peak > 0:
            dd = (peak - equity) / peak
            if dd > max_dd:
                max_dd = dd

    return {
        "ending_equity": equity,
        "net_pnl": pnl_sum,
        "wins": wins,
        "losses": losses,
        "max_drawdown_pct": max_dd,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", required=True, help="Path to minsig sweep JSON (e.g., audit_logs/threshold_sweep/minsig_0.8.json)")
    ap.add_argument("--sims", type=int, default=500, help="Number of Monte Carlo simulations (default: 500)")
    ap.add_argument("--seed", type=int, default=1337, help="RNG seed (default: 1337)")
    args = ap.parse_args()

    with open(args.json, "r", encoding="utf-8") as f:
        sweep = json.load(f)

    models, n_trades, starting_equity = _build_decile_models(sweep)

    rng = random.Random(args.seed)

    dd_list: List[float] = []
    end_eq: List[float] = []
    net_pnl: List[float] = []

    for i in range(args.sims):
        # Derive a new seed per simulation for reproducibility
        sim_rng = random.Random(rng.randint(1, 10_000_000))
        res = run_simulation(models, n_trades, starting_equity, sim_rng)
        dd_list.append(float(res["max_drawdown_pct"]))
        end_eq.append(float(res["ending_equity"]))
        net_pnl.append(float(res["net_pnl"]))

    report = {
        "tool": "run_drawdown_stress_from_deciles.py",
        "run_utc": datetime.now(timezone.utc).isoformat(),
        "input_json": os.path.normpath(args.json),
        "assumption": "Two-point symmetric win/loss magnitude per decile; decile chosen by observed trade-count weights.",
        "sims": args.sims,
        "seed": args.seed,
        "n_trades_per_sim": n_trades,
        "starting_equity": starting_equity,
        "summary": {
            "max_drawdown_pct_p50": _pct(dd_list, 50),
            "max_drawdown_pct_p80": _pct(dd_list, 80),
            "max_drawdown_pct_p90": _pct(dd_list, 90),
            "max_drawdown_pct_p95": _pct(dd_list, 95),
            "max_drawdown_pct_p99": _pct(dd_list, 99),
            "ending_equity_p50": _pct(end_eq, 50),
            "ending_equity_p05": _pct(end_eq, 5),
            "ending_equity_p01": _pct(end_eq, 1),
            "net_pnl_p50": _pct(net_pnl, 50),
            "net_pnl_p05": _pct(net_pnl, 5),
            "net_pnl_p01": _pct(net_pnl, 1),
        },
        "deciles_used": [
            {
                "decile": m.decile,
                "trades": m.trades,
                "win_rate": m.win_rate,
                "avg_pnl_per_trade": m.mean_pnl,
                "win_pnl": m.win_pnl,
                "loss_pnl": m.loss_pnl,
            }
            for m in models
        ],
    }

    out_dir = os.path.join("audit_logs", "stress_tests")
    os.makedirs(out_dir, exist_ok=True)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_path = os.path.join(out_dir, f"stress_deciles_{stamp}.json")

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print("Wrote:", out_path)
    print("Max DD pct (p50/p90/p95/p99):",
          report["summary"]["max_drawdown_pct_p50"],
          report["summary"]["max_drawdown_pct_p90"],
          report["summary"]["max_drawdown_pct_p95"],
          report["summary"]["max_drawdown_pct_p99"])


if __name__ == "__main__":
    main()
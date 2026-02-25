from __future__ import annotations

import csv
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from engine.execution.execution_gate import ExecutionGate
from engine.performance.pnl_tracker import PnLTracker
from engine.capital.compounding_engine import CompoundingEngine

BEHAVIOUR = "C"
MIN_STRENGTH = 0.72
MAX_R_MULTIPLIER = 2.5

STARTING_EQUITY = 100_000.0
STOP_DISTANCE_PCT = 0.001
REGIME_PERSISTENCE = 0.65

# launcher overrides this via tools.run_rvol_launcher
DATA_DIR = REPO_ROOT / "data" / "history"


def decision_final(dec: Any) -> str:
    if not isinstance(dec, dict):
        return ""
    inner = dec.get("decision", {})
    if isinstance(inner, dict):
        return str(inner.get("final", "")).upper()
    return str(dec.get("final", "")).upper()


def is_allow(dec: Any) -> bool:
    f = decision_final(dec)
    if f in {"ALLOW", "APPROVED"}:
        return True
    if isinstance(dec, dict):
        if dec.get("ok", None) is True:
            return True
        if str(dec.get("status", "")).upper() in {"ALLOW", "APPROVED"}:
            return True
    return False


def extract_risk_pct(dec: Any, fallback: float) -> float:
    try:
        if isinstance(dec, dict):
            dbg = dec.get("debug", {})
            rp = dbg.get("risk_pct", None)
            if rp is None:
                rp = dec.get("risk_pct", None)
            return float(rp) if rp is not None else float(fallback)
    except Exception:
        pass
    return float(fallback)


def load_all_data() -> Dict[str, List[Tuple[str, float]]]:
    files = sorted(Path(DATA_DIR).glob("*_M5_1year.csv"))
    if not files:
        raise RuntimeError(f"No *_M5_1year.csv files found in {DATA_DIR}")

    datasets: Dict[str, List[Tuple[str, float]]] = {}
    for fp in files:
        inst = fp.name.replace("_M5_1year.csv", "")
        rows: List[Tuple[str, float]] = []
        with fp.open("r", encoding="utf-8-sig", newline="") as f:
            r = csv.DictReader(f)
            for row in r:
                ts = row.get("timestamp") or row.get("time") or row.get("datetime") or ""
                px = row.get("close") or row.get("price")
                if not ts or px is None:
                    continue
                try:
                    rows.append((ts, float(px)))
                except Exception:
                    continue
        if rows:
            datasets[inst] = rows

    if not datasets:
        raise RuntimeError(f"All datasets empty under {DATA_DIR}")

    return datasets


def anchor_timestamps(datasets: Dict[str, List[Tuple[str, float]]]) -> List[str]:
    first_inst = sorted(datasets.keys())[0]
    return [ts for ts, _ in datasets[first_inst]]


def main() -> None:
    print("\n==== PHASE 1 PORTFOLIO REPLAY V5 (CONVEXITY TRIM) [RVOL RUNNER] ====\n")
    print(f"Behaviour: {BEHAVIOUR}")
    print(f"Min strength: {MIN_STRENGTH}")
    print(f"Max R multiplier: {MAX_R_MULTIPLIER}\n")

    datasets = load_all_data()
    instruments = sorted(datasets.keys())
    ts_list = anchor_timestamps(datasets)

    execution_gate = ExecutionGate()
    pnl_tracker = PnLTracker(starting_equity=STARTING_EQUITY)
    compounding = CompoundingEngine()

    prev_prices: Dict[str, float] = {inst: datasets[inst][0][1] for inst in instruments}

    equity_peak = STARTING_EQUITY
    trades = 0
    gate_blocks = 0
    max_drawdown = 0.0
    new_highs = 0

    for idx, _ts in enumerate(ts_list, start=1):
        approved: List[Tuple[str, float, float, Any]] = []

        for inst in instruments:
            series = datasets[inst]
            if idx - 1 >= len(series):
                continue

            _t, price = series[idx - 1]
            prev_price = prev_prices[inst]
            side = "BUY" if price >= prev_price else "SELL"

            equity = float(pnl_tracker.current_equity)
            base_notional = float(equity)

            # ✅ EXACT keywords that your ExecutionGate.evaluate_trade accepts
            dec = execution_gate.evaluate_trade(
                instrument=inst,
                side=side,
                notional=base_notional,
                stop_distance_pct=float(STOP_DISTANCE_PCT),
                equity=float(equity),
                equity_peak=float(equity_peak),
                regime_persistence=float(REGIME_PERSISTENCE),
                policy="core",
                current_allocations=None,
                rebalance_target_weights=None,
                volatility_state="MEDIUM",
                regime_state="NORMAL",
            )

            if not is_allow(dec):
                gate_blocks += 1
                prev_prices[inst] = price
                continue

            approved.append((inst, price, prev_price, dec))
            prev_prices[inst] = price

        for inst, price, prev_price, dec in approved:
            equity = float(pnl_tracker.current_equity)

            fallback = compounding.compute_dynamic_risk(
                equity=equity,
                equity_peak=float(equity_peak),
                regime_persistence=float(REGIME_PERSISTENCE),
            )
            risk_pct = extract_risk_pct(dec, fallback=fallback)
            risk_amount = equity * float(risk_pct)

            move_ratio = (price - prev_price) / (price * STOP_DISTANCE_PCT)
            if move_ratio > MAX_R_MULTIPLIER:
                move_ratio = MAX_R_MULTIPLIER
            elif move_ratio < -MAX_R_MULTIPLIER:
                move_ratio = -MAX_R_MULTIPLIER

            realized_pnl = move_ratio * risk_amount

            pnl_tracker.record_trade(
                instrument=inst,
                realized_pnl=realized_pnl,
                unrealized_pnl=0.0,
            )
            trades += 1

            equity_now = float(pnl_tracker.current_equity)
            if equity_now > equity_peak:
                equity_peak = equity_now
                new_highs += 1

            dd = (equity_peak - equity_now) / equity_peak if equity_peak > 0 else 0.0
            if dd > max_drawdown:
                max_drawdown = dd

    ending_equity = float(pnl_tracker.current_equity)
    net_pnl = ending_equity - STARTING_EQUITY

    print("\nPortfolio Summary:")
    print("trades:", trades)
    print("net_pnl:", net_pnl)
    print("max_drawdown_pct:", round(max_drawdown * 100, 2))
    print("new_equity_highs:", new_highs)
    print("\nDone.")


if __name__ == "__main__":
    main()
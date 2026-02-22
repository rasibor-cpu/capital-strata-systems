"""
tools/run_replay_csv_governance_deciles.py

Governance-Resilient Strength Deciles
-------------------------------------
SignalEngine → minsig → ExecutionGate → sized 1-bar PnL

Goal:
- Measure whether signal strength hierarchy survives governance.
- This runner is a diagnostic harness; it is NOT live execution.

Key Fix (this version):
- Correctly interprets ExecutionGate decisions that use:
    decision.final == "ALLOW"  (instead of ok=True)
  and/or status strings like APPROVED/REJECTED.
- Only counts gate_blocks when trade is actually blocked.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import inspect
from pathlib import Path
from datetime import datetime, timezone
from statistics import mean
from typing import Any, Dict, List, Tuple
from collections import deque

from engine.strategy.signal_engine import SignalEngine
from engine.strategy.behaviour_mapper import get_profile_for_behaviour
from engine.execution.execution_gate import ExecutionGate


MA_WINDOW_DEFAULT = 20
PIP_SCALE_DEFAULT = 10000.0
STOP_DISTANCE_PCT_DEFAULT = 0.02
REGIME_PERSISTENCE_DEFAULT = 0.95
POLICY_DEFAULT = "core"


def _call_with_signature(fn: Any, kwargs: Dict[str, Any]) -> Any:
    sig = inspect.signature(fn)
    params = sig.parameters
    has_varkw = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values())
    if has_varkw:
        return fn(**kwargs)
    filtered = {k: v for k, v in kwargs.items() if k in params}
    return fn(**filtered)


def _gate_allows(decision_obj: Any) -> tuple[bool, str]:
    """
    Returns: (allowed, reason)

    Supports:
    - dict decisions (common in this repo)
    - dataclass-like objects with .ok/.status/.reason
    - dict with nested decision.final == "ALLOW"
    """
    # Object-style
    if hasattr(decision_obj, "ok"):
        ok = bool(getattr(decision_obj, "ok"))
        reason = str(getattr(decision_obj, "reason", ""))
        if ok:
            return True, reason or "ok"
        return False, reason or "blocked"

    # Dict-style
    if isinstance(decision_obj, dict):
        # 1) direct ok
        if "ok" in decision_obj:
            ok = bool(decision_obj.get("ok"))
            reason = str(decision_obj.get("reason", ""))
            return (ok, reason or ("ok" if ok else "blocked"))

        # 2) nested decision.final
        nested = decision_obj.get("decision")
        if isinstance(nested, dict):
            final = str(nested.get("final", "")).upper()
            if final in {"ALLOW", "APPROVE", "APPROVED", "OK"}:
                return True, str(decision_obj.get("reason", "approved"))
            if final in {"BLOCK", "REJECT", "REJECTED", "DENY"}:
                return False, str(decision_obj.get("reason", "blocked"))

        # 3) status-based
        status = str(decision_obj.get("status", "")).upper()
        if status in {"APPROVED", "ALLOW", "OK"}:
            return True, str(decision_obj.get("reason", "approved"))
        if status in {"REJECTED", "BLOCKED", "DENIED"}:
            return False, str(decision_obj.get("reason", "blocked"))

        # fall back
        return False, str(decision_obj.get("reason", "blocked"))

    # Unknown type: fail closed for diagnostics
    return False, "unknown_decision_type"


def compute_equal_population_deciles(strength_pnl: List[Tuple[float, float]]) -> List[Dict[str, Any]]:
    if not strength_pnl:
        return []

    strength_pnl = sorted(strength_pnl, key=lambda t: t[0])
    n = len(strength_pnl)
    bucket = max(1, n // 10)

    out: List[Dict[str, Any]] = []
    for i in range(10):
        start = i * bucket
        end = (i + 1) * bucket if i < 9 else n
        seg = strength_pnl[start:end]
        if not seg:
            continue

        strengths = [s for s, _ in seg]
        pnls = [p for _, p in seg]

        trades = len(seg)
        wins = sum(1 for p in pnls if p > 0)
        losses = trades - wins

        out.append({
            "decile": i + 1,
            "strength_min": round(min(strengths), 6),
            "strength_max": round(max(strengths), 6),
            "trades": trades,
            "wins": wins,
            "losses": losses,
            "win_rate": round(wins / trades, 4) if trades else 0.0,
            "avg_pnl_per_trade": round(mean(pnls), 8) if trades else 0.0,
            "total_pnl": round(sum(pnls), 8),
        })

    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--instrument", default="USD_GBP")
    ap.add_argument("--behaviour", default="C")
    ap.add_argument("--minsig", type=float, required=True)
    ap.add_argument("--ma_window", type=int, default=MA_WINDOW_DEFAULT)
    args = ap.parse_args()

    policy = os.getenv("CSS_GATE_POLICY", POLICY_DEFAULT)
    regime_persistence = float(os.getenv("CSS_GATE_REGIME_PERSISTENCE", REGIME_PERSISTENCE_DEFAULT))
    stop_distance_pct = float(os.getenv("CSS_STOP_DISTANCE_PCT", STOP_DISTANCE_PCT_DEFAULT))
    pip_scale = float(os.getenv("CSS_PIP_SCALE", PIP_SCALE_DEFAULT))

    profile = get_profile_for_behaviour(args.behaviour)
    signal_engine = SignalEngine(profile)
    gate = ExecutionGate()

    price_window = deque(maxlen=args.ma_window)
    prev_price = None

    total_signals = 0
    threshold_blocks = 0

    gate_blocks = 0
    gate_allow = 0
    gate_block_reasons: Dict[str, int] = {}

    starting_equity = 1000.0
    equity = starting_equity
    equity_peak = starting_equity

    trades = 0
    strength_pnl_records: List[Tuple[float, float]] = []

    csv_path = Path(args.csv)
    if not csv_path.exists():
        raise SystemExit(f"CSV not found: {csv_path}")

    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or "price" not in reader.fieldnames:
            raise SystemExit(f"CSV must include 'price' column. Found: {reader.fieldnames}")

        for row in reader:
            try:
                price = float(row["price"])
            except Exception:
                continue

            price_window.append(price)

            if prev_price is None:
                prev_price = price
                continue

            if len(price_window) < 2:
                prev_price = price
                continue

            moving_avg = sum(price_window) / float(len(price_window))

            signal = signal_engine.generate(
                instrument=args.instrument,
                price_now=price,
                price_prev=prev_price,
                moving_avg=moving_avg,
            )

            total_signals += 1

            if signal.direction == "FLAT" or signal.strength < args.minsig:
                threshold_blocks += 1
                prev_price = price
                continue

            side = "BUY" if signal.direction == "BUY" else "SELL"

            # IMPORTANT: gate expects keyword-only "notional" in this repo
            call_kwargs = {
                "instrument": args.instrument,
                "side": side,
                "notional": float(equity),
                "stop_distance_pct": float(stop_distance_pct),
                "equity": float(equity),
                "equity_peak": float(equity_peak),
                "regime_persistence": float(regime_persistence),
                "policy": str(policy),
                "strength": float(signal.strength),
            }

            try:
                gate_decision = _call_with_signature(gate.evaluate_trade, call_kwargs)
            except Exception as e:
                gate_blocks += 1
                gate_block_reasons[f"gate_call_failed: {e}"] = gate_block_reasons.get(f"gate_call_failed: {e}", 0) + 1
                prev_price = price
                continue

            allowed, reason = _gate_allows(gate_decision)

            if not allowed:
                gate_blocks += 1
                gate_block_reasons[str(reason)] = gate_block_reasons.get(str(reason), 0) + 1
                prev_price = price
                continue

            gate_allow += 1

            # 1-bar realized PnL (diagnostic expectancy)
            direction_sign = 1.0 if signal.direction == "BUY" else -1.0
            delta = price - prev_price
            realized_pnl = delta * direction_sign * pip_scale

            equity += realized_pnl
            if equity > equity_peak:
                equity_peak = equity

            trades += 1
            strength_pnl_records.append((float(signal.strength), float(realized_pnl)))

            prev_price = price

    net_pnl = equity - starting_equity
    deciles = compute_equal_population_deciles(strength_pnl_records)

    out_dir = Path("audit_logs") / "governance_deciles"
    out_dir.mkdir(parents=True, exist_ok=True)
    safe_minsig = str(args.minsig).replace(".", "_")
    out_path = out_dir / f"minsig_{safe_minsig}.json"

    summary = {
        "bars_ma_window": int(args.ma_window),
        "pip_scale": float(pip_scale),
        "stop_distance_pct": float(stop_distance_pct),
        "policy": str(policy),
        "regime_persistence": float(regime_persistence),
        "min_signal_strength": float(args.minsig),
        "behaviour": str(args.behaviour),
        "profile_name": getattr(profile, "name", "UNKNOWN"),
        "total_signals": int(total_signals),
        "threshold_blocks": int(threshold_blocks),
        "gate_allow": int(gate_allow),
        "gate_blocks": int(gate_blocks),
        "gate_block_reasons": gate_block_reasons,
        "trades": int(trades),
        "starting_equity": float(starting_equity),
        "ending_equity": float(equity),
        "net_pnl": float(net_pnl),
        "instrument": str(args.instrument),
        "decile_expectancy": deciles,
        "run_utc": datetime.now(timezone.utc).isoformat(),
    }

    out_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print("\n=== CSS GOVERNANCE DECILE EXPECTANCY (Equal-Population) ===")
    print(json.dumps(summary, indent=2))
    print(f"\nWrote: {out_path}\n")


if __name__ == "__main__":
    main()
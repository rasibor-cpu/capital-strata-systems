"""
Phase 1 Institutional Metrics Sweep
Capital Strata Systems

- Runs full 1Y M5 replay for all pairs
- Extracts institutional metrics from engine.summary()
- Produces structured JSON + console table

This is the real Phase 1 validation runner.
"""

from __future__ import annotations

import csv
import json
import sys
import io
import contextlib
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from engine.engine_loop import EngineLoop


STARTING_EQUITY = 100_000
BEHAVIOUR = "C"

DATA_DIR = REPO_ROOT / "data" / "history"
OUTPUT_DIR = REPO_ROOT / "audit_logs" / "phase1_metrics"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

PRICE_CANDIDATES = ["close", "price", "Close", "Price", "c"]


def detect_price_col(fieldnames: List[str]) -> str:
    for c in PRICE_CANDIDATES:
        if c in fieldnames:
            return c
    return fieldnames[-1]


def run_single_pair(csv_path: Path) -> Dict[str, Any]:

    instrument = csv_path.stem.replace("_M5_1year", "").replace("_", "")
    engine = EngineLoop(behaviour=BEHAVIOUR, starting_equity=STARTING_EQUITY)

    with open(csv_path, "r", newline="") as f:
        reader = csv.DictReader(f)
        price_col = detect_price_col(reader.fieldnames)

        with contextlib.redirect_stdout(io.StringIO()):
            for row in reader:
                price = float(row[price_col])
                engine.process_bar(instrument, price)

    s = engine.summary()

    ending_equity = s.get("ending_equity")
    net_pnl = s.get("net_pnl")
    trades = s.get("trades") or s.get("trade_count")
    gate_blocks = s.get("gate_blocks", 0)
    threshold_blocks = s.get("threshold_blocks", 0)
    regime_blocks = s.get("regime_flat_blocks", 0)
    total_signals = s.get("total_signals", 0)

    return_pct = (
        (ending_equity - STARTING_EQUITY) / STARTING_EQUITY * 100
        if ending_equity is not None else None
    )

    gate_block_ratio = (
        gate_blocks / total_signals if total_signals else None
    )

    return {
        "instrument": instrument,
        "ending_equity": ending_equity,
        "net_pnl": net_pnl,
        "return_pct": return_pct,
        "trades": trades,
        "gate_blocks": gate_blocks,
        "threshold_blocks": threshold_blocks,
        "regime_blocks": regime_blocks,
        "total_signals": total_signals,
        "gate_block_ratio": gate_block_ratio,
    }


def main():
    files = sorted(DATA_DIR.glob("*_M5_1year.csv"))
    results = []

    for file in files:
        print(f"Running {file.name} ...")
        results.append(run_single_pair(file))

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    out = OUTPUT_DIR / f"phase1_metrics_{ts}.json"

    with open(out, "w") as f:
        json.dump(results, f, indent=2)

    print("\n===== PHASE 1 INSTITUTIONAL METRICS =====\n")
    print(f"Saved: {out}\n")

    for r in results:
        print(
            f"{r['instrument']:>6} | "
            f"Return={r['return_pct']:>7.2f}% | "
            f"Trades={r['trades']:>5} | "
            f"GateBlocks={r['gate_blocks']:>5} | "
            f"GateRatio={r['gate_block_ratio']:.3f}"
        )


if __name__ == "__main__":
    main()
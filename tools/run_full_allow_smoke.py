"""
tools/run_full_allow_smoke.py

FULL ALLOW SMOKE + CSV REPLAY (Laptop-1)
----------------------------------------
Default behavior:
- Synthetic price path: trend -> reversal -> recovery (same as before)

Optional behavior:
- Replay from CSV via --csv path/to/file.csv
- CSV must contain at least one of:
    - column "price"
    - OR "close"
    - OR 2nd column numeric (fallback)

Goal:
- Provide a simple robustness harness that can run:
    - synthetic (quick smoke)
    - large real dataset (replay)
- Prints engine.summary() at the end.

Examples:
  # Synthetic (default)
  python tools/run_full_allow_smoke.py

  # Replay from CSV (full file)
  python tools/run_full_allow_smoke.py --csv data/eurusd_large.csv

  # Replay first 50k rows
  python tools/run_full_allow_smoke.py --csv data/eurusd_large.csv --max-rows 50000

  # Replay a window
  python tools/run_full_allow_smoke.py --csv data/eurusd_large.csv --start-row 200000 --max-rows 50000

  # Synthetic but different length
  python tools/run_full_allow_smoke.py --steps 20000
"""

from __future__ import annotations

import argparse
import csv
import math
import sys
from pathlib import Path
from typing import List, Optional


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from engine.engine_loop import EngineLoop


DEFAULT_INSTRUMENT = "EURUSD"
DEFAULT_STARTING_EQUITY = 100_000
DEFAULT_STEPS = 800


# ------------------------------------------------------------
# Synthetic path (legacy)
# ------------------------------------------------------------

def build_prices(steps: int) -> List[float]:
    base = 100.0
    out: List[float] = []
    for i in range(int(steps)):
        if i < steps * 0.35:
            drift = 0.020
        elif i < steps * 0.65:
            drift = -0.030
        else:
            drift = 0.015

        wave = 0.25 * math.sin(i / 7.0)
        micro = 0.05 * math.sin(i / 2.5)
        base += drift + wave + micro
        out.append(float(base))
    return out


# ------------------------------------------------------------
# CSV loading
# ------------------------------------------------------------

def _to_float(x: str) -> Optional[float]:
    try:
        v = float(str(x).strip())
        if v != v:  # NaN
            return None
        return v
    except Exception:
        return None


def load_prices_from_csv(
    csv_path: Path,
    start_row: int = 0,
    max_rows: Optional[int] = None,
) -> List[float]:
    """
    Reads prices from a CSV file. It tries:
    1) header column "price"
    2) header column "close"
    3) fallback: second column if numeric
    Skips non-numeric rows.
    start_row counts data rows (excluding header if present).
    """
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    prices: List[float] = []
    data_row_idx = -1  # increments only when we accept a data row candidate

    with csv_path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        first = next(reader, None)
        if first is None:
            return prices

        # Detect header
        header = [c.strip().lower() for c in first]
        has_header = any(h in ("timestamp", "time", "date", "price", "close", "open", "high", "low") for h in header)

        price_col_idx: Optional[int] = None
        close_col_idx: Optional[int] = None

        if has_header:
            if "price" in header:
                price_col_idx = header.index("price")
            if "close" in header:
                close_col_idx = header.index("close")

        def row_price(row: List[str]) -> Optional[float]:
            nonlocal price_col_idx, close_col_idx
            if not row:
                return None

            # If header known columns exist
            if has_header:
                if price_col_idx is not None and price_col_idx < len(row):
                    return _to_float(row[price_col_idx])
                if close_col_idx is not None and close_col_idx < len(row):
                    return _to_float(row[close_col_idx])

            # Fallback: try 2nd column
            if len(row) >= 2:
                v = _to_float(row[1])
                if v is not None:
                    return v

            # Last resort: try any column
            for c in row:
                v = _to_float(c)
                if v is not None:
                    return v
            return None

        # If first line was NOT header, treat it as data
        if not has_header:
            p = row_price(first)
            if p is not None:
                data_row_idx += 1
                if data_row_idx >= start_row:
                    prices.append(float(p))

        for row in reader:
            p = row_price(row)
            if p is None:
                continue

            data_row_idx += 1
            if data_row_idx < start_row:
                continue

            prices.append(float(p))

            if max_rows is not None and len(prices) >= int(max_rows):
                break

    return prices


# ------------------------------------------------------------
# CLI
# ------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", type=str, default="", help="Path to CSV file containing price/close series")
    ap.add_argument("--instrument", type=str, default=DEFAULT_INSTRUMENT, help="Instrument name (label only)")
    ap.add_argument("--starting-equity", type=float, default=float(DEFAULT_STARTING_EQUITY), help="Starting equity")
    ap.add_argument("--steps", type=int, default=int(DEFAULT_STEPS), help="Synthetic steps (used only if no --csv)")
    ap.add_argument("--start-row", type=int, default=0, help="Start row offset within CSV data rows")
    ap.add_argument("--max-rows", type=int, default=0, help="Max rows to load from CSV (0 = all)")
    ap.add_argument("--behaviour", type=str, default="D", help="Behaviour profile (A/B/C/D)")
    return ap.parse_args()


def main() -> None:
    args = parse_args()

    instrument = str(args.instrument).strip() or DEFAULT_INSTRUMENT
    starting_equity = float(args.starting_equity)
    behaviour = str(args.behaviour).strip() or "D"

    csv_path = str(args.csv).strip()
    use_csv = bool(csv_path)

    if use_csv:
        path = Path(csv_path)
        max_rows = None if int(args.max_rows) <= 0 else int(args.max_rows)
        prices = load_prices_from_csv(
            path,
            start_row=int(args.start_row),
            max_rows=max_rows,
        )
        steps = len(prices)
        source = f"CSV: {path}"
    else:
        steps = int(args.steps)
        prices = build_prices(steps)
        source = "SYNTHETIC"

    print("\n=== FULL ALLOW SMOKE TEST START ===")
    print(f"Repo root: {REPO_ROOT}")
    print(f"Source: {source}")
    print(f"Steps: {steps} | Instrument: {instrument}")
    print(f"Starting equity: {starting_equity}")
    print(f"Behaviour: {behaviour}")

    if len(prices) < 5:
        print("\n[ABORT] Not enough prices loaded to run.")
        print("=== END ===\n")
        return

    engine = EngineLoop(behaviour=behaviour, starting_equity=float(starting_equity))

    for p in prices:
        engine.process_bar(instrument, float(p))

    print("\n=== SUMMARY ===")
    print(engine.summary())
    print("=== END ===\n")


if __name__ == "__main__":
    main()
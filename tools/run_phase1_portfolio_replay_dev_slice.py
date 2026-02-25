"""
tools/run_phase1_portfolio_replay_dev_slice.py

Phase 1 Portfolio Replay – DEV SLICE MODE (NO V5 PATCHING)
----------------------------------------------------------
Fix in this version:
- When redirecting V5, set DATA_DIR/HISTORY_DIR variables as pathlib.Path
  (not string) so .glob() works.

Behavior:
- Reads CSV history files from: data/history/*_M5_1year.csv
- Writes sliced copies into:     data/history__devslice/<RUN_ID>/
- Imports and runs:              tools/run_phase1_portfolio_replay_v5_convexity_trim.py
- Redirects its data folder by setting recognized directory variables on the module.

Still no edits to V5.
"""

from __future__ import annotations

import argparse
import csv
import sys
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.replay._telemetry import ReplayTelemetry

HISTORY_SRC_DIR = REPO_ROOT / "data" / "history"
DEVSLICE_ROOT = REPO_ROOT / "data" / "history__devslice"
V5_MODULE_IMPORT = "tools.run_phase1_portfolio_replay_v5_convexity_trim"


def _parse_date(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    return datetime.fromisoformat(s)


def _parse_instruments(s: Optional[str]) -> Optional[List[str]]:
    if not s:
        return None
    out = [x.strip() for x in s.split(",") if x.strip()]
    return out or None


def _detect_time_column(headers: List[str]) -> str:
    candidates = ["time", "timestamp", "date", "datetime", "Date", "Datetime", "Time"]
    for c in candidates:
        if c in headers:
            return c
    return headers[0]


def _parse_dt(val: str) -> Optional[datetime]:
    val = val.strip()
    if not val:
        return None

    try:
        return datetime.fromisoformat(val.replace("Z", ""))
    except Exception:
        pass

    fmts = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y/%m/%d %H:%M:%S",
        "%Y/%m/%d %H:%M",
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M",
    ]
    for f in fmts:
        try:
            return datetime.strptime(val, f)
        except Exception:
            continue

    return None


def _slice_csv(
    src_path: Path,
    dst_path: Path,
    start: Optional[datetime],
    end: Optional[datetime],
    max_rows: Optional[int],
) -> Tuple[int, int]:
    scanned = 0
    written = 0

    with src_path.open("r", newline="", encoding="utf-8-sig") as f_in:
        reader = csv.DictReader(f_in)
        if reader.fieldnames is None:
            raise RuntimeError(f"CSV has no headers: {src_path.name}")

        time_col = _detect_time_column(reader.fieldnames)

        dst_path.parent.mkdir(parents=True, exist_ok=True)
        with dst_path.open("w", newline="", encoding="utf-8") as f_out:
            writer = csv.DictWriter(f_out, fieldnames=reader.fieldnames)
            writer.writeheader()

            for row in reader:
                scanned += 1
                dt = _parse_dt(row.get(time_col, "") or "")
                if dt is None:
                    continue

                if start and dt < start:
                    continue
                if end and dt >= end:
                    continue

                writer.writerow(row)
                written += 1

                if max_rows and written >= max_rows:
                    break

    return written, scanned


def _make_run_id(start: Optional[datetime], end: Optional[datetime]) -> str:
    s = start.date().isoformat() if start else "NONE"
    e = end.date().isoformat() if end else "NONE"
    return f"{s}__{e}"


def _list_history_files() -> List[Path]:
    return sorted(HISTORY_SRC_DIR.glob("*_M5_1year.csv"))


def _instrument_from_filename(p: Path) -> str:
    return p.name.replace("_M5_1year.csv", "")


def _write_manifest(dst_dir: Path, instruments: List[str], start: Optional[datetime], end: Optional[datetime], max_rows: Optional[int]) -> None:
    manifest = dst_dir / "DEVSLICE_MANIFEST.txt"
    with manifest.open("w", encoding="utf-8") as f:
        f.write("DEV SLICE MANIFEST\n")
        f.write(f"source_dir: {HISTORY_SRC_DIR}\n")
        f.write(f"slice_dir:  {dst_dir}\n")
        f.write(f"start: {start}\n")
        f.write(f"end:   {end}\n")
        f.write(f"max_rows_per_instrument: {max_rows}\n")
        f.write("instruments:\n")
        for inst in instruments:
            f.write(f"  - {inst}\n")


def _try_redirect_v5(module, dev_history_dir: Path) -> List[str]:
    """
    Set likely data-dir attributes if present.
    IMPORTANT: set as pathlib.Path (not str) so `.glob()` works.
    """
    set_keys = []
    candidates = [
        "DATA_DIR",
        "HISTORY_DIR",
        "HISTORY_PATH",
        "DATA_PATH",
        "HISTORY_FOLDER",
        "HISTORY_ROOT",
    ]
    for key in candidates:
        if hasattr(module, key):
            try:
                setattr(module, key, dev_history_dir)  # <-- Path, not string
                set_keys.append(key)
            except Exception:
                pass
    return set_keys


def parse_args():
    p = argparse.ArgumentParser(description="Phase 1 DEV slice replay runner (no V5 patching)")

    p.add_argument("--start", type=str, default=None, help="Start date YYYY-MM-DD")
    p.add_argument("--end", type=str, default=None, help="End date YYYY-MM-DD")
    p.add_argument("--max_rows", type=int, default=50000, help="Max rows per instrument to copy (default 50000)")
    p.add_argument("--instruments", type=str, default=None, help="Comma-separated instruments (e.g., EUR_USD,GBP_USD)")
    p.add_argument("--clean", action="store_true", help="Delete existing devslice folder for this run_id before writing")
    return p.parse_args()


def main():
    args = parse_args()

    start = _parse_date(args.start)
    end = _parse_date(args.end)
    instruments = _parse_instruments(args.instruments)

    all_files = _list_history_files()
    if not all_files:
        raise RuntimeError(f"No history files found at {HISTORY_SRC_DIR} matching *_M5_1year.csv")

    file_map: Dict[str, Path] = {_instrument_from_filename(p): p for p in all_files}

    if instruments is None:
        instruments = sorted(file_map.keys())

    missing = [i for i in instruments if i not in file_map]
    if missing:
        raise RuntimeError(
            "Missing instrument files for: " + ", ".join(missing) +
            f"\nExpected in {HISTORY_SRC_DIR} as <INSTRUMENT>_M5_1year.csv"
        )

    run_id = _make_run_id(start, end)
    dev_dir = DEVSLICE_ROOT / run_id

    if args.clean and dev_dir.exists():
        shutil.rmtree(dev_dir)

    dev_dir.mkdir(parents=True, exist_ok=True)
    _write_manifest(dev_dir, instruments, start, end, args.max_rows)

    print("==== DEV SLICE BUILDER ====")
    print(f"Source history dir: {HISTORY_SRC_DIR}")
    print(f"Slice output dir:   {dev_dir}")
    print(f"Start: {start}")
    print(f"End:   {end}")
    print(f"Max rows per instrument: {args.max_rows}")
    print(f"Instruments ({len(instruments)}): {instruments}")
    print("---------------------------")

    tel = ReplayTelemetry(label="DEVSLICE_COPY", total=len(instruments), print_every=1, unit="inst")

    written_total = 0
    for idx, inst in enumerate(instruments, start=1):
        src = file_map[inst]
        dst = dev_dir / src.name
        w, s = _slice_csv(src, dst, start, end, args.max_rows)
        written_total += w
        tel.tick(idx)
        print(f"[DEVSLICE_COPY] {inst}: wrote {w:,} rows (scanned {s:,}) -> {dst.name}")

    tel.done(processed=len(instruments))
    print(f"[DEVSLICE_COPY] Total rows written across instruments: {written_total:,}")
    print()

    print("==== DEV SLICE RUNNER ====")
    print(f"Importing V5 module: {V5_MODULE_IMPORT}")

    import importlib
    v5 = importlib.import_module(V5_MODULE_IMPORT)

    set_keys = _try_redirect_v5(v5, dev_dir)

    # Expose telemetry symbol for V5 if it chooses to use it
    setattr(v5, "ReplayTelemetry", ReplayTelemetry)

    print(f"Redirect attempt: set {set_keys if set_keys else 'NO KNOWN DIR ATTRIBUTES FOUND'}")
    print("Calling V5 main() ...")

    if not hasattr(v5, "main"):
        public = [k for k in dir(v5) if not k.startswith("_")]
        raise RuntimeError("V5 module has no main(). Public symbols:\n  " + "\n  ".join(public))

    v5.main()


if __name__ == "__main__":
    main()
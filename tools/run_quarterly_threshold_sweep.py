"""
tools/run_quarterly_threshold_sweep.py

Quarterly splitter + wrapper runner for:
  tools/run_replay_csv_threshold_sweep.py

Creates quarterly CSV slices from a canonical replay CSV and runs the sweep
at a fixed minsig threshold for each quarter.

Outputs:
  audit_logs/quarter_sweep/*.json  (produced by underlying runner)
  audit_logs/quarter_sweep/quarters_manifest.csv
"""

from __future__ import annotations

import subprocess
from pathlib import Path
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUNNER = PROJECT_ROOT / "tools" / "run_replay_csv_threshold_sweep.py"

DEFAULT_CSV = PROJECT_ROOT / "data" / "history" / "GBP_USD_M5_1year.csv"
OUT_DIR = PROJECT_ROOT / "audit_logs" / "quarter_sweep"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def run_cmd(cmd: list[str]) -> None:
    print("\n>>> " + " ".join(cmd))
    subprocess.run(cmd, check=True)


def main() -> None:
    csv_path = DEFAULT_CSV
    instrument = "GBP_USD"
    minsig = "0.80"

    if not csv_path.exists():
        raise FileNotFoundError(f"Missing CSV: {csv_path}")

    if not RUNNER.exists():
        raise FileNotFoundError(f"Missing runner: {RUNNER}")

    print(f"Loading: {csv_path}")
    df = pd.read_csv(csv_path)

    if "timestamp" not in df.columns or "price" not in df.columns:
        raise ValueError("CSV must have columns: timestamp,price")

    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    df = df.dropna(subset=["timestamp"]).sort_values("timestamp")

    # Build quarter label
    df["year"] = df["timestamp"].dt.year
    df["q"] = df["timestamp"].dt.quarter
    df["quarter"] = df["year"].astype(str) + "_Q" + df["q"].astype(str)

    quarters = df["quarter"].unique().tolist()
    print(f"Detected quarters: {quarters}")

    manifest_rows = []

    for q in quarters:
        qdf = df[df["quarter"] == q][["timestamp", "price"]].copy()
        if qdf.empty:
            continue

        out_csv = OUT_DIR / f"{instrument}_{q}_M5.csv"
        qdf.to_csv(out_csv, index=False)

        start_ts = qdf["timestamp"].iloc[0].isoformat()
        end_ts = qdf["timestamp"].iloc[-1].isoformat()
        rows = len(qdf)

        manifest_rows.append(
            {"quarter": q, "rows": rows, "start": start_ts, "end": end_ts, "csv": str(out_csv)}
        )

        # Run underlying sweep runner
        run_cmd(
            [
                "python",
                str(RUNNER),
                "--csv",
                str(out_csv),
                "--instrument",
                instrument,
                "--minsig",
                minsig,
            ]
        )

    manifest = pd.DataFrame(manifest_rows)
    manifest_path = OUT_DIR / "quarters_manifest.csv"
    manifest.to_csv(manifest_path, index=False)

    print("\nQuarter sweep complete.")
    print(f"Manifest: {manifest_path}")
    print(f"JSON outputs should be under: {OUT_DIR} and/or audit_logs/threshold_sweep")


if __name__ == "__main__":
    main()
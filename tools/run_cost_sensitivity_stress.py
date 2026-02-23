"""
tools/run_cost_sensitivity_stress.py

Cost Sensitivity Stress Test (SAFE)
-----------------------------------
Runs the existing threshold sweep runner repeatedly. Robustly finds the latest
valid minsig JSON output even when filenames vary between:
- minsig_0.8.json
- minsig_0_8.json

Also ignores zero-byte/tiny JSON artifacts.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from datetime import datetime, timezone
from typing import Dict, Any, List, Tuple


THRESH_SWEEP_SCRIPT = os.path.join("tools", "run_replay_csv_threshold_sweep.py")
OUT_DIR = os.path.join("audit_logs", "threshold_sweep")


def _candidate_prefixes(minsig: float) -> List[str]:
    # Normalize: 0.80 -> "0.8"
    s = f"{minsig:.10f}".rstrip("0").rstrip(".")
    dot = f"minsig_{s}"
    undersc = f"minsig_{s.replace('.', '_')}"
    # include both, de-duped
    return list(dict.fromkeys([dot, undersc]))


def _latest_valid_json(prefixes: List[str]) -> str:
    if not os.path.isdir(OUT_DIR):
        raise FileNotFoundError(f"Missing output dir: {OUT_DIR}")

    candidates: List[Tuple[float, str]] = []
    for fn in os.listdir(OUT_DIR):
        low = fn.lower()
        if not low.endswith(".json"):
            continue

        for p in prefixes:
            if fn.startswith(p):
                path = os.path.join(OUT_DIR, fn)
                try:
                    size = os.path.getsize(path)
                except OSError:
                    continue

                # Ignore zero-byte / tiny junk files
                if size <= 100:
                    continue

                candidates.append((os.path.getmtime(path), path))
                break

    if not candidates:
        # Helpful debug snapshot
        snapshot = sorted(os.listdir(OUT_DIR))
        raise FileNotFoundError(
            f"No valid JSON outputs found for prefixes {prefixes} in {OUT_DIR}. "
            f"Dir snapshot: {snapshot}"
        )

    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]


def _read_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _run_sweep(csv_path: str, minsig: float) -> Dict[str, Any]:
    cmd = ["python", THRESH_SWEEP_SCRIPT, "--csv", csv_path, "--minsig", str(minsig)]
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"Sweep failed:\n{p.stderr}")

    # Give filesystem time to flush
    time.sleep(0.25)

    prefixes = _candidate_prefixes(minsig)
    latest = _latest_valid_json(prefixes)
    data = _read_json(latest)

    # Attach provenance
    data["_source_json_path"] = os.path.normpath(latest)
    data["_sweep_stdout_tail"] = "\n".join(p.stdout.splitlines()[-10:])

    return data


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True, help="Replay CSV with columns timestamp,price")
    ap.add_argument("--minsig", type=float, default=0.80)
    args = ap.parse_args()

    # IMPORTANT NOTE:
    # This tool records "cost multipliers" as a sensitivity grid, but your underlying
    # sweep runner does not yet apply costs. If outputs are identical across multipliers,
    # that confirms cost modeling is not wired into replay yet.
    multipliers = [0.0, 0.5, 1.0, 1.5, 2.0, 3.0]

    if not os.path.isfile(THRESH_SWEEP_SCRIPT):
        raise FileNotFoundError(f"Missing sweep script: {THRESH_SWEEP_SCRIPT}")

    results: List[Dict[str, Any]] = []

    for m in multipliers:
        sweep = _run_sweep(args.csv, args.minsig)

        results.append({
            "cost_multiplier": m,
            "trades": sweep.get("trades"),
            "net_pnl": sweep.get("net_pnl"),
            "ending_equity": sweep.get("ending_equity"),
            "json_used": sweep.get("_source_json_path"),
        })

        print(f"Cost x{m}: trades={sweep.get('trades')} net_pnl={sweep.get('net_pnl')} ending_equity={sweep.get('ending_equity')}")

    report = {
        "tool": "run_cost_sensitivity_stress.py",
        "run_utc": datetime.now(timezone.utc).isoformat(),
        "csv": os.path.normpath(args.csv),
        "min_signal_strength": args.minsig,
        "note": "If results are identical across multipliers, underlying replay/sweep is not applying execution costs yet.",
        "results": results,
    }

    out_dir = os.path.join("audit_logs", "cost_sensitivity")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"cost_sensitivity_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json")

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print("Wrote:", out_path)


if __name__ == "__main__":
    main()
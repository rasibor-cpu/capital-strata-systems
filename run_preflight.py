"""
REA Trading Engine — Preflight (Governance Gate)
------------------------------------------------
One-command safety preflight that MUST pass before any live enable action.

Checks:
- Clean working tree
- Required tags exist
- Runs:
  - test_end_to_end_dryrun.py
  - run_paper_simulation.py
  - run_replay_from_csv.py sample_prices.csv

Hard-fails on any mismatch.

Run:
  python run_preflight.py
"""

import subprocess
import sys
from typing import List


REQUIRED_TAGS = [
    "LIVE_ADAPTERS_TWELVEDATA_OK",
    "SIGNAL_ENVELOPE_OK",
    "SIGNAL_ARBITRATION_OK",
    "REGIME_GATE_OK",
    "EXECUTION_GATE_OK",
    "DRY_RUN_OK",
    "PAPER_SIM_OK",
    "PAPER_SIM_RUNNER_OK",
    "METRICS_ROLLUP_OK",
    "REPLAY_CSV_OK",
    "LIVE_ENABLE_RUNBOOK_OK",
]


def run(cmd: List[str], *, title: str) -> None:
    print(f"\n=== {title} ===")
    print(" ".join(cmd))
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.stdout:
        print(r.stdout.strip())
    if r.returncode != 0:
        if r.stderr:
            print("\n[stderr]")
            print(r.stderr.strip())
        raise RuntimeError(f"FAILED: {title}")


def git_output(args: List[str]) -> str:
    r = subprocess.run(["git"] + args, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {r.stderr.strip()}")
    return r.stdout.strip()


def ensure_clean_tree() -> None:
    status = git_output(["status", "--porcelain"])
    if status.strip():
        print(status)
        raise RuntimeError("Working tree is not clean. Commit/stash changes before preflight.")


def ensure_tags_present() -> None:
    tags = set(git_output(["tag"]).splitlines())
    missing = [t for t in REQUIRED_TAGS if t not in tags]
    if missing:
        raise RuntimeError(f"Missing required tags: {missing}")


def ensure_sample_csv() -> None:
    # Create sample file if not present (safe overwrite OFF)
    import os
    if os.path.exists("sample_prices.csv"):
        return
    content = "\n".join(
        [
            "timestamp,price",
            "t1,1.1000",
            "t2,1.1010",
            "t3,1.1005",
            "t4,1.1020",
            "t5,1.1030",
            "t6,1.1022",
            "",
        ]
    )
    with open("sample_prices.csv", "w", encoding="utf-8") as f:
        f.write(content)


def main() -> int:
    try:
        print("=== REA PRE-FLIGHT: START ===")

        # 1) Clean working tree
        ensure_clean_tree()
        print("OK: working tree clean")

        # 2) Tags present
        ensure_tags_present()
        print("OK: required tags present")

        # 3) Ensure replay smoke file exists
        ensure_sample_csv()
        print("OK: sample_prices.csv present")

        # 4) Run scripts
        run([sys.executable, "test_end_to_end_dryrun.py"], title="DRY RUN (must show execution BLOCK)")
        run([sys.executable, "run_paper_simulation.py"], title="PAPER SIM (execution BLOCK, paper OK)")
        run([sys.executable, "run_replay_from_csv.py", "sample_prices.csv"], title="REPLAY CSV (paper-only)")

        print("\n=== REA PRE-FLIGHT: PASS ✅ ===")
        return 0

    except Exception as e:
        print(f"\n=== REA PRE-FLIGHT: FAIL ❌ ===\n{e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

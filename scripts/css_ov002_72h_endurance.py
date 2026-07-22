"""CLI: OV-002 controlled 72-hour endurance monitor (genuine wall-clock)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.certification.ov002_endurance_monitor import (
    TARGET_HOURS,
    initialize_run,
    run_monitor_loop,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="OV-002 72h endurance monitor")
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--target-hours", type=float, default=TARGET_HOURS)
    parser.add_argument(
        "--snapshot-interval-seconds",
        type=float,
        default=300.0,
        help="Wall-clock seconds between snapshots (default 300 = 5 minutes)",
    )
    parser.add_argument(
        "--init-only",
        action="store_true",
        help="Initialize package + safety assertions + first status; do not loop",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Take a single snapshot then exit (for tests)",
    )
    parser.add_argument(
        "--resume-dir",
        default=None,
        help="Resume monitor loop in an existing package directory",
    )
    args = parser.parse_args(argv)

    if args.resume_dir:
        result = run_monitor_loop(
            args.resume_dir,
            target_hours=float(args.target_hours),
            snapshot_interval_seconds=float(args.snapshot_interval_seconds),
            once=bool(args.once),
        )
        print(json.dumps(result, indent=2))
        return 0 if result.get("status") in {"RUNNING", "COMPLETE"} else 2

    init = initialize_run(output_dir=args.output_dir)
    print(json.dumps({"init": {k: v for k, v in init.items() if k != "meta"}}, indent=2))
    if not init.get("ok"):
        return 3
    if args.init_only:
        # Still take T+0 snapshot
        result = run_monitor_loop(
            init["package_dir"],
            target_hours=float(args.target_hours),
            snapshot_interval_seconds=float(args.snapshot_interval_seconds),
            once=True,
        )
        print(json.dumps(result, indent=2))
        return 0

    result = run_monitor_loop(
        init["package_dir"],
        target_hours=float(args.target_hours),
        snapshot_interval_seconds=float(args.snapshot_interval_seconds),
        once=bool(args.once),
    )
    print(json.dumps(result, indent=2))
    return 0 if result.get("status") in {"RUNNING", "COMPLETE"} else 2


if __name__ == "__main__":
    raise SystemExit(main())

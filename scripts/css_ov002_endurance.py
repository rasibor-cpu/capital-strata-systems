"""OV-002 endurance run CLI for this release line.

  start   --run-id ID --label "OV-002 ATTEMPT 3" [--target-hours 72] [--interim-hours 23]
  resume  --run-id ID      (after a monitor crash; a gap > LOST threshold invalidates)
  status  --run-id ID
  verify  --run-id ID      (hash chains + manifest)
  stop    --run-id ID      (operator stop: STOPPED_BEFORE_TARGET, never "complete")

Evidence goes to runtime/endurance/<run-id>/ (git-ignored, so it cannot dirty
the release tree). Nothing here certifies a run or changes trading state.
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from dashboard.runtime.endurance_evidence import pid_alive, read_json  # noqa: E402
from dashboard.runtime.endurance_monitor import (  # noqa: E402
    GOVERNED_TARGET_HOURS,
    EnduranceMonitor,
    EnduranceRefused,
    MonitorConfig,
    verify_evidence,
)


def _config(args: argparse.Namespace) -> MonitorConfig:
    return MonitorConfig(
        repo=REPO,
        evidence_dir=Path(args.evidence_root) / args.run_id,
        run_id=args.run_id,
        label=getattr(args, "label", None) or "",
        target_hours=getattr(args, "target_hours", GOVERNED_TARGET_HOURS),
        interim_checkpoint_hours=getattr(args, "interim_hours", 23.0),
        snapshot_seconds=getattr(args, "snapshot_seconds", 60.0),
        port=getattr(args, "port", 8765),
        max_restarts=getattr(args, "max_restarts", 3),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["start", "resume", "status", "verify", "stop"])
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--label")
    parser.add_argument("--evidence-root", default=str(REPO / "runtime" / "endurance"))
    parser.add_argument("--target-hours", type=float, default=GOVERNED_TARGET_HOURS)
    parser.add_argument("--interim-hours", type=float, default=23.0)
    parser.add_argument("--snapshot-seconds", type=float, default=60.0)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--max-restarts", type=int, default=3)
    args = parser.parse_args(argv)
    config = _config(args)
    evidence = config.evidence_dir

    if args.command == "start":
        if not args.label:
            parser.error("--label is required for start")
        monitor = EnduranceMonitor(config)
        try:
            meta = monitor.prepare()
        except EnduranceRefused as exc:
            print(f"REFUSED: {exc}", file=sys.stderr)
            return 2
        print(json.dumps({"label": meta["label"], "run_id": meta["run_id"], "head_sha": meta["release"]["head_sha"],
                          "branch": meta["release"]["branch"], "start_utc": meta["start_utc"],
                          "config_fingerprint": meta["configuration"]["fingerprint"],
                          "target_hours": meta["target_hours"], "evidence_dir": str(evidence)}, indent=2), flush=True)
        monitor.launch_supervisor()
        outcome = monitor.run_loop()
        print(f"OUTCOME: {outcome}")
        return 0
    if args.command == "resume":
        try:
            monitor = EnduranceMonitor.resume(config)
        except EnduranceRefused as exc:
            print(f"REFUSED: {exc}", file=sys.stderr)
            return 2
        if monitor.status.get("status") != "RUNNING":
            print(f"OUTCOME: {monitor.status.get('status')} {monitor.status.get('reasons')}")
            return 1
        print(f"OUTCOME: {monitor.run_loop()}")
        return 0
    if args.command == "status":
        status = read_json(evidence / "RUN_STATUS.json")
        print(json.dumps(status, indent=2))
        return 0
    if args.command == "verify":
        result = verify_evidence(evidence)
        print(json.dumps(result, indent=2))
        return 0 if result["ok"] else 1
    if args.command == "stop":
        status = read_json(evidence / "RUN_STATUS.json")
        pid = status.get("monitor_pid")
        if not pid or not pid_alive(pid):
            print("monitor is not running", file=sys.stderr)
            return 1
        os.kill(int(pid), signal.CTRL_BREAK_EVENT if os.name == "nt" else signal.SIGTERM)
        print(f"stop requested for monitor pid {pid}")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

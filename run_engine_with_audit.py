"""
REA Capital — Audited Runner (NO edits to engine_loop.py)

What it does:
- Writes an audit record when a session starts
- Launches the existing engine_loop.py as a subprocess
- Logs duration, exit code, and optional "action" metadata
- Writes append-only JSONL logs to ./audit_logs/access_audit.jsonl

Usage:
  python run_engine_with_audit.py
  python run_engine_with_audit.py --action replay --note "10m FX test"
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Dict, Optional


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


@dataclass
class AuditEvent:
    ts_utc: str
    event: str
    user: str
    host: str
    details: Dict[str, Any]


class AccessAuditLogger:
    """
    Append-only JSONL logger.
    One JSON record per line for auditability.
    """

    def __init__(self, log_path: str = "audit_logs/access_audit.jsonl", user: Optional[str] = None):
        self.log_path = log_path
        self.user = user or os.getenv("USERNAME") or os.getenv("USER") or "unknown"
        self.host = socket.gethostname()
        ensure_dir(os.path.dirname(self.log_path) or ".")

    def write(self, event: str, details: Optional[Dict[str, Any]] = None) -> None:
        rec = AuditEvent(
            ts_utc=utc_now_iso(),
            event=event,
            user=self.user,
            host=self.host,
            details=details or {},
        )
        line = json.dumps(asdict(rec), ensure_ascii=False)
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(line + "\n")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run engine_loop.py with audit logging (no edits).")
    p.add_argument("--action", default="run_engine", help="Label for what you’re doing (e.g., replay, live, test).")
    p.add_argument("--note", default="", help="Free-text note to describe the run.")
    p.add_argument("--engine", default="engine_loop.py", help="Engine entry script to run (default: engine_loop.py).")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    audit = AccessAuditLogger()

    engine_path = args.engine
    if not os.path.exists(engine_path):
        audit.write("session_error", {"reason": "engine_file_missing", "engine": engine_path})
        print(f"[ERROR] Cannot find {engine_path} in current folder.")
        return 2

    # Session start
    start_ts = time.time()
    audit.write(
        "session_start",
        {
            "component": "audited_runner",
            "engine": engine_path,
            "action": args.action,
            "note": args.note,
            "cwd": os.getcwd(),
        },
    )

    # Execute engine_loop.py without modifying it
    cmd = [sys.executable, engine_path]
    audit.write("engine_launch", {"cmd": cmd})

    try:
        proc = subprocess.run(cmd, text=True)
        exit_code = proc.returncode
    except Exception as e:
        audit.write("engine_exception", {"error": repr(e)})
        print(f"[ERROR] Engine crashed: {e}")
        return 1
    finally:
        elapsed_s = round(time.time() - start_ts, 2)
        audit.write("session_end", {"elapsed_seconds": elapsed_s})

    audit.write("engine_exit", {"exit_code": exit_code})
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
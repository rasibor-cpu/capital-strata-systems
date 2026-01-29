"""
REA Capital — Access Audit Logger (append-only)
- Records session starts, key actions, outcomes
- Writes JSONL (one JSON per line) for auditability
- Uses UTC timestamps
- Default path: ./audit_logs/access_audit.jsonl
"""

from __future__ import annotations

import json
import os
import socket
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
    Append-only audit logger.
    Writes one JSON object per line (JSONL).
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
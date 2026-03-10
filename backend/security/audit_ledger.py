from __future__ import annotations

import json
import time
from pathlib import Path
from dataclasses import dataclass, asdict


@dataclass
class AuditEvent:
    timestamp: float
    event_type: str
    user_id: str
    details: dict


class AuditLedger:
    """
    CSS Institutional Audit Ledger
    Records all critical system actions
    """

    def __init__(self):

        root = Path(__file__).resolve().parents[2]

        self.audit_dir = root / "audit_logs"
        self.audit_dir.mkdir(exist_ok=True)

        self.audit_file = self.audit_dir / "css_audit_log.jsonl"

    # -----------------------------------------------------

    def record(self, event_type: str, user_id: str, details: dict):

        event = AuditEvent(
            timestamp=time.time(),
            event_type=event_type,
            user_id=user_id,
            details=details,
        )

        with open(self.audit_file, "a") as f:
            f.write(json.dumps(asdict(event)) + "\n")

    # -----------------------------------------------------

    def read_recent(self, limit: int = 10):

        if not self.audit_file.exists():
            return []

        lines = self.audit_file.read_text().splitlines()

        return [json.loads(x) for x in lines[-limit:]]
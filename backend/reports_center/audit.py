"""Unified report audit history (privacy-safe)."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.reports_center.constants import AUDIT_SCHEMA, DEFAULT_AUDIT_RELATIVE, SAFETY_LOCKS


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class ReportAuditLog:
    def __init__(self, root: Path | str | None = None) -> None:
        self.root = Path(root) if root else Path.cwd() / DEFAULT_AUDIT_RELATIVE
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "report_audit.jsonl"

    def record(
        self,
        *,
        action: str,
        outcome: str,
        actor_id: str,
        actor_role: str,
        permission_used: str = "",
        report_id: str = "",
        report_type: str = "",
        report_version: str = "",
        report_hash: str = "",
        failure_reason: str = "",
        destination_class: str = "",
        official: bool | None = None,
        advisory_only: bool = True,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        event = {
            "schema_version": AUDIT_SCHEMA,
            "event_id": f"rae_{uuid.uuid4().hex[:16]}",
            "report_id": report_id,
            "report_type": report_type,
            "report_version": report_version,
            "actor_id": actor_id,
            "actor_role": actor_role,
            "permission_used": permission_used,
            "timestamp_utc": _utc_now(),
            "action": action,
            "outcome": outcome,
            "failure_reason": failure_reason,
            "destination_class": destination_class,
            "report_hash": report_hash,
            "advisory_only": advisory_only,
            "official_report": official,
            **SAFETY_LOCKS,
        }
        if extra:
            # Strip secrets / emails
            safe_extra = {
                k: v
                for k, v in extra.items()
                if not any(tok in str(k).lower() for tok in ("secret", "token", "password", "email", "recipient"))
            }
            event["extra"] = safe_extra
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, sort_keys=True, default=str) + "\n")
        return event

    def list_events(
        self,
        *,
        report_id: str | None = None,
        action: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        if not self.path.is_file():
            return []
        rows: list[dict[str, Any]] = []
        with self.path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                if report_id and obj.get("report_id") != report_id:
                    continue
                if action and obj.get("action") != action:
                    continue
                rows.append(obj)
        return rows[-limit:]

"""
System Audit Log
----------------
Authoritative append-only audit trail for:
- logins / logouts
- screen access
- actions performed
- unauthorized access attempts
- supervisor alerts (flag-only in v1)

Design goals:
- append-only (no deletes, no updates)
- explicit event typing
- forensic friendly
"""

from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List
import json
import threading
import uuid
import os


# ─────────────────────────────────────────────
# Audit Event Types
# ─────────────────────────────────────────────
class AuditEventType(str, Enum):
    LOGIN = "LOGIN"
    LOGOUT = "LOGOUT"
    SCREEN_VIEW = "SCREEN_VIEW"
    ACTION = "ACTION"
    ACCESS_DENIED = "ACCESS_DENIED"
SECURITY = "SECURITY"
SYSTEM = "SYSTEM"


# ─────────────────────────────────────────────
# Audit Record
# ─────────────────────────────────────────────
@dataclass(frozen=True)
class AuditEvent:
    event_id: str
    timestamp_utc: str
    event_type: AuditEventType

    user_id: Optional[str]
    role: Optional[str]
    session_id: Optional[str]

    screen: Optional[str]
    action: Optional[str]
    resource: Optional[str]

    success: bool
    reason: Optional[str]

    ip_address: Optional[str]
    device: Optional[str]

    meta: Dict[str, Any]


# ─────────────────────────────────────────────
# Audit Log (append-only)
# ─────────────────────────────────────────────
class AuditLogger:
    """
    Thread-safe append-only audit logger.
    """

    def __init__(self, log_dir: str = "engine/security/logs"):
        self.log_dir = log_dir
        self._lock = threading.Lock()
        os.makedirs(self.log_dir, exist_ok=True)

    def log(
        self,
        *,
        event_type: AuditEventType,
        user_id: Optional[str],
        role: Optional[str],
        session_id: Optional[str],
        screen: Optional[str] = None,
        action: Optional[str] = None,
        resource: Optional[str] = None,
        success: bool = True,
        reason: Optional[str] = None,
        ip_address: Optional[str] = None,
        device: Optional[str] = None,
        meta: Optional[Dict[str, Any]] = None,
    ) -> AuditEvent:
        """
        Write a single audit event.
        """

        evt = AuditEvent(
            event_id=str(uuid.uuid4()),
            timestamp_utc=datetime.utcnow().isoformat(),
            event_type=event_type,
            user_id=user_id,
            role=role,
            session_id=session_id,
            screen=screen,
            action=action,
            resource=resource,
            success=success,
            reason=reason,
            ip_address=ip_address,
            device=device,
            meta=meta or {},
        )

        self._append(evt)
        return evt

    def _append(self, evt: AuditEvent) -> None:
        """
        Append event to daily log file.
        """
        day = evt.timestamp_utc[:10]  # YYYY-MM-DD
        path = os.path.join(self.log_dir, f"audit_{day}.jsonl")

        with self._lock:
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(evt), default=str))
                f.write("\n")


# ─────────────────────────────────────────────
# Convenience helpers
# ─────────────────────────────────────────────
def log_login(audit: AuditLogger, **kwargs):
    return audit.log(event_type=AuditEventType.LOGIN, **kwargs)


def log_logout(audit: AuditLogger, **kwargs):
    return audit.log(event_type=AuditEventType.LOGOUT, **kwargs)


def log_screen(audit: AuditLogger, **kwargs):
    return audit.log(event_type=AuditEventType.SCREEN_VIEW, **kwargs)


def log_action(audit: AuditLogger, **kwargs):
    return audit.log(event_type=AuditEventType.ACTION, **kwargs)


def log_access_denied(audit: AuditLogger, **kwargs):
    return audit.log(
        event_type=AuditEventType.ACCESS_DENIED,
        success=False,
        **kwargs,
    )
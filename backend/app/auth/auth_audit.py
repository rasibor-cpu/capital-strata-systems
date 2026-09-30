"""Authentication / account-lifecycle audit trail.

Reuses the same append-only, hash-chained ``CommercialAuditLog`` primitive
the commercial governance API already uses -- one audit architecture, not a
parallel, uncontrolled logging subsystem -- pointed at its own database so
authentication events are captured in every deployment, independent of
whether commercial-collections governance (``CSS_COMMERCIAL_DB``) happens to
be configured. Unlike that governance database, this one is on by default
(with a sensible path under ``data/``) since login/logout/lockout auditing is
baseline security hygiene, not an opt-in commercial capability.

Never pass a password, password hash, bearer/session/CSRF token, or cookie
value into any event recorded here.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_AUTH_AUDIT_DB = _PROJECT_ROOT / "data" / "css_auth_audit.sqlite3"

LOGIN_SUCCESS = "LOGIN_SUCCESS"
LOGIN_FAILURE = "LOGIN_FAILURE"
ACCOUNT_LOCKOUT = "ACCOUNT_LOCKOUT"
LOGOUT = "LOGOUT"
PASSWORD_CHANGE = "PASSWORD_CHANGE"
SESSION_REVOKED = "SESSION_REVOKED"
SESSION_REVOKE_ALL = "SESSION_REVOKE_ALL"
ACCOUNT_DISABLED = "ACCOUNT_DISABLED"
ACCOUNT_ENABLED = "ACCOUNT_ENABLED"
AUTHORIZATION_DENIED = "AUTHORIZATION_DENIED"


def auth_audit_db_path(env: Optional[Dict[str, str]] = None) -> str:
    configured = (env if env is not None else os.environ).get("CSS_AUTH_AUDIT_DB", "").strip()
    return configured or str(DEFAULT_AUTH_AUDIT_DB)


def log_auth_event(
    event_type: str,
    *,
    actor_id: Optional[str] = None,
    actor_role: Optional[str] = None,
    outcome: str = "SUCCEEDED",
    reason: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> None:
    """Append one authentication/account-lifecycle event. Never raises.

    Audit logging is observability, not a gate: a logging failure (disk full,
    locked file) must never block or fail the authentication action it
    describes, so every error here is swallowed after being attempted.
    """
    try:
        from engine.commercial.commercial_audit import CommercialAuditLog

        db_path = auth_audit_db_path()
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        CommercialAuditLog(db_path).append(
            action=event_type,
            object_type="operator_auth",
            outcome=outcome,
            actor_id=actor_id,
            actor_role=actor_role,
            reason=reason,
            details=details,
        )
    except Exception:
        pass

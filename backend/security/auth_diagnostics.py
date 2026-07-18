"""Privacy-safe authorization diagnostics (Phase 176D)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("css.auth.diagnostics")


def log_authorization_denial(
    *,
    route: str,
    auth: Any,
    permission_requested: str,
    denial_reason: str,
) -> None:
    """Log a denial without tokens, credentials, or full session payloads."""
    user_id = getattr(auth, "user_id", None) or (auth.get("user_id") if isinstance(auth, dict) else "")
    role = getattr(auth, "role", None) or (auth.get("role") if isinstance(auth, dict) else "")
    correlation_id = getattr(auth, "correlation_id", None) or (
        auth.get("correlation_id") if isinstance(auth, dict) else ""
    )
    identity_source = getattr(auth, "identity_source", None) or (
        auth.get("identity_source") if isinstance(auth, dict) else ""
    )
    permission_source = getattr(auth, "permission_source", None) or (
        auth.get("permission_source") if isinstance(auth, dict) else ""
    )
    issued = getattr(auth, "issued_at_utc", None) or (auth.get("issued_at_utc") if isinstance(auth, dict) else "")
    logger.info(
        "auth_denied correlation_id=%s route=%s user_id=%s role=%s permission=%s "
        "identity_source=%s permission_source=%s denial_reason=%s session_issued=%s ts=%s",
        correlation_id,
        route,
        user_id or "-",
        role or "-",
        permission_requested,
        identity_source or "-",
        permission_source or "-",
        denial_reason,
        issued or "-",
        datetime.now(timezone.utc).isoformat(),
    )

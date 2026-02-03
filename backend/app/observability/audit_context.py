"""
backend/app/observability/audit_context.py

Holds the authenticated audit context for the current engine run.
Fail-closed: accessing before set raises.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import time

@dataclass(frozen=True)
class AuditContext:
    user_id: str
    role: str
    home_branch: str
    current_branch: str
    engine_run_id: str
    issued_at_utc: float


_AUDIT_CTX: Optional[AuditContext] = None


def set_audit_context(ctx: AuditContext) -> None:
    global _AUDIT_CTX
    _AUDIT_CTX = ctx


def get_audit_context() -> AuditContext:
    if _AUDIT_CTX is None:
        raise RuntimeError("AUDIT_CONTEXT_NOT_INITIALIZED")
    return _AUDIT_CTX


def audit_fields() -> dict:
    """
    Convenience helper for logging / records.
    """
    ctx = get_audit_context()
    return {
        "user_id": ctx.user_id,
        "role": ctx.role,
        "home_branch": ctx.home_branch,
        "current_branch": ctx.current_branch,
        "engine_run_id": ctx.engine_run_id,
        "audit_issued_at_utc": ctx.issued_at_utc,
    }


# backend/app/observability/audit_context.py
"""
Audit context for REA Capital Trading Engine.

Goal:
- Provide a single, reliable place to bind request/run identity into contextvars
- Make it easy to attach audit-safe metadata to logs and downstream actions

This module is intentionally lightweight and dependency-free.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
import contextvars
from typing import Any, Dict, Optional


# -----------------------------
# Data models
# -----------------------------

@dataclass(frozen=True)
class AuditUser:
    user_id: int
    role: str
    unit_code: str
    branch: str


# -----------------------------
# Context variables
# -----------------------------

_ENGINE_RUN_ID: contextvars.ContextVar[str] = contextvars.ContextVar("engine_run_id", default="N/A")
_TRACE_ID: contextvars.ContextVar[str] = contextvars.ContextVar("trace_id", default="N/A")
_AUDIT_USER: contextvars.ContextVar[Optional[AuditUser]] = contextvars.ContextVar("audit_user", default=None)


# -----------------------------
# Engine / trace binding
# -----------------------------

def set_engine_run_id(engine_run_id: str) -> None:
    _ENGINE_RUN_ID.set(str(engine_run_id))


def get_engine_run_id() -> str:
    return _ENGINE_RUN_ID.get()


def set_trace_id(trace_id: str) -> None:
    _TRACE_ID.set(str(trace_id))


def get_trace_id() -> str:
    return _TRACE_ID.get()


def init_audit_context(engine_run_id: str, trace_id: str) -> None:
    """
    Convenience initializer used by startup wrappers.
    """
    set_engine_run_id(engine_run_id)
    set_trace_id(trace_id)


# -----------------------------
# User binding (THIS WAS MISSING)
# -----------------------------

def set_audit_user(user_id: int, role: str, unit_code: str, branch: str) -> None:
    """
    Bind the authenticated user to the audit context.
    This MUST be called after authentication succeeds and before any privileged actions.
    """
    _AUDIT_USER.set(AuditUser(user_id=int(user_id), role=str(role), unit_code=str(unit_code), branch=str(branch)))


def clear_audit_user() -> None:
    _AUDIT_USER.set(None)


def get_audit_user() -> Optional[AuditUser]:
    return _AUDIT_USER.get()


# -----------------------------
# Log extras / helpers
# -----------------------------

def audit_extras() -> Dict[str, Any]:
    """
    Stable dict for logger 'extra=' fields.
    Keep keys flat and audit-safe.
    """
    user = get_audit_user()
    base: Dict[str, Any] = {
        "engine_run_id": get_engine_run_id(),
        "trace_id": get_trace_id(),
    }
    if user is None:
        base.update(
            {
                "user_id": "N/A",
                "role": "N/A",
                "unit_code": "N/A",
                "branch": "N/A",
            }
        )
        return base

    d = asdict(user)
    base.update(
        {
            "user_id": d["user_id"],
            "role": d["role"],
            "unit_code": d["unit_code"],
            "branch": d["branch"],
        }
    )
    return base


def require_audit_user() -> AuditUser:
    user = get_audit_user()
    if user is None:
        raise RuntimeError("AUDIT_USER_NOT_BOUND")
    return user

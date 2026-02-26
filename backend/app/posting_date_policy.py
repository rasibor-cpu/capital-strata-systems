"""
posting_date_policy.py
----------------------
Posting Date Governance Policy (Bank-Grade Controls)

Responsibilities:
- Validate posting_date format (ISO 8601 date or datetime string)
- Enforce allowable posting window:
    - No future dating beyond FUTURE_DAYS_ALLOWED
    - No backdating beyond BACKDATE_DAYS_ALLOWED unless override is logged
- Enforce Period Close gate (closed/locked periods always reject)
- Provide structured decision output for UI + audit

This module does NOT mutate ledgers. It is a control gate only.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone, date
from typing import Any, Dict, Optional, Tuple

from backend.app.period_close import is_posting_allowed, next_open_period
from backend.app.override_log import write_override


# -----------------------------
# Policy Parameters (tunable)
# -----------------------------

BACKDATE_DAYS_ALLOWED = 0          # 0 means "no backdating" unless override
FUTURE_DAYS_ALLOWED = 0           # 0 means "no future dating" unless override
ALLOW_SAME_DAY_ONLY = True        # True => posting_date must be today unless override


@dataclass(frozen=True)
class PostingDateDecision:
    allowed: bool
    reason: str
    posting_date_iso: Optional[str] = None
    requires_override: bool = False
    required_override_type: Optional[str] = None
    next_open_period_iso: Optional[str] = None
    override_record: Optional[Dict[str, Any]] = None


def _parse_iso_date(s: str) -> Optional[date]:
    s = (s or "").strip()
    if not s:
        return None
    try:
        # Accept "YYYY-MM-DD" OR full iso datetime; take date portion.
        d = datetime.fromisoformat(s.replace("Z", "+00:00")).date()
        return d
    except Exception:
        return None


def _today_utc() -> date:
    return datetime.now(timezone.utc).date()


def evaluate_posting_date(
    *,
    posting_date: str,
    actor_user_id: str,
    override: Optional[Dict[str, Any]] = None,
    scope: Optional[Dict[str, Any]] = None,
) -> PostingDateDecision:
    """
    Enforces posting date policy + period close.

    If override required and provided, writes immutable override record (fail-closed).
    """
    actor_user_id = (actor_user_id or "").strip() or "unknown_actor"
    override = override or {}
    scope = scope or {}

    d = _parse_iso_date(posting_date)
    if d is None:
        return PostingDateDecision(
            allowed=False,
            reason="Invalid posting_date format (expected ISO date or datetime).",
            posting_date_iso=None,
            next_open_period_iso=None,
        )

    posting_date_iso = d.isoformat()

    # Period close gate (hard gate)
    if not is_posting_allowed(posting_date_iso):
        return PostingDateDecision(
            allowed=False,
            reason="Posting date falls in a CLOSED/LOCKED period.",
            posting_date_iso=posting_date_iso,
            requires_override=False,  # closed/locked must NOT be overridable here
            next_open_period_iso=next_open_period(posting_date_iso),
        )

    today = _today_utc()
    delta_days = (d - today).days  # future positive, backdate negative

    # Strict same-day if configured
    if ALLOW_SAME_DAY_ONLY and delta_days != 0:
        required_type = "POSTING_DATE_OUTSIDE_TODAY"
        if not override:
            return PostingDateDecision(
                allowed=False,
                reason="Posting date must be today unless an authorized override is provided.",
                posting_date_iso=posting_date_iso,
                requires_override=True,
                required_override_type=required_type,
            )
        # override provided => log it
        rec = write_override(
            actor_user_id=actor_user_id,
            override_type=required_type,
            reason=str(override.get("reason", "")).strip() or "Override: posting date outside today",
            scope={**scope, "posting_date": posting_date_iso, "today_utc": today.isoformat(), "delta_days": delta_days},
            approval_level=str(override.get("approval_level", "CHECKER")).strip() or "CHECKER",
            override_id=override.get("override_id"),
        )
        return PostingDateDecision(
            allowed=True,
            reason="Allowed with override (posting date outside today).",
            posting_date_iso=posting_date_iso,
            override_record=rec,
        )

    # If not strict same-day, enforce windows
    if delta_days < -BACKDATE_DAYS_ALLOWED:
        required_type = "BACKDATE"
        if not override:
            return PostingDateDecision(
                allowed=False,
                reason=f"Backdating beyond {BACKDATE_DAYS_ALLOWED} day(s) requires override.",
                posting_date_iso=posting_date_iso,
                requires_override=True,
                required_override_type=required_type,
            )
        rec = write_override(
            actor_user_id=actor_user_id,
            override_type=required_type,
            reason=str(override.get("reason", "")).strip() or "Override: backdate beyond policy window",
            scope={**scope, "posting_date": posting_date_iso, "today_utc": today.isoformat(), "delta_days": delta_days},
            approval_level=str(override.get("approval_level", "CHECKER")).strip() or "CHECKER",
            override_id=override.get("override_id"),
        )
        return PostingDateDecision(
            allowed=True,
            reason="Allowed with override (backdate).",
            posting_date_iso=posting_date_iso,
            override_record=rec,
        )

    if delta_days > FUTURE_DAYS_ALLOWED:
        required_type = "FUTURE_DATE"
        if not override:
            return PostingDateDecision(
                allowed=False,
                reason=f"Future-dating beyond {FUTURE_DAYS_ALLOWED} day(s) requires override.",
                posting_date_iso=posting_date_iso,
                requires_override=True,
                required_override_type=required_type,
            )
        rec = write_override(
            actor_user_id=actor_user_id,
            override_type=required_type,
            reason=str(override.get("reason", "")).strip() or "Override: future-date beyond policy window",
            scope={**scope, "posting_date": posting_date_iso, "today_utc": today.isoformat(), "delta_days": delta_days},
            approval_level=str(override.get("approval_level", "CHECKER")).strip() or "CHECKER",
            override_id=override.get("override_id"),
        )
        return PostingDateDecision(
            allowed=True,
            reason="Allowed with override (future-date).",
            posting_date_iso=posting_date_iso,
            override_record=rec,
        )

    return PostingDateDecision(
        allowed=True,
        reason="Posting date allowed (within policy).",
        posting_date_iso=posting_date_iso,
    )
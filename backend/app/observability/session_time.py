"""
Time & Session Integrity
REA Capital Trading Engine

Purpose:
- Conservative market/session gating (fail-closed)
- Weekend lock
- Market-hours lock (basic, UTC-based defaults)
- Clock sanity checks to detect skew / mis-set clocks

This module is intentionally minimal and independent.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from backend.app.observability.logger import get_logger, with_trace

log = get_logger("observability.session_time")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class SessionDecision:
    allowed: bool
    state: str
    reason: str
    now_utc: datetime


def clock_sanity_check(now_utc: Optional[datetime] = None) -> Tuple[bool, str]:
    """
    Basic sanity guard:
    - Detect absurd dates far in the past/future (often indicates clock mis-set).
    - Does NOT call external time sources (offline-safe).

    Returns: (ok, reason)
    """
    now = now_utc or _utc_now()

    # Conservative bounds: if your clock is outside these, something is off.
    earliest = datetime(2020, 1, 1, tzinfo=timezone.utc)
    latest = datetime(2035, 1, 1, tzinfo=timezone.utc)

    if now < earliest:
        return False, "clock_too_old"
    if now > latest:
        return False, "clock_too_future"
    return True, "clock_ok"


def is_weekend_utc(now_utc: Optional[datetime] = None) -> bool:
    now = now_utc or _utc_now()
    # Monday=0 ... Sunday=6
    return now.weekday() >= 5


def in_utc_window(
    now_utc: datetime,
    start_hhmm: str,
    end_hhmm: str,
) -> bool:
    """
    Check if now_utc time is within a UTC time window [start, end).
    Supports windows that do not cross midnight.
    """
    sh, sm = (int(x) for x in start_hhmm.split(":"))
    eh, em = (int(x) for x in end_hhmm.split(":"))

    start = now_utc.replace(hour=sh, minute=sm, second=0, microsecond=0)
    end = now_utc.replace(hour=eh, minute=em, second=0, microsecond=0)

    return start <= now_utc < end


def default_fx_session_allowed(now_utc: Optional[datetime] = None) -> SessionDecision:
    """
    Conservative FX session rule (UTC-based):
    - Disallow weekends entirely (Sat/Sun UTC)
    - Allow only within a safe default window on weekdays

    NOTE: FX is often 24/5, but we choose a conservative window to reduce edge risks
    until full market-hours module is finalized.

    Default window: 01:00–22:00 UTC (weekday)
    """
    now = now_utc or _utc_now()

    ok_clock, clock_reason = clock_sanity_check(now)
    if not ok_clock:
        return SessionDecision(False, "UNKNOWN", clock_reason, now)

    if is_weekend_utc(now):
        return SessionDecision(False, "CLOSED_WEEKEND", "weekend_lock", now)

    if in_utc_window(now, "01:00", "22:00"):
        return SessionDecision(True, "OPEN", "weekday_in_window", now)

    return SessionDecision(False, "CLOSED_HOURS", "weekday_outside_window", now)


def default_crypto_session_allowed(now_utc: Optional[datetime] = None) -> SessionDecision:
    """
    Crypto is 24/7, but still apply clock sanity checks.
    """
    now = now_utc or _utc_now()

    ok_clock, clock_reason = clock_sanity_check(now)
    if not ok_clock:
        return SessionDecision(False, "UNKNOWN", clock_reason, now)

    return SessionDecision(True, "OPEN", "crypto_24_7", now)


def assert_session_allowed(
    asset_class: str,
    now_utc: Optional[datetime] = None,
    hard_fail: bool = True,
) -> SessionDecision:
    """
    Central gating entry point.

    asset_class examples: "fx", "crypto", "equities", "options"
    Currently:
      - fx => conservative weekday window + weekend lock
      - crypto => open 24/7 (clock sanity still enforced)
      - everything else => fail-closed (until explicitly added)

    If hard_fail=True, it logs WARNING and returns allowed=False.
    (We avoid raising exceptions to keep this independent & non-invasive.)
    """
    now = now_utc or _utc_now()
    cls = (asset_class or "").strip().lower()

    if cls == "fx":
        decision = default_fx_session_allowed(now)
    elif cls == "crypto":
        decision = default_crypto_session_allowed(now)
    else:
        ok_clock, clock_reason = clock_sanity_check(now)
        if not ok_clock:
            decision = SessionDecision(False, "UNKNOWN", clock_reason, now)
        else:
            decision = SessionDecision(False, "CLOSED", f"asset_class_not_whitelisted:{cls}", now)

    adapter = with_trace(log, "SESSION")
    if decision.allowed:
        adapter.info("SESSION_ALLOW | asset_class=%s | state=%s | reason=%s | now_utc=%s",
                     cls, decision.state, decision.reason, decision.now_utc.isoformat())
    else:
        level_fn = adapter.warning if hard_fail else adapter.info
        level_fn("SESSION_BLOCK | asset_class=%s | state=%s | reason=%s | now_utc=%s",
                 cls, decision.state, decision.reason, decision.now_utc.isoformat())

    return decision

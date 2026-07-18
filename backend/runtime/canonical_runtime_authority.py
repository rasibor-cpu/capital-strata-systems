from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

# Statuses written by the real launcher's CSSRuntimeSupervisor that indicate
# a genuinely live, heartbeating canonical runtime.
HEALTHY_STATUSES = {"RUNNING"}

# Statuses that indicate the canonical writer itself reported it is not
# running (a truthful shutdown, not a masking value).
STOPPED_STATUSES = {"STOPPED", "FAILED"}

AUTHORITY_ONLINE = "ONLINE"
AUTHORITY_STOPPED = "STOPPED"
AUTHORITY_MISSING = "MISSING"
AUTHORITY_MALFORMED = "MALFORMED"
AUTHORITY_STALE = "STALE"
AUTHORITY_ORPHANED_RUNTIME = "ORPHANED_RUNTIME"


def _parse_iso(value: Any) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _is_fresh(state: Mapping[str, Any] | None, *, now: datetime, stale_after_seconds: float) -> bool:
    if not isinstance(state, Mapping):
        return False
    status = str(state.get("status") or "").upper()
    if status not in HEALTHY_STATUSES:
        return False
    heartbeat = _parse_iso(state.get("last_heartbeat_at") or state.get("last_heartbeat"))
    if heartbeat is None:
        return False
    return (now - heartbeat).total_seconds() <= stale_after_seconds


def classify_canonical_runtime_authority(
    supervisor_state: Mapping[str, Any] | None,
    dashboard_state: Mapping[str, Any] | None = None,
    *,
    now: datetime | None = None,
    stale_after_seconds: float = 120.0,
) -> dict[str, Any]:
    """Classify the true health of the canonical runtime authority.

    This is the single fail-closed source of truth for whether the canonical
    launcher (`launcher/css_runtime_launcher.py`) is genuinely alive and
    heartbeating. It never treats a subordinate dashboard heartbeat, a
    synthetic gap-fill write, or a merely-recent file mtime as proof of
    canonical health -- it reads the declared `status` and `last_heartbeat_at`
    fields directly.
    """
    now_dt = now or datetime.now(timezone.utc)
    dashboard_fresh = _is_fresh(dashboard_state, now=now_dt, stale_after_seconds=stale_after_seconds)

    if not isinstance(supervisor_state, Mapping) or not supervisor_state:
        return {
            "authority_status": AUTHORITY_ORPHANED_RUNTIME if dashboard_fresh else AUTHORITY_MISSING,
            "canonical_alive": False,
            "orphan_runtime": dashboard_fresh,
            "reason": "canonical_supervisor_state_missing",
        }

    if bool(supervisor_state.get("synthetic")):
        # A gap-fill / fallback writer wrote this file. It is never proof
        # that the real canonical launcher process is alive.
        return {
            "authority_status": AUTHORITY_ORPHANED_RUNTIME if dashboard_fresh else AUTHORITY_STOPPED,
            "canonical_alive": False,
            "orphan_runtime": dashboard_fresh,
            "reason": "canonical_artifact_is_synthetic_gap_fill",
        }

    status = str(supervisor_state.get("status") or "").upper()
    heartbeat_raw = supervisor_state.get("last_heartbeat_at")
    if heartbeat_raw is None and "last_heartbeat_at" not in supervisor_state:
        heartbeat_raw = supervisor_state.get("last_heartbeat")
    heartbeat = _parse_iso(heartbeat_raw)

    if not status:
        return {
            "authority_status": AUTHORITY_ORPHANED_RUNTIME if dashboard_fresh else AUTHORITY_MALFORMED,
            "canonical_alive": False,
            "orphan_runtime": dashboard_fresh,
            "reason": "canonical_status_field_missing",
        }

    if status not in HEALTHY_STATUSES:
        reason = "canonical_status_stopped" if status in STOPPED_STATUSES else f"canonical_status_unhealthy:{status}"
        return {
            "authority_status": AUTHORITY_ORPHANED_RUNTIME if dashboard_fresh else AUTHORITY_STOPPED,
            "canonical_alive": False,
            "orphan_runtime": dashboard_fresh,
            "reason": reason,
        }

    # Status is a healthy value (RUNNING) from here on.
    if heartbeat_raw and heartbeat is None:
        return {
            "authority_status": AUTHORITY_ORPHANED_RUNTIME if dashboard_fresh else AUTHORITY_MALFORMED,
            "canonical_alive": False,
            "orphan_runtime": dashboard_fresh,
            "reason": "canonical_heartbeat_unparseable",
        }

    if heartbeat is None:
        # RUNNING with no heartbeat recorded yet (e.g. immediately after
        # start(), before the first heartbeat() call). Trust the declared
        # status rather than failing closed on an absent-but-not-yet-due field.
        return {
            "authority_status": AUTHORITY_ONLINE,
            "canonical_alive": True,
            "orphan_runtime": False,
            "reason": "canonical_status_running_heartbeat_pending",
        }

    age_seconds = (now_dt - heartbeat).total_seconds()
    if age_seconds > stale_after_seconds:
        return {
            "authority_status": AUTHORITY_ORPHANED_RUNTIME if dashboard_fresh else AUTHORITY_STALE,
            "canonical_alive": False,
            "orphan_runtime": dashboard_fresh,
            "reason": "canonical_heartbeat_stale",
        }

    return {
        "authority_status": AUTHORITY_ONLINE,
        "canonical_alive": True,
        "orphan_runtime": False,
        "reason": "canonical_heartbeat_fresh",
    }


__all__ = [
    "AUTHORITY_ONLINE",
    "AUTHORITY_STOPPED",
    "AUTHORITY_MISSING",
    "AUTHORITY_MALFORMED",
    "AUTHORITY_STALE",
    "AUTHORITY_ORPHANED_RUNTIME",
    "classify_canonical_runtime_authority",
]

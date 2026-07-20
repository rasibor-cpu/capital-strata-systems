"""
Phase 177F — Canonical Runtime Telemetry Service.

Unifies distinct operational counters without collapsing them into one field.
Never converts missing counters to factual zero.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

SCHEMA_VERSION = "css.runtime_telemetry.v1"

REPO_ROOT = Path(__file__).resolve().parents[2]
ENGINE_SUPERVISOR_FILE = REPO_ROOT / "runtime_supervisor.json"
CSS_SUPERVISOR_FILE = REPO_ROOT / "runtime" / "supervisor" / "css_runtime_supervisor_state.json"
SESSION_CANDIDATES = (
    REPO_ROOT / "artifacts" / "css_session_state_pcnrass.json",
    REPO_ROOT / "artifacts" / "css_session_recovery.json",
)

STATUS_UNKNOWN = "UNKNOWN"
STATUS_NOT_REPORTED = "NOT_REPORTED"
STATUS_STALE = "STALE"
STATUS_UNAVAILABLE = "UNAVAILABLE"
STATUS_OK = "OK"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_json(path: Path) -> tuple[dict[str, Any] | None, str]:
    try:
        if not path.is_file():
            return None, STATUS_UNAVAILABLE
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return None, STATUS_UNAVAILABLE
        return data, STATUS_OK
    except Exception:
        return None, STATUS_UNAVAILABLE


def _parse_ts(value: Any) -> datetime | None:
    if value in (None, "", "N/A"):
        return None
    try:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        text = str(value).strip()
        if text.replace(".", "", 1).isdigit():
            return datetime.fromtimestamp(float(text), tz=timezone.utc)
        return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None


def _field(
    value: Any,
    *,
    source: str,
    definition: str,
    period: str = "CURRENT",
    status: str = STATUS_OK,
    freshness: str = STATUS_OK,
) -> dict[str, Any]:
    return {
        "value": value,
        "status": status if value is not None else STATUS_NOT_REPORTED,
        "source": source,
        "provenance": source,
        "definition": definition,
        "period": period,
        "freshness": freshness,
    }


def _optional_int(raw: Mapping[str, Any] | None, key: str) -> int | None:
    if not raw or key not in raw:
        return None
    try:
        return int(raw[key])
    except (TypeError, ValueError):
        return None


def _load_session_cycle(session_paths: tuple[Path, ...] | None = None) -> tuple[int | None, str, str]:
    for path in session_paths or SESSION_CANDIDATES:
        data, status = _read_json(path)
        if status != STATUS_OK or not data:
            continue
        session = data.get("session") if isinstance(data.get("session"), Mapping) else data
        if not isinstance(session, Mapping):
            continue
        if "cycle_number" not in session and "cycle" not in session:
            return None, STATUS_NOT_REPORTED, f"SESSION:{path.name}"
        try:
            value = session.get("cycle_number", session.get("cycle"))
            return int(value), STATUS_OK, f"RUNTIME_SESSION:{path.name}"
        except (TypeError, ValueError):
            return None, STATUS_UNAVAILABLE, f"RUNTIME_SESSION:{path.name}"
    return None, STATUS_UNAVAILABLE, "RUNTIME_SESSION"


def build_runtime_telemetry(
    *,
    engine_supervisor_path: Path | None = None,
    css_supervisor_path: Path | None = None,
    session_paths: tuple[Path, ...] | None = None,
    heartbeat_stale_seconds: float = 120.0,
) -> dict[str, Any]:
    """Canonical telemetry snapshot for MC, launcher, mobile, and APIs."""
    generated_at = _utc_now()
    engine_path = engine_supervisor_path or ENGINE_SUPERVISOR_FILE
    css_path = css_supervisor_path or CSS_SUPERVISOR_FILE

    engine, engine_status = _read_json(engine_path)
    css, css_status = _read_json(css_path)
    session_cycle, session_status, session_source = _load_session_cycle(session_paths)

    supervisor_cycles = _optional_int(engine, "cycles_completed")
    uptime = _optional_int(engine, "uptime_seconds")
    runtime_errors = _optional_int(engine, "runtime_errors")
    broker_disconnects = _optional_int(engine, "broker_disconnects")
    recovery_attempts = _optional_int(engine, "recovery_attempts")
    alerts_generated = _optional_int(engine, "alerts_generated")
    engine_start = (engine or {}).get("start_time") if engine else None

    managed_restarts = _optional_int(css, "restart_count")
    failure_count = _optional_int(css, "failure_count")
    css_status_label = str((css or {}).get("status") or STATUS_UNAVAILABLE).upper() if css else STATUS_UNAVAILABLE
    heartbeat_at = (css or {}).get("last_heartbeat_at") or (css or {}).get("last_heartbeat")
    css_started = (css or {}).get("started_at")

    heartbeat_age: float | None = None
    heartbeat_freshness = STATUS_UNAVAILABLE
    parsed_hb = _parse_ts(heartbeat_at)
    if parsed_hb is not None:
        heartbeat_age = max(0.0, (datetime.now(timezone.utc) - parsed_hb).total_seconds())
        heartbeat_freshness = STATUS_OK if heartbeat_age <= heartbeat_stale_seconds else STATUS_STALE

    # Primary display cycle: session cycle when present; else UNKNOWN (never invent 0).
    if session_cycle is not None:
        display_cycle = session_cycle
        display_status = session_status
        display_source = session_source
        display_definition = "Primary UI cycle = session_cycle from runtime session state"
    else:
        display_cycle = None
        display_status = STATUS_UNKNOWN
        display_source = session_source
        display_definition = (
            "Primary UI cycle unavailable — session_cycle not reported; "
            "see supervisor_cycles_completed for engine-loop counter"
        )

    fields = {
        "display_cycle": _field(
            display_cycle,
            source=display_source,
            definition=display_definition,
            status=display_status,
            freshness=display_status,
        ),
        "session_cycle": _field(
            session_cycle,
            source=session_source,
            definition="Trading/runtime session cycle_number from session artifacts",
            status=session_status,
        ),
        "supervisor_cycles_completed": _field(
            supervisor_cycles,
            source="RUNTIME_SUPERVISOR:runtime_supervisor.json",
            definition="Lifetime dashboard / RuntimeSupervisor completed loop cycles (cumulative)",
            period="CUMULATIVE_SINCE_ENGINE_SUPERVISOR_START",
            status=engine_status if supervisor_cycles is not None else engine_status,
        ),
        "managed_service_restart_count": _field(
            managed_restarts,
            source="RUNTIME_SUPERVISOR:css_runtime_supervisor_state.json",
            definition=(
                "Lifetime successful auto-restarts of supervised child services "
                "(CSS Runtime / Mobile Launcher) within the current CSSRuntimeSupervisor process"
            ),
            period="CUMULATIVE_WITHIN_SUPERVISOR_PROCESS",
            status=css_status if managed_restarts is not None else css_status,
        ),
        "supervisor_failure_count": _field(
            failure_count,
            source="RUNTIME_SUPERVISOR:css_runtime_supervisor_state.json",
            definition="CSSRuntimeSupervisor recorded failure events",
            status=css_status if failure_count is not None else css_status,
        ),
        "recovery_attempts": _field(
            recovery_attempts,
            source="RUNTIME_SUPERVISOR:runtime_supervisor.json",
            definition="Engine RuntimeSupervisor recovery attempts",
            status=engine_status if recovery_attempts is not None else engine_status,
        ),
        "broker_disconnect_count": _field(
            broker_disconnects,
            source="RUNTIME_SUPERVISOR:runtime_supervisor.json",
            definition="Broker disconnect events recorded by engine RuntimeSupervisor",
            status=engine_status if broker_disconnects is not None else engine_status,
        ),
        "runtime_error_count": _field(
            runtime_errors,
            source="RUNTIME_SUPERVISOR:runtime_supervisor.json",
            definition="Runtime errors recorded by engine RuntimeSupervisor",
            status=engine_status if runtime_errors is not None else engine_status,
        ),
        "alerts_generated": _field(
            alerts_generated,
            source="RUNTIME_SUPERVISOR:runtime_supervisor.json",
            definition="Alerts generated counter from engine RuntimeSupervisor",
            status=engine_status if alerts_generated is not None else engine_status,
        ),
        "uptime_seconds": _field(
            uptime,
            source="RUNTIME_SUPERVISOR:runtime_supervisor.json",
            definition="Engine RuntimeSupervisor uptime since its recorded start_time",
            status=engine_status if uptime is not None else engine_status,
        ),
        "authoritative_heartbeat": _field(
            heartbeat_at,
            source="RUNTIME_SUPERVISOR:css_runtime_supervisor_state.json",
            definition="CSSRuntimeSupervisor last_heartbeat_at",
            freshness=heartbeat_freshness,
            status=css_status if heartbeat_at else css_status,
        ),
        "heartbeat_age_seconds": _field(
            round(heartbeat_age, 3) if heartbeat_age is not None else None,
            source="DERIVED",
            definition="Age of authoritative CSSRuntimeSupervisor heartbeat",
            freshness=heartbeat_freshness,
            status=STATUS_OK if heartbeat_age is not None else STATUS_UNAVAILABLE,
        ),
        "engine_supervisor_start_time": _field(
            engine_start,
            source="RUNTIME_SUPERVISOR:runtime_supervisor.json",
            definition="Engine RuntimeSupervisor start_time",
            status=engine_status if engine_start else engine_status,
        ),
        "css_supervisor_started_at": _field(
            css_started,
            source="RUNTIME_SUPERVISOR:css_runtime_supervisor_state.json",
            definition="CSSRuntimeSupervisor started_at (refreshed on managed restart success)",
            status=css_status if css_started else css_status,
        ),
        "css_supervisor_status": _field(
            css_status_label if css else None,
            source="RUNTIME_SUPERVISOR:css_runtime_supervisor_state.json",
            definition="CSSRuntimeSupervisor status string",
            status=css_status,
        ),
    }

    # Compatibility aliases (same values — no separate calculation)
    aliases = {
        "cycle": {
            **fields["display_cycle"],
            "deprecated": True,
            "migration": "Use display_cycle or session_cycle; never treat missing as 0",
            "alias_of": "display_cycle",
        },
        "restart_count": {
            **fields["managed_service_restart_count"],
            "deprecated": True,
            "migration": "Use managed_service_restart_count (managed child auto-restarts, not host reboots)",
            "alias_of": "managed_service_restart_count",
        },
        "cycles_completed": {
            **fields["supervisor_cycles_completed"],
            "deprecated": True,
            "migration": "Use supervisor_cycles_completed",
            "alias_of": "supervisor_cycles_completed",
        },
    }

    core = {
        "schema_version": SCHEMA_VERSION,
        "primary_display_cycle_field": "display_cycle",
        "fields": fields,
        "compatibility_aliases": aliases,
        "supervisor_status": css_status_label if css else STATUS_UNAVAILABLE,
        "freshness": heartbeat_freshness if heartbeat_at else engine_status,
        "paths": {
            "engine_supervisor": str(engine_path),
            "css_supervisor": str(css_path),
        },
        "generated_at": generated_at,
        "source": "RUNTIME_TELEMETRY",
        "provenance": {
            "engine_loop": "RUNTIME_SUPERVISOR",
            "managed_restarts": "RUNTIME_SUPERVISOR",
            "session_cycle": "RUNTIME_SESSION",
        },
    }
    core["state_hash"] = hashlib.sha256(
        json.dumps(
            {
                "display_cycle": display_cycle,
                "session_cycle": session_cycle,
                "supervisor_cycles_completed": supervisor_cycles,
                "managed_service_restart_count": managed_restarts,
                "heartbeat_at": heartbeat_at,
                "generated_at": generated_at,
            },
            sort_keys=True,
            default=str,
        ).encode("utf-8")
    ).hexdigest()
    return core


def telemetry_summary_for_ui(telemetry: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Concise card for mobile / frontend — preserves UNKNOWN for missing cycles."""
    snap = dict(telemetry or build_runtime_telemetry())
    fields = snap.get("fields") if isinstance(snap.get("fields"), Mapping) else {}

    def _v(name: str) -> Any:
        row = fields.get(name) if isinstance(fields.get(name), Mapping) else {}
        value = row.get("value")
        status = row.get("status")
        if value is None:
            return status or STATUS_UNKNOWN
        return value

    return {
        "display_cycle": _v("display_cycle"),
        "session_cycle": _v("session_cycle"),
        "supervisor_cycles_completed": _v("supervisor_cycles_completed"),
        "managed_service_restart_count": _v("managed_service_restart_count"),
        "supervisor_failure_count": _v("supervisor_failure_count"),
        "broker_disconnect_count": _v("broker_disconnect_count"),
        "runtime_error_count": _v("runtime_error_count"),
        "uptime_seconds": _v("uptime_seconds"),
        "heartbeat": _v("authoritative_heartbeat"),
        "heartbeat_age_seconds": _v("heartbeat_age_seconds"),
        "supervisor_status": snap.get("supervisor_status"),
        "freshness": snap.get("freshness"),
        "state_hash": snap.get("state_hash"),
        "generated_at": snap.get("generated_at"),
        "primary_display_cycle_field": snap.get("primary_display_cycle_field"),
        "provenance": snap.get("provenance"),
        "source": "RUNTIME_TELEMETRY",
        # Compatibility (explicitly aliased)
        "cycle": _v("display_cycle"),
        "restart_count": _v("managed_service_restart_count"),
        "cycle_deprecated": True,
        "restart_count_deprecated": True,
    }


__all__ = [
    "SCHEMA_VERSION",
    "STATUS_NOT_REPORTED",
    "STATUS_STALE",
    "STATUS_UNAVAILABLE",
    "STATUS_UNKNOWN",
    "build_runtime_telemetry",
    "telemetry_summary_for_ui",
]

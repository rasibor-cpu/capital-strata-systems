from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence


RUNNING = "RUNNING"
DEGRADED = "DEGRADED"
RECOVERING = "RECOVERING"
STOPPED = "STOPPED"
FAILED = "FAILED"
UNKNOWN = "UNKNOWN"

HEALTHY = "HEALTHY"
STALE = "STALE"
LOST = "LOST"
UNAVAILABLE = "UNAVAILABLE"
NOT_APPLICABLE = "NOT_APPLICABLE"

NOT_REQUIRED = "NOT_REQUIRED"
RECOVERY_PENDING = "RECOVERY_PENDING"
RECOVERING_STATUS = "RECOVERING"
RECOVERED = "RECOVERED"
RECOVERY_FAILED = "RECOVERY_FAILED"
MANUAL_INTERVENTION_REQUIRED = "MANUAL_INTERVENTION_REQUIRED"

_HEARTBEAT_STALE_SECONDS = 60
_HEARTBEAT_LOST_SECONDS = 180


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_timestamp(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.replace(tzinfo=parsed.tzinfo or timezone.utc).astimezone(timezone.utc)


def _iso(value: datetime | None) -> str | None:
    return value.astimezone(timezone.utc).isoformat() if value else None


@dataclass(frozen=True)
class RuntimeAlert:
    timestamp: str
    severity: str
    code: str
    reason: str
    subsystem: str
    next_action: str
    safety_state: dict[str, bool]
    recovery_status: str
    evidence_ref: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RestartPolicyDecision:
    allowed: bool
    restart_count: int
    max_restarts: int
    window_seconds: int
    recovery_status: str
    backoff_seconds: int
    reason: str


@dataclass(frozen=True)
class RuntimeOperationalState:
    runtime_status: str = UNKNOWN
    process_alive: bool | None = None
    heartbeat_status: str = UNAVAILABLE
    heartbeat_age: float | None = None
    broker_state: str = UNKNOWN
    broker_data_freshness: str = UNAVAILABLE
    api_health: str = UNAVAILABLE
    supervisor_status: str = UNKNOWN
    restart_count: int = 0
    last_restart_at: str | None = None
    last_failure_at: str | None = None
    last_failure_reason: str | None = None
    recovery_status: str = NOT_REQUIRED
    unattended_ready: bool = False
    advisory_only: bool = True
    execution_allowed: bool = False
    live_trading_blocked: bool = True
    broker_execution_armed: bool = False
    state_reason_codes: tuple[str, ...] = field(default_factory=tuple)
    evidence_refs: tuple[str, ...] = field(default_factory=tuple)
    alerts: tuple[RuntimeAlert, ...] = field(default_factory=tuple)
    assessed_at: str = field(default_factory=lambda: _iso(_now()) or "")

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["state_reason_codes"] = list(self.state_reason_codes)
        payload["evidence_refs"] = list(self.evidence_refs)
        payload["alerts"] = [alert.as_dict() for alert in self.alerts]
        payload["read_only"] = True
        return payload


def evaluate_restart_policy(
    restart_timestamps: Sequence[str] | None,
    *,
    now: datetime | None = None,
    max_restarts: int = 3,
    window_seconds: int = 300,
) -> RestartPolicyDecision:
    assessed_at = (now or _now()).astimezone(timezone.utc)
    recent = []
    for value in restart_timestamps or ():
        parsed = _parse_timestamp(value)
        if parsed and 0 <= (assessed_at - parsed).total_seconds() <= window_seconds:
            recent.append(parsed)
    count = len(recent)
    limit = max(1, int(max_restarts))
    if count >= limit:
        return RestartPolicyDecision(
            allowed=False,
            restart_count=count,
            max_restarts=limit,
            window_seconds=int(window_seconds),
            recovery_status=MANUAL_INTERVENTION_REQUIRED,
            backoff_seconds=0,
            reason="restart threshold reached within rolling window",
        )
    return RestartPolicyDecision(
        allowed=True,
        restart_count=count,
        max_restarts=limit,
        window_seconds=int(window_seconds),
        recovery_status=RECOVERY_PENDING,
        backoff_seconds=min(300, 2 ** count),
        reason="bounded recovery attempt permitted",
    )


def build_runtime_alerts(
    snapshot: Mapping[str, Any],
    *,
    now: datetime | None = None,
) -> tuple[RuntimeAlert, ...]:
    assessed_at = _iso((now or _now()).astimezone(timezone.utc)) or ""
    safety = {
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
    }
    recovery_status = str(snapshot.get("recovery_status", NOT_REQUIRED))
    alerts: list[RuntimeAlert] = []

    def add(code: str, severity: str, reason: str, action: str, subsystem: str = "runtime") -> None:
        alerts.append(RuntimeAlert(assessed_at, severity, code, reason, subsystem, action, safety, recovery_status, "runtime.operational_state"))

    heartbeat = str(snapshot.get("heartbeat_status", UNAVAILABLE)).upper()
    if heartbeat == LOST:
        add("ENGINE_HEARTBEAT_LOST", "CRITICAL", "engine heartbeat is lost", "stop relying on runtime state and inspect the process")
    elif heartbeat in {STALE, UNAVAILABLE}:
        add("DEGRADED_RUNTIME", "MEDIUM", "engine heartbeat is not current", "inspect heartbeat source and runtime logs")
    if str(snapshot.get("supervisor_status", UNKNOWN)).upper() in {"FAILED", "LOST"}:
        add("SUPERVISOR_FAILURE", "CRITICAL", "runtime supervisor is unhealthy", "require manual intervention before restart")
    if snapshot.get("process_alive") is False:
        add("UNEXPECTED_PROCESS_EXIT", "CRITICAL", "runtime process is not alive", "verify process state before bounded recovery")
    if str(snapshot.get("api_health", UNAVAILABLE)).upper() in {"FAILED", "UNAVAILABLE"}:
        add("API_HEALTH_FAILED", "HIGH", "runtime API health is unavailable", "inspect API process and health endpoint")
    if str(snapshot.get("broker_data_freshness", UNAVAILABLE)).upper() in {STALE, UNAVAILABLE}:
        add("BROKER_DATA_STALE", "HIGH", "broker data is not current", "revalidate broker state before relying on it", "broker")
    if str(snapshot.get("recovery_status", NOT_REQUIRED)) == MANUAL_INTERVENTION_REQUIRED:
        add("RESTART_LOOP", "CRITICAL", "bounded restart threshold was reached", "stop automatic recovery and require manual intervention")
    if str(snapshot.get("recovery_status", NOT_REQUIRED)) == RECOVERY_FAILED:
        add("RECOVERY_FAILED", "HIGH", "automatic recovery failed", "require manual intervention and inspect failure evidence")
    return tuple(alerts)


def build_runtime_operational_state(
    snapshot: Mapping[str, Any] | None = None,
    *,
    now: datetime | None = None,
) -> RuntimeOperationalState:
    raw = dict(snapshot or {})
    assessed = (now or _now()).astimezone(timezone.utc)
    heartbeat_at = _parse_timestamp(raw.get("heartbeat_at") or raw.get("last_heartbeat_at"))
    age = (assessed - heartbeat_at).total_seconds() if heartbeat_at else None
    supplied_heartbeat = str(raw.get("heartbeat_status", "")).upper()
    if supplied_heartbeat in {HEALTHY, STALE, LOST, UNAVAILABLE}:
        heartbeat_status = supplied_heartbeat
    elif age is None:
        heartbeat_status = UNAVAILABLE
    elif age <= _HEARTBEAT_STALE_SECONDS:
        heartbeat_status = HEALTHY
    elif age <= _HEARTBEAT_LOST_SECONDS:
        heartbeat_status = STALE
    else:
        heartbeat_status = LOST

    process_alive = raw.get("process_alive") if isinstance(raw.get("process_alive"), bool) else None
    api_health = str(raw.get("api_health", UNAVAILABLE)).upper()
    if api_health == "OK":
        api_health = "HEALTHY"
    supervisor_status = str(raw.get("supervisor_status", UNKNOWN)).upper()
    broker_freshness = str(raw.get("broker_data_freshness", UNAVAILABLE)).upper()
    recovery_status = str(raw.get("recovery_status", NOT_REQUIRED)).upper()
    restart_count = int(raw.get("restart_count", 0)) if isinstance(raw.get("restart_count", 0), int) else 0

    reasons = set(str(item) for item in raw.get("state_reason_codes", []) if item)
    if heartbeat_status in {STALE, LOST, UNAVAILABLE}:
        reasons.add("HEARTBEAT_NOT_CURRENT")
    if supervisor_status in {"FAILED", "LOST"}:
        reasons.add("SUPERVISOR_UNHEALTHY")
    if broker_freshness in {STALE, UNAVAILABLE}:
        reasons.add("BROKER_DATA_NOT_CURRENT")
    if recovery_status == MANUAL_INTERVENTION_REQUIRED:
        reasons.add("CRASH_LOOP_GUARD")

    alerts = build_runtime_alerts({
        **raw,
        "heartbeat_status": heartbeat_status,
        "broker_data_freshness": broker_freshness,
        "api_health": api_health,
        "supervisor_status": supervisor_status,
        "recovery_status": recovery_status,
        "process_alive": process_alive,
    }, now=assessed)
    critical_alert = any(alert.severity == "CRITICAL" for alert in alerts)
    healthy = process_alive is True and heartbeat_status == HEALTHY and api_health == "HEALTHY" and supervisor_status == HEALTHY
    runtime_status = RUNNING if healthy and not critical_alert else (STOPPED if process_alive is False else DEGRADED)
    broker_ready = broker_freshness in {"CURRENT", NOT_APPLICABLE}
    unattended_ready = healthy and broker_ready and recovery_status not in {RECOVERY_FAILED, MANUAL_INTERVENTION_REQUIRED} and not critical_alert
    return RuntimeOperationalState(
        runtime_status=runtime_status,
        process_alive=process_alive,
        heartbeat_status=heartbeat_status,
        heartbeat_age=age,
        broker_state=str(raw.get("broker_state", UNKNOWN)),
        broker_data_freshness=broker_freshness,
        api_health=api_health,
        supervisor_status=supervisor_status,
        restart_count=restart_count,
        last_restart_at=str(raw.get("last_restart_at")) if raw.get("last_restart_at") else None,
        last_failure_at=str(raw.get("last_failure_at")) if raw.get("last_failure_at") else None,
        last_failure_reason=str(raw.get("last_failure_reason")) if raw.get("last_failure_reason") else None,
        recovery_status=recovery_status,
        unattended_ready=unattended_ready,
        advisory_only=True,
        execution_allowed=False,
        live_trading_blocked=True,
        broker_execution_armed=False,
        state_reason_codes=tuple(sorted(reasons)),
        evidence_refs=tuple(str(item) for item in raw.get("evidence_refs", ["runtime.operational_state"])),
        alerts=alerts,
        assessed_at=assessed.isoformat(),
    )


__all__ = [
    "RuntimeAlert", "RuntimeOperationalState", "RestartPolicyDecision",
    "build_runtime_alerts", "build_runtime_operational_state", "evaluate_restart_policy",
    "HEALTHY", "STALE", "LOST", "UNAVAILABLE", "MANUAL_INTERVENTION_REQUIRED",
]
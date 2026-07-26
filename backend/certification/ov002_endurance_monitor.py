"""OV-002 controlled 72-hour endurance monitor (genuine wall-clock only).

Never simulates elapsed time. Never backfills snapshots. Never enables live trading.
"""

from __future__ import annotations

import json
import math
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.certification.evidence_machine import REPO_ROOT, current_git_identity

TARGET_HOURS = 72.0
SNAPSHOT_INTERVAL_SECONDS = 5 * 60
CHECKPOINT_HOURS = (6, 12, 24, 36, 48, 60, 72)
MONITOR_GAP_INVALIDATE_SECONDS = 20 * 60
HEALTH_BASE = os.environ.get("CSS_OV002_HEALTH_BASE", "http://127.0.0.1:8765")
SUPERVISOR_STATE_PATH = REPO_ROOT / "runtime" / "supervisor" / "css_runtime_supervisor_state.json"
ALERTS_DIR = REPO_ROOT / "runtime" / "alerts"
SUPERVISOR_FRESHNESS_SECONDS = 15 * 60
FUTURE_SKEW_SECONDS = 5 * 60
BOUNDED_ALERT_SCAN_LIMIT = 1000


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_stamp(dt: datetime | None = None) -> str:
    return (dt or _utc_now()).strftime("%Y%m%dT%H%M%SZ")


def _iso(dt: datetime | None = None) -> str:
    return (dt or _utc_now()).isoformat()


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _parse_utc_timestamp(value: Any, *, now: datetime | None = None) -> tuple[datetime | None, str | None]:
    if value is None or value == "":
        return None, "missing"
    if isinstance(value, (int, float)):
        if not math.isfinite(float(value)):
            return None, "non_finite"
        try:
            dt = datetime.fromtimestamp(float(value), tz=timezone.utc)
        except Exception:
            return None, "malformed"
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            return None, "missing"
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except Exception:
            return None, "malformed"
    else:
        return None, "malformed"

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt = dt.astimezone(timezone.utc)
    reference = now or _utc_now()
    if (dt - reference).total_seconds() > FUTURE_SKEW_SECONDS:
        return None, "future_skew"
    return dt, None


def _finite_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        return int(value)
    if isinstance(value, str):
        try:
            number = float(value)
        except Exception:
            return None
        if not math.isfinite(number):
            return None
        return int(number)
    return None


def _alert_code(alert: dict[str, Any]) -> str:
    metadata = alert.get("metadata") if isinstance(alert.get("metadata"), dict) else {}
    for key in ("event_type", "alert_code", "code", "type"):
        value = metadata.get(key) or alert.get(key)
        if value:
            return str(value).upper()
    return str(alert.get("message") or "").upper()


def _load_alerts_since(alerts_dir: Path, start_utc: str, *, now: datetime | None = None) -> dict[str, Any]:
    start_dt, start_error = _parse_utc_timestamp(start_utc, now=now)
    if start_error or start_dt is None:
        return {"ok": False, "errors": [f"run_start_timestamp_{start_error}"], "alerts": []}
    if not alerts_dir.exists():
        return {"ok": True, "errors": [], "alerts": []}

    alerts: list[dict[str, Any]] = []
    errors: list[str] = []
    for path in sorted(alerts_dir.glob("*.json"), reverse=True)[:BOUNDED_ALERT_SCAN_LIMIT]:
        payload = _read_json(path)
        if payload is None:
            errors.append(f"alert_malformed:{path.name}")
            continue
        timestamp = payload.get("timestamp") or payload.get("observed_at_utc")
        alert_dt, alert_error = _parse_utc_timestamp(timestamp, now=now)
        if alert_error or alert_dt is None:
            errors.append(f"alert_timestamp_{alert_error}:{path.name}")
            continue
        if alert_dt >= start_dt:
            payload["_path"] = str(path)
            alerts.append(payload)
    return {"ok": not errors, "errors": errors, "alerts": list(reversed(alerts))}


def load_supervisor_state(supervisor_state_path: Path) -> dict[str, Any]:
    state = _read_json(supervisor_state_path)
    if state is None:
        return {
            "ok": False,
            "path": str(supervisor_state_path),
            "errors": ["supervisor_state_missing_or_malformed"],
            "state": {},
        }
    return {"ok": True, "path": str(supervisor_state_path), "errors": [], "state": state}


def _snapshot_supervisor_identity(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "supervisor_id": state.get("supervisor_id"),
        "started_at": state.get("started_at"),
        "process_generation": state.get("process_generation"),
        "process_identity": state.get("process_identity"),
        "restart_count": state.get("restart_count"),
        "max_restart_limit": state.get("max_restart_limit"),
    }


def reconcile_supervisor_and_alerts(
    *,
    supervisor_state: dict[str, Any] | None,
    alerts: list[dict[str, Any]],
    run_meta: dict[str, Any],
    now: datetime | None = None,
    freshness_seconds: int = SUPERVISOR_FRESHNESS_SECONDS,
) -> dict[str, Any]:
    now_dt = now or _utc_now()
    reasons: list[str] = []
    events: list[dict[str, Any]] = []

    state = supervisor_state if isinstance(supervisor_state, dict) else {}
    if not state:
        reasons.append("supervisor_state_missing")
    else:
        status_text = str(state.get("status") or "").upper()
        if status_text != "RUNNING":
            if state.get("shutdown_requested") is True:
                reasons.append("supervisor_controlled_shutdown_observed")
            else:
                reasons.append("supervisor_not_running")

        for field in ("started_at", "last_heartbeat_at"):
            parsed, error = _parse_utc_timestamp(state.get(field), now=now_dt)
            if error:
                reasons.append(f"supervisor_{field}_{error}")
            elif field == "last_heartbeat_at" and parsed is not None:
                age = (now_dt - parsed).total_seconds()
                if age > freshness_seconds:
                    reasons.append("supervisor_heartbeat_stale")

        restart_count = _finite_int(state.get("restart_count"))
        restart_attempt_count = _finite_int(state.get("restart_attempt_count", 0))
        max_restart_limit = _finite_int(state.get("max_restart_limit"))
        process_generation = _finite_int(state.get("process_generation"))
        if restart_count is None:
            reasons.append("supervisor_restart_count_malformed")
        if restart_attempt_count is None:
            reasons.append("supervisor_restart_attempt_count_malformed")
        if restart_count is not None and restart_count > 0:
            reasons.append("unexpected_supervisor_restart_observed")
            events.append(
                {
                    "reason": "unexpected_supervisor_restart_observed",
                    "restart_count": restart_count,
                    "observed_at_utc": _iso(now_dt),
                }
            )
        if max_restart_limit is None:
            reasons.append("supervisor_max_restart_limit_malformed")
        elif restart_count is not None:
            if restart_count >= max_restart_limit:
                reasons.append("restart_limit_reached")
            if restart_count > max_restart_limit:
                reasons.append("restart_limit_exceeded")
            if restart_attempt_count is not None and restart_attempt_count >= max_restart_limit:
                reasons.append("restart_attempt_limit_reached")
            if restart_attempt_count is not None and restart_attempt_count > max_restart_limit:
                reasons.append("restart_attempt_limit_exceeded")
        if process_generation is None:
            reasons.append("supervisor_process_generation_malformed")

        if state.get("restart_limit_exhausted") is True or str(state.get("status")) in {
            "FAILED",
            "RESTART_LIMIT_EXHAUSTED",
        }:
            reasons.append("restart_limit_exhausted")

        duplicate_owners = state.get("duplicate_canonical_owners")
        if duplicate_owners:
            reasons.append("duplicate_canonical_runtime_owner")

        expected = run_meta.get("supervisor_identity")
        if isinstance(expected, dict):
            if state.get("supervisor_id") != expected.get("supervisor_id"):
                reasons.append("supervisor_identity_changed")
            if state.get("started_at") != expected.get("started_at"):
                reasons.append("supervisor_started_at_changed")
            expected_generation = _finite_int(expected.get("process_generation"))
            if (
                expected_generation is not None
                and process_generation is not None
                and process_generation != expected_generation
            ):
                reasons.append("process_generation_changed")
                events.append(
                    {
                        "reason": "process_generation_changed",
                        "expected_generation": expected_generation,
                        "observed_generation": process_generation,
                        "observed_at_utc": _iso(now_dt),
                    }
                )

        for item in state.get("failure_history") or []:
            if not isinstance(item, dict):
                continue
            event_type = str(item.get("event_type") or "")
            if event_type == "controlled_shutdown":
                continue
            if event_type in {
                "unexpected_failure",
                "unexpected_restart_success",
                "restart_limit_exhausted",
            }:
                events.append(item)

    for alert in alerts:
        severity = str(alert.get("severity") or "").upper()
        code = _alert_code(alert)
        message = str(alert.get("message") or "")
        if severity == "CRITICAL" and (
            "ENGINE_HEARTBEAT_LOST" in code or "HEARTBEAT LOST" in message.upper()
        ):
            reasons.append("engine_heartbeat_lost")
            events.append(
                {
                    "reason": "engine_heartbeat_lost",
                    "alert_id": alert.get("alert_id"),
                    "timestamp": alert.get("timestamp"),
                    "message": message,
                }
            )
        elif severity == "CRITICAL" and "RESTART LIMIT" in message.upper():
            reasons.append("restart_limit_exhausted")
            events.append(
                {
                    "reason": "restart_limit_exhausted",
                    "alert_id": alert.get("alert_id"),
                    "timestamp": alert.get("timestamp"),
                    "message": message,
                }
            )
        elif severity == "WARNING" and (
            "AUTO-RESTART" in message.upper()
            or "EXITED UNEXPECTEDLY" in message.upper()
            or "RUNTIME_FAILURE" in code
        ):
            reasons.append("unexpected_restart_alert")
            events.append(
                {
                    "reason": "unexpected_restart_alert",
                    "alert_id": alert.get("alert_id"),
                    "timestamp": alert.get("timestamp"),
                    "message": message,
                }
            )

    unique_reasons = list(dict.fromkeys(reasons))
    return {
        "ok": not unique_reasons,
        "reasons": unique_reasons,
        "events": events[-100:],
        "observed_at_utc": _iso(now_dt),
    }


def _http_json(path: str, timeout: float = 8.0) -> tuple[int | None, Any]:
    url = f"{HEALTH_BASE.rstrip('/')}{path}"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            try:
                return int(resp.status), json.loads(body)
            except json.JSONDecodeError:
                return int(resp.status), {"raw": body[:2000]}
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read().decode("utf-8", errors="replace")
            data = json.loads(body)
        except Exception:
            data = {"error": str(exc)}
        return int(exc.code), data
    except Exception as exc:  # noqa: BLE001
        return None, {"error": str(exc), "url": url}


def machine_identity() -> dict[str, Any]:
    return {
        "hostname": socket.gethostname(),
        "platform": os.name,
        "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "pid_monitor": os.getpid(),
    }


def git_freeze() -> dict[str, str]:
    identity = current_git_identity()
    return identity


def capture_safety_assertions() -> dict[str, Any]:
    status_code, runtime = _http_json("/api/runtime-mode")
    auth_code, authority = _http_json("/api/v1/live-execution-authority")
    health_code, health = _http_json("/health")

    runtime = runtime if isinstance(runtime, dict) else {}
    authority = authority if isinstance(authority, dict) else {}
    # Nested authority payloads vary.
    data = authority.get("data") if isinstance(authority.get("data"), dict) else authority
    live = data.get("live_execution_authority") if isinstance(data.get("live_execution_authority"), dict) else {}

    execution_allowed = bool(
        runtime.get("execution_allowed")
        or runtime.get("execution_enabled")
        or data.get("execution_allowed")
        or live.get("execution_authority")
    )
    can_live = bool(data.get("can_live_execute") or live.get("can_live_execute"))
    advisory = bool(runtime.get("advisory_only", True) and data.get("advisory_only", True))
    fail_closed = bool(runtime.get("fail_closed", True))
    mode = str(runtime.get("runtime_mode") or "UNKNOWN")

    checks = {
        "execution_allowed_false": execution_allowed is False,
        "can_live_execute_false": can_live is False,
        "live_trading_blocked": (not can_live) and (not execution_allowed),
        "advisory_or_disabled_mode": mode in {"DISABLED", "PAPER", "LIVE_READ_ONLY"} or advisory,
        "fail_closed": fail_closed,
        "health_reachable": health_code == 200,
        "runtime_reachable": status_code == 200,
        "authority_reachable": auth_code == 200,
        "phase181_not_certified_claimed": True,  # certification claim never set by this monitor
        "coinbase_account_auth_not_claimed": True,
        "oanda_not_live_certified_claimed": True,
        "broker_writes_not_enabled_by_monitor": True,
    }
    ok = all(checks.values()) and mode != "LIVE"
    return {
        "ok": ok,
        "observed_at_utc": _iso(),
        "runtime_mode": mode,
        "advisory_only": advisory,
        "fail_closed": fail_closed,
        "execution_allowed": execution_allowed,
        "can_live_execute": can_live,
        "health": health if isinstance(health, dict) else {"status_code": health_code},
        "checks": checks,
        "authority_reason": data.get("authority_reason") or live.get("authority_reason"),
        "live_authority_state": data.get("live_authority_state") or live.get("live_authority_state"),
        "non_claims": {
            "coinbase_account_authenticated": False,
            "oanda_live_certified": False,
            "broker_fail_closed_is_not_certification": True,
            "phase181": "NOT_CERTIFIED",
        },
    }


def _process_rss_mb() -> dict[str, Any]:
    """Best-effort memory sample for CSS-related python processes (Windows)."""
    rows: list[dict[str, Any]] = []
    try:
        completed = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                (
                    "Get-CimInstance Win32_Process -Filter \"name='python.exe'\" | "
                    "Where-Object { $_.CommandLine -match 'css_|launcher.css_|css_live_dashboard' } | "
                    "Select-Object ProcessId,"
                    "@{n='WS_MB';e={[math]::Round($_.WorkingSetSize/1MB,2)}},"
                    "@{n='Cmd';e={ if ($_.CommandLine.Length -gt 120) "
                    "{ $_.CommandLine.Substring(0,120) } else { $_.CommandLine } }} | "
                    "ConvertTo-Json -Compress"
                ),
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        raw = (completed.stdout or "").strip()
        if raw:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                rows = [parsed]
            elif isinstance(parsed, list):
                rows = parsed
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc), "processes": []}
    total = 0.0
    for row in rows:
        try:
            total += float(row.get("WS_MB") or 0)
        except Exception:
            pass
    return {"ok": True, "process_count": len(rows), "total_ws_mb": round(total, 2), "processes": rows}


def _disk_free_gb(path: Path) -> float | None:
    try:
        usage = os.statvfs  # type: ignore[attr-defined]
    except AttributeError:
        usage = None
    if usage is not None:
        try:
            st = os.statvfs(str(path))  # type: ignore[attr-defined]
            return round((st.f_bavail * st.f_frsize) / (1024**3), 3)
        except Exception:
            return None
    try:
        import shutil

        total, used, free = shutil.disk_usage(str(path))
        return round(free / (1024**3), 3)
    except Exception:
        return None


def capture_health_snapshot(
    *,
    run_id: str,
    start_epoch: float,
    frozen_sha: str,
    run_meta: dict[str, Any] | None = None,
    supervisor_state_path: str | Path | None = None,
    alerts_dir: str | Path | None = None,
    supervisor_freshness_seconds: int = SUPERVISOR_FRESHNESS_SECONDS,
) -> dict[str, Any]:
    now = time.time()
    elapsed_h = (now - start_epoch) / 3600.0
    health_code, health = _http_json("/health")
    mode_code, runtime = _http_json("/api/runtime-mode")
    auth_code, authority = _http_json("/api/v1/live-execution-authority")
    telem_code, telem = _http_json("/api/runtime-telemetry")
    oi_code, oi = _http_json("/api/options-income/status")

    runtime = runtime if isinstance(runtime, dict) else {}
    authority = authority if isinstance(authority, dict) else {}
    data = authority.get("data") if isinstance(authority.get("data"), dict) else authority
    live = data.get("live_execution_authority") if isinstance(data.get("live_execution_authority"), dict) else {}

    identity = current_git_identity()
    commit_drift = identity.get("git_sha") != frozen_sha
    execution_allowed = bool(
        runtime.get("execution_enabled")
        or data.get("execution_allowed")
        or live.get("execution_authority")
    )
    can_live = bool(data.get("can_live_execute") or live.get("can_live_execute"))

    resources = _process_rss_mb()
    meta_for_reconcile = dict(run_meta or {})
    if not meta_for_reconcile.get("start_utc"):
        meta_for_reconcile["start_utc"] = _iso(datetime.fromtimestamp(start_epoch, tz=timezone.utc))

    supervisor_path = Path(supervisor_state_path or SUPERVISOR_STATE_PATH)
    alerts_path = Path(alerts_dir or ALERTS_DIR)
    supervisor_payload = load_supervisor_state(supervisor_path)
    alerts_payload = _load_alerts_since(alerts_path, str(meta_for_reconcile.get("start_utc") or ""))
    supervisor_state = supervisor_payload.get("state") if supervisor_payload.get("ok") else {}
    reconciliation = reconcile_supervisor_and_alerts(
        supervisor_state=supervisor_state,
        alerts=alerts_payload.get("alerts") or [],
        run_meta=meta_for_reconcile,
        freshness_seconds=supervisor_freshness_seconds,
    )
    if supervisor_payload.get("errors"):
        reconciliation["reasons"] = list(
            dict.fromkeys(list(reconciliation.get("reasons") or []) + supervisor_payload["errors"])
        )
        reconciliation["ok"] = False
    if alerts_payload.get("errors"):
        reconciliation["reasons"] = list(
            dict.fromkeys(list(reconciliation.get("reasons") or []) + alerts_payload["errors"])
        )
        reconciliation["ok"] = False

    snapshot = {
        "schema_version": "css.ov002.health_snapshot.v1",
        "run_id": run_id,
        "observed_at_utc": _iso(),
        "elapsed_hours_wall_clock": round(elapsed_h, 6),
        "timing_mode": "wall_clock",
        "synthetic_timing": False,
        "health_http": health_code,
        "health": health if isinstance(health, dict) else {"payload": health},
        "runtime_http": mode_code,
        "runtime_mode": runtime.get("runtime_mode"),
        "advisory_only": runtime.get("advisory_only"),
        "fail_closed": runtime.get("fail_closed"),
        "execution_enabled": runtime.get("execution_enabled"),
        "execution_allowed": execution_allowed,
        "can_live_execute": can_live,
        "authority_http": auth_code,
        "live_authority_state": data.get("live_authority_state") or live.get("live_authority_state"),
        "authority_reason": data.get("authority_reason") or live.get("authority_reason"),
        "telemetry_http": telem_code,
        "options_income_http": oi_code,
        "options_income": {
            "status": (oi or {}).get("status") if isinstance(oi, dict) else None,
            "advisory_only": (oi or {}).get("advisory_only") if isinstance(oi, dict) else None,
            "execution_allowed": (oi or {}).get("execution_allowed") if isinstance(oi, dict) else None,
        },
        "brokers": {
            "coinbase": {
                "account_authenticated_claimed": False,
                "note": "OV-001 residual: do not claim account auth; market may be available",
                "execution_blocked": not can_live and not execution_allowed,
            },
            "oanda": {
                "practice_read_only_identity": True,
                "live_certified_claimed": False,
                "execution_blocked": not can_live and not execution_allowed,
            },
        },
        "resources": resources,
        "disk_free_gb": _disk_free_gb(REPO_ROOT),
        "supervisor": {
            "path": str(supervisor_path),
            "ok": bool(supervisor_payload.get("ok")),
            "errors": supervisor_payload.get("errors") or [],
            "state": supervisor_state,
            "reconciliation": reconciliation,
        },
        "alerts": {
            "path": str(alerts_path),
            "ok": bool(alerts_payload.get("ok")),
            "errors": alerts_payload.get("errors") or [],
            "in_window_count": len(alerts_payload.get("alerts") or []),
            "in_window": alerts_payload.get("alerts") or [],
        },
        "git": identity,
        "frozen_sha": frozen_sha,
        "commit_drift": commit_drift,
        "safety_ok": (not execution_allowed)
        and (not can_live)
        and (not commit_drift)
        and health_code == 200
        and mode_code == 200
        and bool(reconciliation.get("ok")),
    }
    return snapshot


def evaluate_invalidation(
    snapshot: dict[str, Any],
    *,
    last_snapshot_epoch: float | None,
) -> dict[str, Any] | None:
    reasons: list[str] = []
    events: list[dict[str, Any]] = []
    if snapshot.get("execution_allowed") or snapshot.get("can_live_execute"):
        reasons.append("live_execution_enabled")
    if snapshot.get("commit_drift"):
        reasons.append("active_commit_changed")
    if snapshot.get("health_http") != 200:
        reasons.append("health_unreachable")
    if snapshot.get("runtime_http") != 200:
        reasons.append("runtime_mode_unreachable")
    supervisor = snapshot.get("supervisor") if isinstance(snapshot.get("supervisor"), dict) else {}
    reconciliation = (
        supervisor.get("reconciliation") if isinstance(supervisor.get("reconciliation"), dict) else {}
    )
    for reason in reconciliation.get("reasons") or []:
        reasons.append(str(reason))
    for event in reconciliation.get("events") or []:
        if isinstance(event, dict):
            events.append(event)
    if last_snapshot_epoch is not None:
        gap = time.time() - last_snapshot_epoch
        # gap check applied by caller between successful snapshots; here only if provided stale
        if gap > MONITOR_GAP_INVALIDATE_SECONDS and snapshot.get("_gap_check"):
            reasons.append("monitoring_gap_exceeded")
    if not reasons:
        return None
    return {
        "invalidated": True,
        "reasons": list(dict.fromkeys(reasons)),
        "events": events[-100:],
        "observed_at_utc": _iso(),
        "elapsed_hours_wall_clock": snapshot.get("elapsed_hours_wall_clock"),
    }


def write_checkpoint(
    root: Path,
    *,
    hour: int,
    run_meta: dict[str, Any],
    latest: dict[str, Any],
    incidents: list[dict[str, Any]],
) -> dict[str, Any]:
    recommendation = "CONTINUE"
    if not latest.get("safety_ok"):
        recommendation = "INVALIDATE AND STOP"
    elif latest.get("health_http") != 200:
        recommendation = "CONTINUE WITH OBSERVATION"

    payload = {
        "checkpoint": f"T+{hour}h",
        "elapsed_hours_wall_clock": latest.get("elapsed_hours_wall_clock"),
        "run_still_valid": recommendation != "INVALIDATE AND STOP",
        "incidents_since_prior": incidents,
        "restarts": "see process resource samples / supervisor evidence",
        "failures": [] if latest.get("safety_ok") else ["safety_or_health_degraded"],
        "degraded_checks": [
            name
            for name, ok in (
                ("health", latest.get("health_http") == 200),
                ("runtime", latest.get("runtime_http") == 200),
                ("authority", latest.get("authority_http") == 200),
            )
            if not ok
        ],
        "broker_status": latest.get("brokers"),
        "resource_trends": latest.get("resources"),
        "safety_posture": {
            "execution_allowed": latest.get("execution_allowed"),
            "can_live_execute": latest.get("can_live_execute"),
            "advisory_only": latest.get("advisory_only"),
            "fail_closed": latest.get("fail_closed"),
            "runtime_mode": latest.get("runtime_mode"),
        },
        "recommendation": recommendation,
        "observed_at_utc": _iso(),
        "run_id": run_meta.get("run_id"),
        "frozen_sha": run_meta.get("frozen_sha"),
    }
    stamp = f"Tplus{hour:02d}h"
    _write_json(root / "checkpoints" / f"CHECKPOINT_{stamp}.json", payload)
    md = root / "checkpoints" / f"CHECKPOINT_{stamp}.md"
    md.write_text(
        "\n".join(
            [
                f"# OV-002 Checkpoint T+{hour}h",
                "",
                f"- Elapsed wall-clock hours: `{payload['elapsed_hours_wall_clock']}`",
                f"- Run still valid: `{payload['run_still_valid']}`",
                f"- Recommendation: **{recommendation}**",
                f"- Runtime mode: `{latest.get('runtime_mode')}`",
                f"- execution_allowed: `{latest.get('execution_allowed')}`",
                f"- can_live_execute: `{latest.get('can_live_execute')}`",
                f"- Health HTTP: `{latest.get('health_http')}`",
                f"- Observed (UTC): `{payload['observed_at_utc']}`",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return payload


def _existing_invalidation(root: Path) -> dict[str, Any] | None:
    invalidation = _read_json(root / "INVALIDATION.json")
    if invalidation:
        return invalidation
    status = _read_json(root / "RUN_STATUS.json")
    if status and str(status.get("status")) == "INVALIDATED":
        return {
            "invalidated": True,
            "reasons": status.get("reasons") or status.get("invalidation_reasons") or [],
            "observed_at_utc": status.get("updated_at_utc") or status.get("observed_at_utc"),
        }
    return None


def _write_invalidated_status(
    root: Path,
    *,
    run_id: str,
    invalidation: dict[str, Any],
) -> None:
    _write_json(root / "INVALIDATION.json", invalidation)
    _write_json(
        root / "RUN_STATUS.json",
        {
            "status": "INVALIDATED",
            "run_id": run_id,
            "updated_at_utc": _iso(),
            "reasons": invalidation.get("reasons") or [],
            "invalidation_reasons": invalidation.get("reasons") or [],
            "invalidation_events": invalidation.get("events") or [],
            "recommendation_pending": "ENDURANCE INVALIDATED",
        },
    )


def initialize_run(
    output_dir: Path | None = None,
    *,
    supervisor_state_path: str | Path | None = None,
    alerts_dir: str | Path | None = None,
    supervisor_freshness_seconds: int = SUPERVISOR_FRESHNESS_SECONDS,
) -> dict[str, Any]:
    start = _utc_now()
    stamp = _utc_stamp(start)
    root = Path(
        output_dir
        or REPO_ROOT / "runtime_reports" / "operational_validation" / f"ov002_72h_{stamp}"
    )
    root.mkdir(parents=True, exist_ok=True)
    (root / "snapshots").mkdir(exist_ok=True)
    (root / "checkpoints").mkdir(exist_ok=True)
    (root / "resources").mkdir(exist_ok=True)
    (root / "brokers").mkdir(exist_ok=True)

    frozen = git_freeze()
    safety = capture_safety_assertions()
    if not safety.get("ok"):
        _write_json(root / "SAFETY_ASSERTIONS.json", safety)
        _write_json(
            root / "RUN_STATUS.json",
            {
                "status": "NOT_STARTED",
                "reason": "safety_assertions_failed",
                "observed_at_utc": _iso(),
            },
        )
        return {
            "ok": False,
            "package_dir": str(root),
            "safety": safety,
            "status": "NOT_STARTED",
        }

    supervisor_path = Path(supervisor_state_path or SUPERVISOR_STATE_PATH)
    alerts_path = Path(alerts_dir or ALERTS_DIR)
    supervisor_payload = load_supervisor_state(supervisor_path)
    supervisor_state = supervisor_payload.get("state") if supervisor_payload.get("ok") else {}
    alerts_payload = _load_alerts_since(alerts_path, _iso(start), now=start)
    preflight = reconcile_supervisor_and_alerts(
        supervisor_state=supervisor_state,
        alerts=alerts_payload.get("alerts") or [],
        run_meta={"start_utc": _iso(start)},
        now=start,
        freshness_seconds=supervisor_freshness_seconds,
    )
    preflight_reasons = list(preflight.get("reasons") or [])
    preflight_reasons.extend(supervisor_payload.get("errors") or [])
    preflight_reasons.extend(alerts_payload.get("errors") or [])
    preflight_reasons = list(dict.fromkeys(preflight_reasons))
    if preflight_reasons:
        payload = {
            "status": "NOT_STARTED",
            "reason": "supervisor_preflight_failed",
            "reasons": preflight_reasons,
            "observed_at_utc": _iso(),
            "supervisor_state_path": str(supervisor_path),
            "alerts_dir": str(alerts_path),
        }
        _write_json(root / "SUPERVISOR_PREFLIGHT.json", payload)
        _write_json(root / "RUN_STATUS.json", payload)
        return {
            "ok": False,
            "package_dir": str(root),
            "safety": safety,
            "status": "NOT_STARTED",
            "preflight": payload,
        }

    run_id = f"OV002-{stamp}"
    meta = {
        "schema_version": "css.ov002.run_meta.v1",
        "run_id": run_id,
        "programme": "Release Gate 3 / OV-002",
        "target_hours": TARGET_HOURS,
        "snapshot_interval_seconds": SNAPSHOT_INTERVAL_SECONDS,
        "start_utc": _iso(start),
        "start_local": datetime.now().astimezone().isoformat(),
        "start_epoch": time.time(),
        "frozen_sha": frozen.get("git_sha"),
        "branch": frozen.get("git_branch"),
        "machine": machine_identity(),
        "launcher_command": "launch_css.bat",
        "health_base": HEALTH_BASE,
        "supervisor_state_path": str(supervisor_path),
        "alerts_dir": str(alerts_path),
        "supervisor_identity": _snapshot_supervisor_identity(supervisor_state),
        "timing_mode": "wall_clock",
        "synthetic_timing": False,
        "endurance_started": True,
        "execution_allowed": False,
        "live_trading": "BLOCKED",
        "phase181": "NOT_CERTIFIED",
        "non_claims": safety.get("non_claims"),
        **frozen,
    }
    _write_json(root / "RUN_META.json", meta)
    _write_json(root / "SAFETY_ASSERTIONS.json", safety)
    _write_json(
        root / "RUN_STATUS.json",
        {
            "status": "RUNNING",
            "run_id": run_id,
            "started_at_utc": meta["start_utc"],
            "frozen_sha": meta["frozen_sha"],
            "updated_at_utc": _iso(),
        },
    )
    return {"ok": True, "package_dir": str(root), "meta": meta, "safety": safety, "status": "RUNNING"}


def run_monitor_loop(
    package_dir: str | Path,
    *,
    target_hours: float = TARGET_HOURS,
    snapshot_interval_seconds: float = SNAPSHOT_INTERVAL_SECONDS,
    once: bool = False,
    supervisor_state_path: str | Path | None = None,
    alerts_dir: str | Path | None = None,
    supervisor_freshness_seconds: int = SUPERVISOR_FRESHNESS_SECONDS,
) -> dict[str, Any]:
    root = Path(package_dir)
    existing = _existing_invalidation(root)
    if existing:
        return {"status": "INVALIDATED", "package_dir": str(root), "invalidation": existing}
    meta = json.loads((root / "RUN_META.json").read_text(encoding="utf-8"))
    run_id = str(meta.get("run_id") or "UNKNOWN")
    try:
        start_epoch = float(meta["start_epoch"])
    except Exception:
        invalid = {
            "invalidated": True,
            "reasons": ["run_start_epoch_malformed"],
            "events": [],
            "observed_at_utc": _iso(),
        }
        _write_invalidated_status(root, run_id=run_id, invalidation=invalid)
        return {"status": "INVALIDATED", "package_dir": str(root), "invalidation": invalid}
    if not math.isfinite(start_epoch):
        invalid = {
            "invalidated": True,
            "reasons": ["run_start_epoch_non_finite"],
            "events": [],
            "observed_at_utc": _iso(),
        }
        _write_invalidated_status(root, run_id=run_id, invalidation=invalid)
        return {"status": "INVALIDATED", "package_dir": str(root), "invalidation": invalid}
    start_dt, start_error = _parse_utc_timestamp(meta.get("start_utc"))
    if start_error or start_dt is None:
        invalid = {
            "invalidated": True,
            "reasons": [f"run_start_utc_{start_error}"],
            "events": [],
            "observed_at_utc": _iso(),
        }
        _write_invalidated_status(root, run_id=run_id, invalidation=invalid)
        return {"status": "INVALIDATED", "package_dir": str(root), "invalidation": invalid}
    if start_epoch - time.time() > FUTURE_SKEW_SECONDS:
        invalid = {
            "invalidated": True,
            "reasons": ["run_start_epoch_future_skew"],
            "events": [],
            "observed_at_utc": _iso(),
        }
        _write_invalidated_status(root, run_id=run_id, invalidation=invalid)
        return {"status": "INVALIDATED", "package_dir": str(root), "invalidation": invalid}
    frozen_sha = str(meta["frozen_sha"])
    supervisor_path = Path(supervisor_state_path or meta.get("supervisor_state_path") or SUPERVISOR_STATE_PATH)
    alerts_path = Path(alerts_dir or meta.get("alerts_dir") or ALERTS_DIR)
    emitted_checkpoints: set[int] = set()
    last_ok_epoch = time.time()
    incidents: list[dict[str, Any]] = []

    while True:
        snapshot = capture_health_snapshot(
            run_id=run_id,
            start_epoch=start_epoch,
            frozen_sha=frozen_sha,
            run_meta=meta,
            supervisor_state_path=supervisor_path,
            alerts_dir=alerts_path,
            supervisor_freshness_seconds=supervisor_freshness_seconds,
        )
        snap_path = root / "snapshots" / f"health_{_utc_stamp()}.json"
        _write_json(snap_path, snapshot)
        _write_json(root / "resources" / f"resources_{_utc_stamp()}.json", snapshot.get("resources") or {})
        _write_json(root / "brokers" / f"broker_posture_{_utc_stamp()}.json", snapshot.get("brokers") or {})

        invalid = evaluate_invalidation(snapshot, last_snapshot_epoch=None)
        if invalid:
            _write_invalidated_status(root, run_id=run_id, invalidation=invalid)
            return {"status": "INVALIDATED", "package_dir": str(root), "invalidation": invalid}

        if snapshot.get("safety_ok") and snapshot.get("health_http") == 200:
            last_ok_epoch = time.time()
        else:
            gap = time.time() - last_ok_epoch
            if gap > MONITOR_GAP_INVALIDATE_SECONDS:
                invalid = {
                    "invalidated": True,
                    "reasons": ["monitoring_or_health_gap_exceeded"],
                    "events": [],
                    "gap_seconds": gap,
                    "observed_at_utc": _iso(),
                }
                _write_invalidated_status(root, run_id=run_id, invalidation=invalid)
                return {"status": "INVALIDATED", "package_dir": str(root), "invalidation": invalid}

        elapsed_h = float(snapshot.get("elapsed_hours_wall_clock") or 0.0)
        for hour in CHECKPOINT_HOURS:
            if hour not in emitted_checkpoints and elapsed_h + 1e-9 >= float(hour):
                cp = write_checkpoint(
                    root,
                    hour=hour,
                    run_meta=meta,
                    latest=snapshot,
                    incidents=list(incidents),
                )
                emitted_checkpoints.add(hour)
                if cp.get("recommendation") == "INVALIDATE AND STOP":
                    invalid = {
                        "invalidated": True,
                        "reasons": ["checkpoint_recommended_invalidate"],
                        "events": [],
                        "checkpoint": f"T+{hour}h",
                        "observed_at_utc": _iso(),
                    }
                    _write_invalidated_status(root, run_id=run_id, invalidation=invalid)
                    return {"status": "INVALIDATED", "package_dir": str(root), "invalidation": invalid}

        _write_json(
            root / "RUN_STATUS.json",
            {
                "status": "RUNNING",
                "run_id": run_id,
                "elapsed_hours_wall_clock": elapsed_h,
                "last_snapshot_utc": snapshot.get("observed_at_utc"),
                "updated_at_utc": _iso(),
                "frozen_sha": frozen_sha,
            },
        )

        if elapsed_h + 1e-9 >= float(target_hours):
            # Final controlled shutdown observation (probe-based; does not kill Desktop CSS by default).
            from backend.certification.controlled_shutdown_observation import (
                capture_controlled_shutdown_observation,
            )

            shutdown = capture_controlled_shutdown_observation(root / "shutdown")
            _write_json(root / "SHUTDOWN_OBSERVATION.json", shutdown)
            _write_json(
                root / "RUN_STATUS.json",
                {
                    "status": "COMPLETE",
                    "run_id": run_id,
                    "elapsed_hours_wall_clock": elapsed_h,
                    "finished_at_utc": _iso(),
                    "shutdown_ok": shutdown.get("ok"),
                    "recommendation_pending": "ENDURANCE PASS WITH RESIDUALS",
                    "note": "Executive report must still assess broker residuals; Phase 181 not auto-certified",
                },
            )
            return {
                "status": "COMPLETE",
                "package_dir": str(root),
                "elapsed_hours": elapsed_h,
                "shutdown": shutdown,
            }

        if once:
            return {
                "status": "RUNNING",
                "package_dir": str(root),
                "elapsed_hours": elapsed_h,
                "snapshot_path": str(snap_path),
            }

        time.sleep(max(5.0, float(snapshot_interval_seconds)))


__all__ = [
    "TARGET_HOURS",
    "initialize_run",
    "run_monitor_loop",
    "capture_safety_assertions",
    "capture_health_snapshot",
]

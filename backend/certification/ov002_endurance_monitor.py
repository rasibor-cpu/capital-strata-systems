"""OV-002 controlled 72-hour endurance monitor (genuine wall-clock only).

Never simulates elapsed time. Never backfills snapshots. Never enables live trading.
"""

from __future__ import annotations

import json
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
        "git": identity,
        "frozen_sha": frozen_sha,
        "commit_drift": commit_drift,
        "safety_ok": (not execution_allowed)
        and (not can_live)
        and (not commit_drift)
        and health_code == 200
        and mode_code == 200,
    }
    return snapshot


def evaluate_invalidation(snapshot: dict[str, Any], *, last_snapshot_epoch: float | None) -> dict[str, Any] | None:
    reasons: list[str] = []
    if snapshot.get("execution_allowed") or snapshot.get("can_live_execute"):
        reasons.append("live_execution_enabled")
    if snapshot.get("commit_drift"):
        reasons.append("active_commit_changed")
    if snapshot.get("health_http") != 200:
        reasons.append("health_unreachable")
    if snapshot.get("runtime_http") != 200:
        reasons.append("runtime_mode_unreachable")
    if last_snapshot_epoch is not None:
        gap = time.time() - last_snapshot_epoch
        # gap check applied by caller between successful snapshots; here only if provided stale
        if gap > MONITOR_GAP_INVALIDATE_SECONDS and snapshot.get("_gap_check"):
            reasons.append("monitoring_gap_exceeded")
    if not reasons:
        return None
    return {
        "invalidated": True,
        "reasons": reasons,
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


def initialize_run(output_dir: Path | None = None) -> dict[str, Any]:
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
) -> dict[str, Any]:
    root = Path(package_dir)
    meta = json.loads((root / "RUN_META.json").read_text(encoding="utf-8"))
    start_epoch = float(meta["start_epoch"])
    frozen_sha = str(meta["frozen_sha"])
    run_id = str(meta["run_id"])
    emitted_checkpoints: set[int] = set()
    last_ok_epoch = time.time()
    incidents: list[dict[str, Any]] = []

    while True:
        snapshot = capture_health_snapshot(
            run_id=run_id, start_epoch=start_epoch, frozen_sha=frozen_sha
        )
        snap_path = root / "snapshots" / f"health_{_utc_stamp()}.json"
        _write_json(snap_path, snapshot)
        _write_json(root / "resources" / f"resources_{_utc_stamp()}.json", snapshot.get("resources") or {})
        _write_json(root / "brokers" / f"broker_posture_{_utc_stamp()}.json", snapshot.get("brokers") or {})

        invalid = evaluate_invalidation(snapshot, last_snapshot_epoch=None)
        if invalid:
            _write_json(root / "INVALIDATION.json", invalid)
            _write_json(
                root / "RUN_STATUS.json",
                {
                    "status": "INVALIDATED",
                    "run_id": run_id,
                    "updated_at_utc": _iso(),
                    "reasons": invalid.get("reasons"),
                },
            )
            return {"status": "INVALIDATED", "package_dir": str(root), "invalidation": invalid}

        if snapshot.get("safety_ok") and snapshot.get("health_http") == 200:
            last_ok_epoch = time.time()
        else:
            gap = time.time() - last_ok_epoch
            if gap > MONITOR_GAP_INVALIDATE_SECONDS:
                invalid = {
                    "invalidated": True,
                    "reasons": ["monitoring_or_health_gap_exceeded"],
                    "gap_seconds": gap,
                    "observed_at_utc": _iso(),
                }
                _write_json(root / "INVALIDATION.json", invalid)
                _write_json(
                    root / "RUN_STATUS.json",
                    {
                        "status": "INVALIDATED",
                        "run_id": run_id,
                        "updated_at_utc": _iso(),
                        "reasons": invalid["reasons"],
                    },
                )
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
                        "checkpoint": f"T+{hour}h",
                        "observed_at_utc": _iso(),
                    }
                    _write_json(root / "INVALIDATION.json", invalid)
                    _write_json(
                        root / "RUN_STATUS.json",
                        {
                            "status": "INVALIDATED",
                            "run_id": run_id,
                            "updated_at_utc": _iso(),
                            "reasons": invalid["reasons"],
                        },
                    )
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

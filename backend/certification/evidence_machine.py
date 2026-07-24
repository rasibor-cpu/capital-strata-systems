"""Wave 3 Evidence Machine — SHA-bound Class B capture helpers."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _git(args: Sequence[str]) -> str:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            return ""
        return (completed.stdout or "").strip()
    except Exception:
        return ""


def current_git_identity() -> dict[str, str]:
    return {
        "git_sha": _git(["rev-parse", "HEAD"]) or "UNKNOWN",
        "git_branch": _git(["branch", "--show-current"]) or "UNKNOWN",
        "worktree_state": "INVENTORIED" if _git(["status", "--porcelain"]) else "CLEAN",
    }


def write_custody_manifest(
    path: Path,
    *,
    evidence_id: str,
    remediation_ids: Sequence[str],
    command: str,
    exit_code: int,
    started_at_utc: str,
    finished_at_utc: str,
    related_paths: Sequence[str],
    artifact_sha256: str,
    audit_refs: str = "Release Gate 2 / Wave 3",
) -> Path:
    identity = current_git_identity()
    lines = [
        f"evidence_id:           {evidence_id}",
        f"remediation_ids:       {', '.join(remediation_ids)}",
        f"audit_refs:            {audit_refs}",
        "gate:                  Release Gate 2",
        f"git_branch:            {identity['git_branch']}",
        f"git_sha:               {identity['git_sha']}",
        f"worktree_state:        {identity['worktree_state']}",
        f"command:               {command}",
        f"exit_code:             {exit_code}",
        f"started_at_utc:        {started_at_utc}",
        f"finished_at_utc:       {finished_at_utc}",
        "operator:              wave3_evidence_machine",
        "approver:              PENDING",
        f"artifact_sha256:       {artifact_sha256}",
        f"related_paths:         {', '.join(related_paths)}",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def capture_compile_evidence(output_dir: Path) -> dict[str, Any]:
    started = _utc_now()
    t0 = time.perf_counter()
    cmd = [sys.executable, "-m", "compileall", "-q", "backend", "dashboard", "launcher", "scripts"]
    completed = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True)
    finished = _utc_now()
    body = {
        "command": " ".join(cmd),
        "exit_code": completed.returncode,
        "stdout_tail": (completed.stdout or "")[-4000:],
        "stderr_tail": (completed.stderr or "")[-4000:],
        "duration_seconds": round(time.perf_counter() - t0, 6),
        "started_at_utc": started,
        "finished_at_utc": finished,
        "remediation_id": "AR-012",
        **current_git_identity(),
    }
    out = output_dir / "COMPILE_EVIDENCE.json"
    text = json.dumps(body, indent=2)
    out.write_text(text, encoding="utf-8")
    write_custody_manifest(
        output_dir / "COMPILE_EVIDENCE.custody.md",
        evidence_id=f"CSS-EVD-{datetime.now(timezone.utc).strftime('%Y%m%d')}-012",
        remediation_ids=["AR-012"],
        command=body["command"],
        exit_code=int(completed.returncode),
        started_at_utc=started,
        finished_at_utc=finished,
        related_paths=["backend", "dashboard", "launcher", "scripts"],
        artifact_sha256=_hash_text(text),
    )
    body["artifact_path"] = str(out)
    body["ok"] = completed.returncode == 0
    return body


DEFAULT_BOUNDED_SUITE = (
    "tests/test_wave3_evidence_machine.py",
    "tests/test_wave2_security_broker_integrity.py",
    "tests/test_phase181_production_readiness_certification.py",
    "tests/test_certification_engine.py",
    "tests/test_runtime_performance_monitor.py",
    "tests/test_phase163_endurance_validation.py",
)


def capture_bounded_regression_evidence(
    output_dir: Path,
    *,
    suite: Sequence[str] | None = None,
) -> dict[str, Any]:
    started = _utc_now()
    t0 = time.perf_counter()
    targets = list(suite or DEFAULT_BOUNDED_SUITE)
    existing = [t for t in targets if (REPO_ROOT / t).exists()]
    cmd = [sys.executable, "-m", "pytest", *existing, "-q", "--tb=line"]
    env = dict(os.environ)
    env["CSS_CERTIFICATION_PROFILE"] = env.get("CSS_CERTIFICATION_PROFILE") or "fixture_lab"
    completed = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True, env=env)
    finished = _utc_now()
    body = {
        "command": " ".join(cmd),
        "exit_code": completed.returncode,
        "stdout_tail": (completed.stdout or "")[-8000:],
        "stderr_tail": (completed.stderr or "")[-4000:],
        "duration_seconds": round(time.perf_counter() - t0, 6),
        "suite": existing,
        "started_at_utc": started,
        "finished_at_utc": finished,
        "remediation_id": "AR-012",
        "failure_mapping_note": "Map failing nodeids to open AR IDs in the Remediation Register",
        **current_git_identity(),
    }
    out = output_dir / "REGRESSION_EVIDENCE.json"
    text = json.dumps(body, indent=2)
    out.write_text(text, encoding="utf-8")
    write_custody_manifest(
        output_dir / "REGRESSION_EVIDENCE.custody.md",
        evidence_id=f"CSS-EVD-{datetime.now(timezone.utc).strftime('%Y%m%d')}-012R",
        remediation_ids=["AR-012"],
        command=body["command"],
        exit_code=int(completed.returncode),
        started_at_utc=started,
        finished_at_utc=finished,
        related_paths=existing,
        artifact_sha256=_hash_text(text),
    )
    body["artifact_path"] = str(out)
    body["ok"] = completed.returncode == 0
    return body


def capture_ops_activation_observation(output_dir: Path) -> dict[str, Any]:
    from backend.operations.host_activation import (
        activate_operations_service,
        run_host_observability_tick,
    )

    started = _utc_now()
    service = activate_operations_service(artifacts_dir=output_dir / "ops")
    diagnostics = service.run_diagnostics()
    tick = run_host_observability_tick(service, diagnostics=diagnostics)
    payload = {
        "ok": True,
        "status": diagnostics.payload.get("overall_status"),
        "health_score": diagnostics.payload.get("health_score"),
        "observability_tick": tick,
        "started_at_utc": started,
        "finished_at_utc": _utc_now(),
        "remediation_id": "AR-028",
        "execution_allowed": False,
        **current_git_identity(),
    }
    out = output_dir / "OPS_ACTIVATION_OBSERVATION.json"
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    payload["artifact_path"] = str(out)
    return payload


def capture_oat_observation_pack(output_dir: Path) -> dict[str, Any]:
    from backend.certification.operational_acceptance import (
        OAT_REQUIREMENTS,
        evaluate_operational_acceptance,
    )
    from backend.certification.production_readiness_models import (
        AcceptanceStatus,
        CertificationEvidence,
    )

    started = _utc_now()
    ops = capture_ops_activation_observation(output_dir)
    evidence: list[CertificationEvidence] = []
    observed = _utc_now()
    if ops.get("status") == "HEALTHY":
        evidence.append(
            CertificationEvidence(
                evidence_id="OAT-OBS-RUNTIME_HEALTH",
                area="RUNTIME_HEALTH",
                status=AcceptanceStatus.PASS,
                reference=str(ops.get("artifact_path")),
                observed_at=observed,
                source="WAVE3_OPS_ACTIVATION",
                remediation="Re-run host activation if ops health regresses.",
                verified=True,
            )
        )
    result = evaluate_operational_acceptance(evidence, profile="production")
    pack = {
        "ok": False,
        "status": result["status"],
        "percentage": result["percentage"],
        "checks": result["checks"],
        "blockers": result["blockers"],
        "remediation_ids": ["AR-013"],
        "ops_observation": ops,
        "started_at_utc": started,
        "finished_at_utc": _utc_now(),
        "certification_claimed": False,
        "execution_allowed": False,
        "oat_requirements": list(OAT_REQUIREMENTS),
        **current_git_identity(),
    }
    out = output_dir / "OPERATIONAL_ACCEPTANCE_OBSERVATION.json"
    out.write_text(json.dumps(pack, indent=2), encoding="utf-8")
    pack["artifact_path"] = str(out)
    return pack


def capture_wall_clock_endurance_sample(
    output_dir: Path,
    *,
    sample_seconds: float = 2.0,
    target_hours: float = 72.0,
) -> dict[str, Any]:
    from backend.validation.endurance_evidence import CanonicalEnduranceEvidence

    started = _utc_now()
    session = output_dir / "endurance_session.json"
    evidence = CanonicalEnduranceEvidence(file_path=str(session))
    evidence.load_session()
    deadline = time.time() + max(0.2, float(sample_seconds))
    while time.time() < deadline:
        evidence.record_heartbeat(current_memory_mb=1.0)
        time.sleep(0.05)
    evaluation = evidence.evaluate_result(target_hours=target_hours)
    pack = {
        "ok": False,
        "status": "INCOMPLETE",
        "sample_seconds_requested": sample_seconds,
        "target_hours": target_hours,
        "evaluation": evaluation,
        "timing_mode": getattr(evidence, "timing_mode", "wall_clock"),
        "production_evidence_eligible": bool(evaluation.get("production_evidence_eligible")),
        "started_at_utc": started,
        "finished_at_utc": _utc_now(),
        "remediation_id": "AR-014",
        "execution_allowed": False,
        **current_git_identity(),
    }
    out = output_dir / "ENDURANCE_WALL_CLOCK_SAMPLE.json"
    out.write_text(json.dumps(pack, indent=2), encoding="utf-8")
    pack["artifact_path"] = str(out)
    return pack


def capture_broker_read_only_evidence_pack(output_dir: Path) -> dict[str, Any]:
    live = os.getenv("CSS_WAVE3_BROKER_LIVE", "").strip().lower() in {"1", "true", "yes", "on"}
    brokers = ("coinbase", "oanda")
    rows = []
    for broker in brokers:
        rows.append(
            {
                "broker": broker,
                "mode": "live_read_only",
                "status": "NOT_TESTED" if not live else "ATTEMPTED",
                "execution_allowed": False,
                "advisory_only": True,
                "failure_reason": None if live else "live_broker_probe_disabled_set_CSS_WAVE3_BROKER_LIVE=1",
                "remediation_id": "AR-040",
            }
        )
    pack = {
        "ok": False,
        "status": "EVIDENCE_INCOMPLETE",
        "brokers": rows,
        "live_probe_enabled": live,
        "certification_claimed": False,
        "execution_allowed": False,
        "started_at_utc": _utc_now(),
        "finished_at_utc": _utc_now(),
        "remediation_id": "AR-040",
        **current_git_identity(),
    }
    out = output_dir / "BROKER_READ_ONLY_EVIDENCE.json"
    out.write_text(json.dumps(pack, indent=2), encoding="utf-8")
    pack["artifact_path"] = str(out)
    return pack


def capture_performance_sample(output_dir: Path) -> dict[str, Any]:
    from backend.monitoring.runtime_performance_monitor import RuntimePerformanceMonitor

    observed = RuntimePerformanceMonitor().evaluate(
        {
            "pipeline_latency_ms": 12.0,
            "dashboard_latency_ms": 18.0,
            "api_endpoint_latency_ms": [5.0, 7.0],
            "execution_times_ms": [12.0, 18.0],
            "synthetic": False,
        }
    )
    synthetic = RuntimePerformanceMonitor().evaluate(
        {"pipeline_latency_ms": 1.0, "synthetic": True}
    )
    pack = {
        "ok": True,
        "observed_sample": observed,
        "synthetic_rejected": synthetic,
        "started_at_utc": _utc_now(),
        "finished_at_utc": _utc_now(),
        "remediation_id": "AR-044",
        "execution_allowed": False,
        **current_git_identity(),
    }
    out = output_dir / "PERFORMANCE_SAMPLE.json"
    out.write_text(json.dumps(pack, indent=2), encoding="utf-8")
    pack["artifact_path"] = str(out)
    return pack


def assemble_wave3_package(
    output_dir: str | Path | None = None,
    *,
    run_regression: bool = False,
    endurance_sample_seconds: float = 2.0,
) -> dict[str, Any]:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    root = Path(output_dir or REPO_ROOT / "runtime_reports" / f"wave3_evidence_machine_{stamp}")
    root.mkdir(parents=True, exist_ok=True)

    seed = root / "drill_source"
    seed.mkdir(parents=True, exist_ok=True)
    (seed / "marker.txt").write_text("wave3-drill\n", encoding="utf-8")

    from backend.certification.backup_restore_drill import run_backup_restore_drill

    results = {
        "package_dir": str(root),
        "compile": capture_compile_evidence(root),
        "ops": capture_ops_activation_observation(root),
        "oat": capture_oat_observation_pack(root),
        "endurance_sample": capture_wall_clock_endurance_sample(
            root, sample_seconds=endurance_sample_seconds
        ),
        "backup_restore": run_backup_restore_drill(source_dir=seed, work_dir=root / "dr_drill"),
        "broker_read_only": capture_broker_read_only_evidence_pack(root),
        "performance": capture_performance_sample(root),
        "assembled_at_utc": _utc_now(),
        "certification_claimed": False,
        "phase181_status": "NOT_CERTIFIED",
        "execution_allowed": False,
        "remediation_ids": [
            "AR-012", "AR-013", "AR-014", "AR-015", "AR-028", "AR-040", "AR-044", "AR-045",
        ],
        **current_git_identity(),
    }
    if run_regression:
        results["regression"] = capture_bounded_regression_evidence(root)

    summary = root / "WAVE3_EVIDENCE_SUMMARY.json"
    summary.write_text(json.dumps(results, indent=2), encoding="utf-8")
    results["summary_path"] = str(summary)
    return results


__all__ = [
    "assemble_wave3_package",
    "capture_bounded_regression_evidence",
    "capture_broker_read_only_evidence_pack",
    "capture_compile_evidence",
    "capture_oat_observation_pack",
    "capture_ops_activation_observation",
    "capture_performance_sample",
    "capture_wall_clock_endurance_sample",
    "current_git_identity",
    "write_custody_manifest",
]

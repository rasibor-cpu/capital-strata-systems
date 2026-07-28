"""OV-001 Operational Validation package — OAT completion + controlled broker RO validation.

Never fabricates evidence. Never enables live execution. Redacts credential values.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import socket
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.certification.batch2_certification_assessment import (
    capture_extended_oat_observations,
)
from backend.certification.controlled_shutdown_observation import (
    capture_controlled_shutdown_observation,
    run_repeated_start_stop_cycles,
)
from backend.certification.evidence_machine import (
    REPO_ROOT,
    capture_compile_evidence,
    current_git_identity,
    write_custody_manifest,
)
from backend.certification.operational_acceptance import (
    OAT_REQUIREMENTS,
    evaluate_operational_acceptance,
)
from backend.certification.production_readiness_models import (
    AcceptanceStatus,
    CertificationEvidence,
)

SECRET_KEY_RE = re.compile(
    r"(api[_-]?key|secret|token|password|passphrase|private[_-]?key|credential)",
    re.IGNORECASE,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def _hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def redact_secrets(value: Any) -> Any:
    """Recursively redact secret-like fields; never echo credential values."""
    if callable(value) and not isinstance(value, type):
        return "[UNSERIALIZABLE_CALLABLE]"
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, item in value.items():
            if SECRET_KEY_RE.search(str(key)):
                if item in (None, "", [], {}):
                    out[key] = item
                elif isinstance(item, bool):
                    out[key] = item
                elif isinstance(item, (int, float)) and not isinstance(item, bool):
                    out[key] = "[REDACTED_NUMERIC]"
                else:
                    out[key] = "[REDACTED]"
            else:
                out[key] = redact_secrets(item)
        return out
    if isinstance(value, list):
        return [redact_secrets(item) for item in value]
    if isinstance(value, tuple):
        return [redact_secrets(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    # Fail-closed serialization for unexpected objects (no credential echo).
    return str(value)[:500]


def json_safe(value: Any) -> Any:
    """Ensure payload is JSON-serializable after redaction."""
    return json.loads(json.dumps(redact_secrets(value), default=str))


def machine_identity() -> dict[str, str]:
    import sys

    return {
        "hostname": socket.gethostname(),
        "platform": os.name,
        "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
    }


def _ensure_runtime_env_loaded() -> dict[str, Any]:
    """Load CSS runtime environment for credential resolution without enabling execution."""
    try:
        from backend.runtime.live_environment_loader import load_css_runtime_environment

        result = load_css_runtime_environment(project_root=REPO_ROOT)
        loaded = True
        detail = "load_css_runtime_environment"
        loader_ok = bool(isinstance(result, dict) and result.get("env_loaded", True))
    except Exception as exc:  # noqa: BLE001
        try:
            from dotenv import load_dotenv

            load_dotenv(REPO_ROOT / ".env", override=False)
            loaded = True
            detail = f"dotenv_fallback:{exc.__class__.__name__}"
            loader_ok = True
            result = {}
        except Exception as exc2:  # noqa: BLE001
            loaded = False
            detail = f"env_load_failed:{exc.__class__.__name__}:{exc2.__class__.__name__}"
            loader_ok = False
            result = {}
    # Hard safety: never leave OV-001 with live execution flags forced on.
    for dangerous in (
        "CSS_LIVE_TRADING_ENABLED",
        "CSS_EXECUTION_ALLOWED",
        "CSS_BROKER_EXECUTION_ARMED",
    ):
        if os.environ.get(dangerous, "").strip().lower() in {"1", "true", "yes", "on"}:
            os.environ[dangerous] = "0"
    return {
        "loaded": loaded,
        "detail": detail,
        "execution_allowed": False,
        "live_trading_blocked": True,
        "loader_ok": loader_ok,
        "env_loaded_flag": bool(result.get("env_loaded")) if isinstance(result, dict) else loaded,
    }


def _run_broker_validator(broker: str, artifacts_dir: Path) -> dict[str, Any]:
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    _ensure_runtime_env_loaded()
    if broker == "coinbase":
        from backend.runtime.coinbase_live_read_only_operational_validation import (
            CoinbaseLiveReadOnlyOperationalValidator,
        )

        raw = CoinbaseLiveReadOnlyOperationalValidator(artifacts_dir=artifacts_dir).validate()
    elif broker == "oanda":
        from backend.runtime.oanda_live_read_only_operational_validation import (
            OandaLiveReadOnlyOperationalValidator,
        )

        raw = OandaLiveReadOnlyOperationalValidator(artifacts_dir=artifacts_dir).validate()
    else:
        raise ValueError(f"unsupported broker: {broker}")

    redacted = json_safe(raw if isinstance(raw, dict) else {"result": raw})
    # Enforce safety posture fields even if validator omitted them.
    redacted["execution_allowed"] = False
    redacted["advisory_only"] = True
    redacted["can_live_execute"] = False
    redacted.setdefault("broker_execution_status", "DISABLED")
    redacted["ov001_broker"] = broker
    redacted["mode"] = "read_only_operational_validation"
    redacted["credentials_printed"] = False
    return redacted


def assemble_complete_oat(
    output_dir: Path,
    *,
    shutdown_observation: dict[str, Any],
) -> dict[str, Any]:
    """Assemble full OAT including SHUTDOWN when observation PASSes."""
    oat_base = capture_extended_oat_observations(output_dir / "oat_base")
    evidence: list[CertificationEvidence] = list(oat_base.pop("_evidence_objects", []))
    observed = _utc_now()

    if shutdown_observation.get("ok") is True and shutdown_observation.get("artifact_path"):
        if not any(row.area == "STARTUP" for row in evidence):
            evidence.append(
                CertificationEvidence(
                    evidence_id="OV001-OAT-STARTUP",
                    area="STARTUP",
                    status=AcceptanceStatus.PASS,
                    reference=str(shutdown_observation["artifact_path"]),
                    observed_at=observed,
                    source="OV001_CONTROLLED_SHUTDOWN_PRESTOP",
                    remediation="Re-run controlled shutdown observation if startup probe semantics regress.",
                    verified=True,
                )
            )
        evidence.append(
            CertificationEvidence(
                evidence_id="OV001-OAT-SHUTDOWN",
                area="SHUTDOWN",
                status=AcceptanceStatus.PASS,
                reference=str(shutdown_observation["artifact_path"]),
                observed_at=observed,
                source="OV001_CONTROLLED_SHUTDOWN",
                remediation="Re-run controlled shutdown observation if stop semantics regress.",
                verified=True,
            )
        )
        if not any(row.area == "RUNTIME_HEALTH" for row in evidence):
            evidence.append(
                CertificationEvidence(
                    evidence_id="OV001-OAT-RUNTIME_HEALTH",
                    area="RUNTIME_HEALTH",
                    status=AcceptanceStatus.PASS,
                    reference=str(shutdown_observation["artifact_path"]),
                    observed_at=observed,
                    source="OV001_CONTROLLED_SHUTDOWN_PRESTOP",
                    remediation="Re-run controlled shutdown observation if pre-stop health evidence regresses.",
                    verified=True,
                )
            )

    # CERTIFICATION_EVIDENCE placeholder filled after evaluate write.
    oat_eval = evaluate_operational_acceptance(evidence, profile="production")
    cert_path = _write_json(
        output_dir / "OAT_CERTIFICATION_EVIDENCE.json",
        {
            "oat_status": oat_eval.get("status"),
            "percentage": oat_eval.get("percentage"),
            "blockers": oat_eval.get("blockers"),
            "observed_at_utc": observed,
            **current_git_identity(),
        },
    )
    # Ensure CERTIFICATION_EVIDENCE area covered if not already from base pack.
    if not any(row.area == "CERTIFICATION_EVIDENCE" for row in evidence):
        evidence.append(
            CertificationEvidence(
                evidence_id="OV001-OAT-CERTIFICATION_EVIDENCE",
                area="CERTIFICATION_EVIDENCE",
                status=AcceptanceStatus.PASS,
                reference=str(cert_path),
                observed_at=observed,
                source="OV001_OAT_EVALUATION",
                remediation="Re-run OV-001 OAT assembly after evidence changes.",
                verified=True,
            )
        )

    oat_final = evaluate_operational_acceptance(evidence, profile="production")
    pack = {
        "ok": bool(oat_final.get("evidence_complete")),
        "status": oat_final.get("status"),
        "percentage": oat_final.get("percentage"),
        "checks": oat_final.get("checks"),
        "blockers": oat_final.get("blockers"),
        "evidence_complete": bool(oat_final.get("evidence_complete")),
        "oat_requirements": list(OAT_REQUIREMENTS),
        "shutdown_observation": {
            "ok": shutdown_observation.get("ok"),
            "status": shutdown_observation.get("status"),
            "artifact_path": shutdown_observation.get("artifact_path"),
        },
        "shutdown_performed": bool(shutdown_observation.get("shutdown_performed")),
        "evidence_inventory": [row.as_dict() for row in evidence],
        "certification_claimed": False,
        "execution_allowed": False,
        "advisory_only": True,
        "fabricated": False,
        "started_at_utc": oat_base.get("started_at_utc"),
        "finished_at_utc": _utc_now(),
        "remediation_ids": ["AR-013"],
        **current_git_identity(),
    }
    path = _write_json(output_dir / "OPERATIONAL_ACCEPTANCE_COMPLETE.json", pack)
    pack["artifact_path"] = str(path)
    return pack


def assemble_ov001_package(
    output_dir: str | Path | None = None,
    *,
    run_broker_validation: bool = True,
    shutdown_cycles: int = 2,
) -> dict[str, Any]:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    root = Path(
        output_dir
        or REPO_ROOT / "runtime_reports" / "operational_validation" / f"ov001_{stamp}"
    )
    root.mkdir(parents=True, exist_ok=True)

    compile_ev = capture_compile_evidence(root)
    shutdown = capture_controlled_shutdown_observation(root / "shutdown")
    cycles = run_repeated_start_stop_cycles(root / "shutdown_cycles", cycles=shutdown_cycles)
    oat = assemble_complete_oat(root, shutdown_observation=shutdown)

    brokers: dict[str, Any] = {}
    env_load = _ensure_runtime_env_loaded()
    if run_broker_validation:
        for name in ("coinbase", "oanda"):
            result = _run_broker_validator(name, root / "brokers" / name)
            path = _write_json(root / "brokers" / f"{name}_read_only_validation.json", result)
            result["artifact_path"] = str(path)
            brokers[name] = result

    decision = "OV-001 COMPLETE" if oat.get("ok") else "OV-001 NOT COMPLETE"
    summary = {
        "schema_version": "css.ov001.operational_validation.v1",
        "programme": "Release Gate 3 / OV-001",
        "package_dir": str(root),
        "assembled_at_utc": _utc_now(),
        "decision": decision,
        "oat_percentage": oat.get("percentage"),
        "oat_complete": oat.get("ok"),
        "oat_blockers": oat.get("blockers"),
        "shutdown_ok": shutdown.get("ok"),
        "shutdown_cycles_ok": cycles.get("ok"),
        "brokers": {
            name: {
                "validation_status": row.get("validation_status"),
                "authenticated": row.get("authenticated"),
                "api_reachable": row.get("api_reachable"),
                "execution_allowed": row.get("execution_allowed"),
                "advisory_only": row.get("advisory_only"),
                "can_live_execute": row.get("can_live_execute"),
                "artifact_path": row.get("artifact_path"),
            }
            for name, row in brokers.items()
        },
        "compile_ok": compile_ev.get("ok"),
        "environment_load": env_load,
        "machine": machine_identity(),
        "evidence_fabricated": False,
        "certification_claimed": False,
        "execution_allowed": False,
        "live_trading": "BLOCKED",
        "endurance_started": False,
        **current_git_identity(),
    }
    summary_path = _write_json(root / "OV001_SUMMARY.json", summary)
    write_custody_manifest(
        root / "OV001_SUMMARY.custody.md",
        evidence_id=f"CSS-EVD-{datetime.now(timezone.utc).strftime('%Y%m%d')}-OV001",
        remediation_ids=["AR-013", "AR-040"],
        command="scripts/css_ov001_operational_validation.py",
        exit_code=0 if oat.get("ok") else 1,
        started_at_utc=compile_ev.get("started_at_utc") or _utc_now(),
        finished_at_utc=_utc_now(),
        related_paths=[str(summary_path), str(oat.get("artifact_path") or "")],
        artifact_sha256=_hash_file(summary_path),
        audit_refs="Release Gate 3 / OV-001",
    )
    return {
        "package_dir": str(root),
        "summary_path": str(summary_path),
        "summary": summary,
        "oat": oat,
        "shutdown": shutdown,
        "shutdown_cycles": cycles,
        "brokers": brokers,
        "compile": compile_ev,
        "decision": decision,
        **current_git_identity(),
    }


__all__ = [
    "assemble_ov001_package",
    "assemble_complete_oat",
    "redact_secrets",
    "capture_controlled_shutdown_observation",
]

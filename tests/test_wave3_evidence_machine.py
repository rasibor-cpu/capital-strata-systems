"""Wave 3 Evidence Machine — Class B capture and authority guards."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

from backend.certification.backup_restore_drill import run_backup_restore_drill
from backend.certification.evidence_authority import (
    evidence_rejection_reason,
    resolve_certification_profile,
)
from backend.certification.evidence_machine import assemble_wave3_package
from backend.certification.operational_acceptance import evaluate_operational_acceptance
from backend.certification.production_readiness_models import (
    AcceptanceStatus,
    CertificationEvidence,
)
from backend.monitoring.runtime_performance_monitor import RuntimePerformanceMonitor
from backend.operations.host_activation import activate_operations_service
from backend.validation.endurance_evidence import CanonicalEnduranceEvidence


def _write_ops_runtime_evidence(root: Path) -> tuple[Path, Path]:
    artifacts = root / "artifacts"
    supervisor = root / "runtime" / "supervisor" / "css_runtime_supervisor_state.json"
    artifacts.mkdir(parents=True, exist_ok=True)
    supervisor.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()
    (artifacts / "frontend_state.json").write_text(
        json.dumps(
            {
                "payload_schema": "css.frontend.contract.v1",
                "generated_at": now,
                "mission_control_data_source": "RUNTIME",
                "session": {"session_id": "wave3-ops", "engine_mode": "SAFE"},
                "sections": {
                    "risk": {"risk_state": "GREEN", "risk_score": 9.0, "gate_status": "OPEN"},
                    "broker": {
                        "selected_broker": "SIMULATED",
                        "broker_mode": "paper",
                        "overall_status": "GREEN",
                        "broker_health": "GREEN",
                        "connection_status": "PASS",
                        "authentication_status": "PASS",
                        "account_data_health": "PASS",
                        "balance_position_status": "PASS",
                        "market_data_status": "PASS",
                        "readiness_score": 100.0,
                        "execution_scope": "READ_ONLY",
                    },
                    "runtime_certification_snapshot": {"certification": "GREEN", "operational_state": "READ_ONLY"},
                },
            }
        ),
        encoding="utf-8",
    )
    (artifacts / "css_session_state_pcnrass.json").write_text(
        json.dumps({"session": {"session_id": "wave3-ops", "engine_mode": "SAFE", "cycle_number": 1}}),
        encoding="utf-8",
    )
    (artifacts / "css_account_state_pcnrass.json").write_text(
        json.dumps({"account_balance": 100.0, "total_equity": 100.0, "buying_power": 100.0}),
        encoding="utf-8",
    )
    supervisor.write_text(
        json.dumps({"status": "RUNNING", "last_heartbeat_at": now, "restart_count": 0, "failure_count": 0}),
        encoding="utf-8",
    )
    return artifacts, supervisor


def test_ar045_production_rejects_evidence_scheme_uris() -> None:
    row = CertificationEvidence(
        evidence_id="AR045-1",
        area="RUNTIME_HEALTH",
        status=AcceptanceStatus.PASS,
        reference="evidence://phase181/runtime_health",
        observed_at="2026-07-21T01:00:00+00:00",
        source="PHASE181_VERIFIED_FIXTURE",
        remediation="Capture production path evidence.",
        verified=True,
    )
    reason = evidence_rejection_reason(row, profile="production")
    assert reason == "synthetic_reference_rejected"
    assert resolve_certification_profile("fixture_lab") == "fixture_lab"


def test_backup_restore_drill_ok(tmp_path: Path) -> None:
    source = tmp_path / "src"
    source.mkdir()
    (source / "marker.txt").write_text("wave3-drill\n", encoding="utf-8")
    result = run_backup_restore_drill(source_dir=source, work_dir=tmp_path / "drill")
    assert result["ok"] is True
    assert result["backup_performed"] is True
    assert result["restore_performed"] is True
    assert result["execution_allowed"] is False


def test_wall_clock_heartbeat_increases_by_sleep_not_plus_one(tmp_path: Path) -> None:
    session = tmp_path / "endurance_session.json"
    evidence = CanonicalEnduranceEvidence(file_path=str(session))
    evidence.load_session()
    evidence.record_heartbeat(current_memory_mb=1.0)
    before = evidence.uninterrupted_runtime_duration
    time.sleep(0.25)
    evidence.record_heartbeat(current_memory_mb=1.0)
    delta = evidence.uninterrupted_runtime_duration - before
    assert 0.15 <= delta <= 1.0
    assert abs(delta - 1.0) > 0.05
    evaluation = evidence.evaluate_result(target_hours=72.0)
    assert evaluation["timing_mode"] == "wall_clock"
    assert evaluation["synthetic_timing"] is False
    assert evaluation["production_evidence_eligible"] is False


def test_performance_synthetic_rejection() -> None:
    observed = RuntimePerformanceMonitor().evaluate(
        {
            "pipeline_latency_ms": 12.0,
            "dashboard_latency_ms": 18.0,
            "synthetic": False,
        }
    )
    synthetic = RuntimePerformanceMonitor().evaluate(
        {"pipeline_latency_ms": 1.0, "synthetic": True}
    )
    assert observed["observed_samples_present"] is True
    assert observed["synthetic_claim"] is False
    assert observed["production_evidence_eligible"] is True
    assert synthetic["synthetic_claim"] is True
    assert synthetic["production_evidence_eligible"] is False


def test_ops_activation(tmp_path: Path) -> None:
    artifacts, supervisor = _write_ops_runtime_evidence(tmp_path)
    service = activate_operations_service(
        artifacts_dir=tmp_path / "ops",
        runtime_artifacts_dir=artifacts,
        supervisor_state_path=supervisor,
    )
    state = service.run_diagnostics()
    assert state.payload["overall_status"] == "HEALTHY"
    assert state.payload["health_score"] == 100.0


def test_oat_incomplete_under_production_profile() -> None:
    evidence = [
        CertificationEvidence(
            evidence_id="OAT-OBS-RUNTIME_HEALTH",
            area="RUNTIME_HEALTH",
            status=AcceptanceStatus.PASS,
            reference="evidence://fixture/runtime_health",
            observed_at="2026-07-21T01:00:00+00:00",
            source="WAVE3_OPS_ACTIVATION",
            remediation="Capture real runtime health evidence.",
            verified=True,
        )
    ]
    result = evaluate_operational_acceptance(evidence, profile="production")
    assert result["status"] == "EVIDENCE_INCOMPLETE"
    assert "RUNTIME_HEALTH" in result["blockers"] or any(
        "EVIDENCE_REJECTED" in str(check.get("status", "")) for check in result["checks"]
    )


def test_assemble_wave3_package_without_regression(tmp_path: Path) -> None:
    result = assemble_wave3_package(
        output_dir=tmp_path / "wave3_pkg",
        run_regression=False,
        endurance_sample_seconds=0.3,
    )
    assert result["certification_claimed"] is False
    assert result["execution_allowed"] is False
    assert result["phase181_status"] == "NOT_CERTIFIED"
    assert "regression" not in result
    assert Path(result["summary_path"]).is_file()
    assert result["backup_restore"]["ok"] is True
    assert result["performance"]["synthetic_rejected"]["production_evidence_eligible"] is False
    assert result["oat"]["status"] == "EVIDENCE_INCOMPLETE"

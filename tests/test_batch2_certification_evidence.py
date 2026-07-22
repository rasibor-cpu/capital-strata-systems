"""Batch 2 — Production Certification evidence honesty tests."""

from __future__ import annotations

from pathlib import Path

from backend.certification.batch2_certification_assessment import (
    assemble_batch2_package,
    assess_certification_decision,
    capture_extended_oat_observations,
    classify_gaps,
)
from backend.certification.production_readiness_certification import (
    ProductionReadinessCertificationEngine,
)


def test_batch2_never_claims_certified_without_complete_ops(tmp_path: Path) -> None:
    decision = assess_certification_decision(
        {"status": "NOT_CERTIFIED", "deployment_blockers": ["ENDURANCE_READINESS:MEMORY_STABILITY"]},
        endurance_eligible=False,
        broker_live_complete=False,
        oat_complete=False,
    )
    assert decision == "CERTIFIABLE AFTER OPERATIONAL VALIDATION"


def test_batch2_refuses_certified_when_engine_says_certified_but_ops_incomplete() -> None:
    decision = assess_certification_decision(
        {"status": "CERTIFIED_FOR_CONTROLLED_DEPLOYMENT", "deployment_blockers": []},
        endurance_eligible=False,
        broker_live_complete=False,
        oat_complete=True,
    )
    assert decision == "CERTIFIABLE AFTER OPERATIONAL VALIDATION"


def test_batch2_certified_only_when_ops_earned() -> None:
    decision = assess_certification_decision(
        {"status": "CERTIFIED_FOR_CONTROLLED_DEPLOYMENT", "deployment_blockers": []},
        endurance_eligible=True,
        broker_live_complete=True,
        oat_complete=True,
    )
    assert decision == "CERTIFIED"


def test_extended_oat_does_not_claim_shutdown(tmp_path: Path) -> None:
    pack = capture_extended_oat_observations(tmp_path)
    assert pack["shutdown_performed"] is False
    assert pack["certification_claimed"] is False
    assert "SHUTDOWN" in (pack.get("blockers") or [])
    assert (tmp_path / "OPERATIONAL_ACCEPTANCE_OBSERVATION.json").is_file()


def test_assemble_batch2_package_not_certified(tmp_path: Path) -> None:
    result = assemble_batch2_package(
        output_dir=tmp_path / "pkg",
        run_regression=False,
        endurance_sample_seconds=0.3,
    )
    assert result["certification_claimed"] is False
    assert result["execution_allowed"] is False
    assert result["executive_certification_decision"] in {
        "NOT CERTIFIED",
        "CERTIFIABLE AFTER OPERATIONAL VALIDATION",
    }
    assert result["executive_certification_decision"] != "CERTIFIED"
    engine_status = (result.get("phase181_evaluation") or {}).get("status")
    assert engine_status == "NOT_CERTIFIED"
    assessment = result["assessment"]
    assert assessment["evidence_fabricated"] is False
    assert assessment["residual_blockers"]["AR-014"]["production_evidence_eligible"] is False
    assert assessment["residual_blockers"]["AR-040"]["live_probe_enabled"] is False
    assert (Path(result["package_dir"]) / "CERTIFICATION_READINESS_ASSESSMENT.json").is_file()


def test_phase181_production_profile_with_batch2_evidence_stays_not_certified(
    tmp_path: Path,
) -> None:
    pack = capture_extended_oat_observations(tmp_path)
    evidence = pack.pop("_evidence_objects")
    cert = ProductionReadinessCertificationEngine(
        evidence=evidence, profile="production"
    ).evaluate(profile="production")
    assert cert["status"] == "NOT_CERTIFIED"
    assert cert["execution_allowed"] is False
    gaps = classify_gaps(cert)
    assert gaps["engineering_complete"] is True

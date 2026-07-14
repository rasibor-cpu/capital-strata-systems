from __future__ import annotations

import pytest

from backend.certification.platform_deployment_validator import validate_platform_deployment
from backend.certification.platform_environment_validator import validate_platform_environment
from backend.certification.platform_live_disable_verification import SAFE_FLAGS, PlatformLiveDisableVerificationError, assert_platform_safe, verify_platform_live_disabled
from backend.certification.platform_operational_readiness import assess_platform_operational_readiness
from backend.certification.platform_rc1_final_certification import MAXIMUM_POSITIVE_VERDICT, SUBSYSTEMS, certify_platform_rc1_final
from backend.certification.platform_rc1_report import build_platform_rc1_report
from backend.certification.platform_release_scorecard import SCORE_DIMENSIONS, build_platform_release_scorecard
from backend.execution.unified_execution_pipeline import UnifiedExecutionPipeline, UnifiedExecutionPipelineError, UnifiedExecutionRequest


NOW = "2026-07-14T00:00:00+00:00"
DOCS = [
    "docs/release/RC1_PLATFORM_CERTIFICATION.md",
    "docs/release/RC1_OPERATIONAL_BROKER_CERTIFICATION.md",
    "docs/governance/PHASE_RC1_FINAL_ENTERPRISE_CERTIFICATION.md",
]


def test_platform_rc1_final_certifies_integrated_paper_system() -> None:
    result = certify_platform_rc1_final(timestamp=NOW, available_documents=DOCS, payloads=[SAFE_FLAGS])
    assert result["overall_verdict"] == MAXIMUM_POSITIVE_VERDICT
    assert result["release_recommendation"] == "CONTROLLED_RC1_RELEASE"
    assert result["ready_for_live_trading"] is False
    assert {row["subsystem"] for row in result["subsystems"]} == set(SUBSYSTEMS)
    assert all(row["status"] == "PASS" for row in result["subsystems"])
    assert result["live_disable_verification"]["status"] == "PASS"
    assert result["report"]["overall_verdict"] == MAXIMUM_POSITIVE_VERDICT


def test_subsystem_warning_produces_hold_for_review() -> None:
    result = certify_platform_rc1_final(
        timestamp=NOW,
        available_documents=DOCS,
        subsystem_evidence={"Dashboard": "WARNING"},
        payloads=[SAFE_FLAGS],
    )
    assert result["overall_verdict"] == "READY_WITH_WARNINGS"
    assert result["release_recommendation"] == "HOLD_FOR_REVIEW"
    assert "Dashboard" in result["warnings"]


def test_subsystem_failure_blocks_certification() -> None:
    result = certify_platform_rc1_final(
        timestamp=NOW,
        available_documents=DOCS,
        subsystem_evidence={"Risk": "FAIL"},
        payloads=[SAFE_FLAGS],
    )
    assert result["overall_verdict"] == "NOT_READY"
    assert "Risk" in result["production_blockers"]


def test_live_disable_violation_fails_safety() -> None:
    result = certify_platform_rc1_final(timestamp=NOW, available_documents=DOCS, payloads=[{**SAFE_FLAGS, "execution_allowed": True}])
    assert result["overall_verdict"] == "FAILED_SAFETY"
    assert result["live_disable_verification"]["status"] == "FAIL"


def test_assert_platform_safe_rejects_live_authority() -> None:
    with pytest.raises(PlatformLiveDisableVerificationError):
        assert_platform_safe({**SAFE_FLAGS, "broker_write": True})
    with pytest.raises(PlatformLiveDisableVerificationError):
        assert_platform_safe({**SAFE_FLAGS, "mode": "LIVE"})
    with pytest.raises(PlatformLiveDisableVerificationError):
        assert_platform_safe({**SAFE_FLAGS, "api_key": "SECRET"})


def test_environment_validator_detects_missing_docs_and_dependency_failure() -> None:
    env = validate_platform_environment(
        required_documents=DOCS,
        available_documents=DOCS[:1],
        dependency_status={"runtime": "PASS", "dashboard": "FAIL"},
    )
    assert env["status"] == "FAIL"
    assert "dashboard" in env["failed_dependencies"]
    assert DOCS[1] in env["missing_documents"]


def test_operational_readiness_warning_and_failure_scores() -> None:
    warning = assess_platform_operational_readiness({"restart": "WARNING"})
    assert warning["status"] == "WARNING"
    assert warning["score"] < 100
    failed = assess_platform_operational_readiness({"recovery": "FAIL"})
    assert failed["status"] == "FAIL"
    assert "recovery" in failed["failures"]


def test_deployment_validator_blocks_unsafe_deployment_evidence() -> None:
    result = validate_platform_deployment({"rollback": False, "live_disabled": False})
    assert result["status"] == "FAIL"
    assert "rollback" in result["failures"]
    assert result["production_deployment_authorized"] is False
    assert result["live_trading_authorized"] is False


def test_release_scorecard_dimensions_and_override() -> None:
    scorecard = build_platform_release_scorecard({"architecture": 80, "paper_safety": 100})
    assert set(scorecard["scores"]) == set(SCORE_DIMENSIONS)
    assert scorecard["scores"]["architecture"] == 80
    assert scorecard["maximum_positive_verdict"] == MAXIMUM_POSITIVE_VERDICT


def test_missing_document_blocks_final_certification() -> None:
    result = certify_platform_rc1_final(timestamp=NOW, available_documents=DOCS[:2], payloads=[SAFE_FLAGS])
    assert result["overall_verdict"] == "NOT_READY"
    assert "docs/governance/PHASE_RC1_FINAL_ENTERPRISE_CERTIFICATION.md" in result["production_blockers"]


def test_final_report_is_deterministic() -> None:
    result = certify_platform_rc1_final(timestamp=NOW, available_documents=DOCS, payloads=[SAFE_FLAGS])
    report = build_platform_rc1_report({key: value for key, value in result.items() if key != "report"})
    assert report == result["report"]
    assert report["paper_only"] is True
    assert "READY_FOR_LIVE_TRADING" not in report["markdown"]


def test_live_disable_verification_scans_nested_payloads() -> None:
    proof = verify_platform_live_disabled([{**SAFE_FLAGS, "nested": {"supports_order_submission": True}}])
    assert proof["status"] == "FAIL"
    assert any("supports_order_submission" in item for item in proof["failures"])


def test_platform_certification_does_not_authorize_live_execution() -> None:
    result = certify_platform_rc1_final(timestamp=NOW, available_documents=DOCS, payloads=[SAFE_FLAGS])
    assert result["execution_allowed"] is False
    assert result["live_trading_blocked"] is True
    assert result["broker_execution_armed"] is False
    assert result["paper_only"] is True
    assert result["advisory_only"] is True


def test_unified_execution_regression_live_options_still_rejected() -> None:
    with pytest.raises(UnifiedExecutionPipelineError, match="Live mode rejected"):
        UnifiedExecutionPipeline().execute(UnifiedExecutionRequest(asset_class="OPTIONS", symbol="SPY", side="BUY", quantity=1, mode="live"))

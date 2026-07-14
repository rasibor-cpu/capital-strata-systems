from __future__ import annotations

import inspect
import json

import pytest

from backend.options.options_income_audit_report import OptionsIncomeAuditReportBuilder, OptionsIncomeAuditReportError
from backend.options.options_income_certification import OptionsIncomeCertificationEngine, OptionsIncomeCertificationError, certify_options_income_engine
from backend.options.options_income_certification_report import OptionsIncomeCertificationReportBuilder, OptionsIncomeCertificationReportError
from backend.options.options_income_end_to_end_validator import OptionsIncomeEndToEndValidator, OptionsIncomeEndToEndValidatorError, SUBSYSTEMS
from backend.options.options_income_operational_readiness import OptionsIncomeOperationalReadiness
from backend.options.options_income_replay_validator import OptionsIncomeReplayValidator
from backend.options.options_income_runtime_validator import OptionsIncomeRuntimeValidator, OptionsIncomeRuntimeValidatorError

import backend.options.options_income_certification as certification_module
import backend.options.options_income_end_to_end_validator as end_to_end_module


def test_full_certification_passes_controlled_paper_readiness():
    result = certify_options_income_engine()

    assert result["certification_status"] == "PASS"
    assert result["overall_readiness"] == "READY_FOR_CONTROLLED_CERTIFICATION"
    assert result["certification_score"] == 100.0
    assert {row["subsystem"] for row in result["subsystems"]} == set(SUBSYSTEMS)
    assert all(row["status"] == "PASS" for row in result["subsystems"])
    assert result["execution_allowed"] is False
    assert result["live_trading_blocked"] is True
    assert result["paper_only"] is True


def test_end_to_end_workflow_constructs_required_integrated_artifacts():
    workflow = OptionsIncomeEndToEndValidator().validate()

    assert workflow["status"] == "PASS"
    assert workflow["artifacts"]["portfolio"]["portfolio_id"] == "OI010-PAPER"
    assert workflow["artifacts"]["risk"]["approval_status"] in {"APPROVED_PAPER", "APPROVED_WITH_WARNINGS"}
    assert workflow["artifacts"]["dashboard"]["summary"]["engine_version"] == "OI-008"
    assert workflow["artifacts"]["broker_registry"]["provider_name"] == "oi010_paper"
    assert workflow["artifacts"]["order_preview"]["preview_status"] == "PASS"


def test_replay_validation_is_deterministic_and_stably_ordered():
    replay = OptionsIncomeReplayValidator().validate()

    assert replay["status"] == "PASS"
    assert replay["same_inputs"] is True
    assert replay["same_outputs"] is True
    assert replay["same_ordering"] is True
    assert replay["same_certification"] is True
    assert replay["first_hash"] == replay["second_hash"]


def test_audit_report_contains_required_canonical_evidence():
    certification = certify_options_income_engine(tests_executed=["oi010"])
    audit = certification["audit_report"]

    assert audit["certification_timestamp"] == "2026-07-14T00:00:00+00:00"
    assert set(audit["modules_tested"]) == set(SUBSYSTEMS)
    assert audit["tests_executed"] == ["oi010"]
    assert audit["tests_passed"] == 1
    assert audit["tests_failed"] == 0
    assert audit["paper_only_confirmation"] is True
    assert audit["execution_allowed"] is False
    assert audit["live_trading_blocked"] is True
    assert audit["overall_readiness"] == "READY_FOR_CONTROLLED_CERTIFICATION"


def test_certification_report_generation():
    certification = certify_options_income_engine()
    report = certification["certification_report"]

    assert report["report_type"] == "OPTIONS_INCOME_CONTROLLED_PAPER_CERTIFICATION"
    assert report["certification_status"] == "PASS"
    assert "controlled paper certification PASS" in report["summary"]
    assert report["audit"]["certification_score"] == 100.0


def test_readiness_score_status_bands():
    readiness = OptionsIncomeOperationalReadiness()
    pass_cert = {"subsystems": [{"subsystem": name, "status": "PASS"} for name in SUBSYSTEMS]}
    fail_cert = {"subsystems": [{"subsystem": name, "status": "FAIL"} for name in SUBSYSTEMS]}
    replay = {"status": "PASS"}
    runtime = {"status": "PASS"}

    ready = readiness.score(certification=pass_cert, replay=replay, runtime=runtime)
    not_ready = readiness.score(certification=fail_cert, replay={"status": "FAIL"}, runtime={"status": "FAIL"}, documentation_present=False)

    assert ready["overall_readiness"] == "READY_FOR_CONTROLLED_CERTIFICATION"
    assert ready["overall_readiness_score"] == 100.0
    assert not_ready["overall_readiness"] == "NOT_READY"


def test_runtime_validator_detects_unsafe_execution_enabled_payload():
    unsafe = {"execution_allowed": True, "live_trading_blocked": True, "advisory_only": True, "broker_execution_armed": False, "paper_only": True}
    result = OptionsIncomeRuntimeValidator().validate(unsafe)

    assert result["status"] == "FAIL"
    assert any("execution_enabled" in item for item in result["blockers"])


def test_runtime_validator_rejects_non_mapping_payload():
    with pytest.raises(OptionsIncomeRuntimeValidatorError):
        OptionsIncomeRuntimeValidator().validate(["bad"])  # type: ignore[arg-type]


def test_live_mode_rejected_fail_closed():
    with pytest.raises(OptionsIncomeCertificationError, match="unsafe runtime"):
        OptionsIncomeCertificationEngine().certify(mode="LIVE")
    with pytest.raises(OptionsIncomeEndToEndValidatorError, match="live routing"):
        OptionsIncomeEndToEndValidator().validate(mode="LIVE")


def test_duplicate_report_detection_fails_closed():
    class DuplicateEndToEnd:
        def validate(self, **kwargs):
            return {
                "status": "PASS",
                "subsystems": [
                    {"subsystem": "scanner", "status": "PASS"},
                    {"subsystem": "scanner", "status": "PASS"},
                ],
                "blockers": [],
                "warnings": [],
                "paper_only": True,
                "advisory_only": True,
                "execution_allowed": False,
                "live_trading_blocked": True,
                "broker_execution_armed": False,
            }

    with pytest.raises(OptionsIncomeCertificationError, match="duplicate reports"):
        OptionsIncomeCertificationEngine(end_to_end=DuplicateEndToEnd()).certify()


def test_missing_audit_fails_closed():
    with pytest.raises(OptionsIncomeAuditReportError, match="modules tested missing"):
        OptionsIncomeAuditReportBuilder().build(certification={"subsystems": []}, readiness={}, replay={})
    with pytest.raises(OptionsIncomeCertificationReportError, match="missing audit"):
        OptionsIncomeCertificationReportBuilder().build({"certification_status": "PASS"}, {})


def test_fail_closed_payload_preserves_safety_flags():
    payload = OptionsIncomeCertificationEngine().fail_closed("broken integration")

    assert payload["certification_status"] == "FAIL"
    assert payload["overall_readiness"] == "NOT_READY"
    assert payload["execution_allowed"] is False
    assert payload["live_trading_blocked"] is True
    assert payload["paper_only"] is True
    assert payload["blockers"] == ["broken integration"]


def test_replay_detects_hidden_state_or_output_drift():
    calls = {"count": 0}

    def factory():
        calls["count"] += 1
        return {"status": "PASS", "value": calls["count"], "paper_only": True, "advisory_only": True, "execution_allowed": False, "live_trading_blocked": True, "broker_execution_armed": False}

    replay = OptionsIncomeReplayValidator().validate(factory)

    assert replay["status"] == "FAIL"
    assert replay["blockers"] == ["replay_mismatch"]


def test_json_serializable_and_idempotent_certification():
    first = certify_options_income_engine()
    second = certify_options_income_engine()

    assert first == second
    assert json.loads(json.dumps(first, sort_keys=True))["certification_status"] == "PASS"


def test_no_live_execution_terms_added_to_oi010_modules():
    source = "\n".join(
        [
            inspect.getsource(certification_module),
            inspect.getsource(end_to_end_module),
        ]
    )

    assert "submit_order" not in source
    assert "place_order" not in source
    assert "execute_trade" not in source
    assert "enable_live" not in source
    assert ".env" not in source
    assert "PEM" not in source

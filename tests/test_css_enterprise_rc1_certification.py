"""CSS Enterprise RC1 evidence-only certification closure."""

from dataclasses import replace

from backend.certification import (
    RC1Evidence,
    RC1_REPORT_TITLES,
    build_rc1_report_suite,
    certify_rc1,
)
from backend.certification.rc1_certification import (
    COMMAND_REQUIREMENTS,
    RC1_REQUIREMENTS,
)
from backend.reports_center.producers import registered_producer_codes
from backend.reports_center.registry import by_code


def _evidence() -> list[RC1Evidence]:
    return [
        RC1Evidence(
            evidence_id=f"RC1-{index:03d}",
            area=area,
            status="PASS",
            reference=f"evidence://rc1/{area.lower()}",
            observed_at="2026-07-21T05:14:00Z",
            verified=True,
            command=f"verify-{area.lower()}" if area in COMMAND_REQUIREMENTS else None,
            exit_code=0 if area in COMMAND_REQUIREMENTS else None,
            duration_seconds=1.0 if area in COMMAND_REQUIREMENTS else None,
            output_reference=f"output://rc1/{area.lower()}"
            if area in COMMAND_REQUIREMENTS
            else None,
        )
        for index, area in enumerate(
            (*RC1_REQUIREMENTS, *COMMAND_REQUIREMENTS),
            start=1,
        )
    ]


def test_missing_actual_evidence_is_not_ready_with_complete_blockers() -> None:
    result = certify_rc1([])
    assert result["status"] == "NOT_READY"
    assert result["scorecard"]["certification_readiness"] == 0
    assert len(result["outstanding_blockers"]) == (
        len(RC1_REQUIREMENTS) + len(COMMAND_REQUIREMENTS)
    )
    for blocker in result["outstanding_blockers"]:
        assert blocker["description"]
        assert blocker["severity"]
        assert blocker["owner"]
        assert blocker["remediation"]
        assert "evidence" in blocker
        assert blocker["verification_status"]
    assert result["tag_recommendation"] is None
    assert result["evidence_fabricated"] is False


def test_certified_requires_all_actual_evidence_and_only_recommends_tag() -> None:
    result = certify_rc1(_evidence())
    assert result["status"] == "CERTIFIED"
    assert result["scorecard"]["certification_readiness"] == 100
    assert result["outstanding_blockers"] == []
    assert result["tag_recommendation"] == "CSS_ENTERPRISE_RC1"
    assert result["tag_creation_authorized"] is False
    assert result["deployment_authorized"] is False
    assert result["execution_allowed"] is False


def test_command_pass_requires_exit_code_duration_and_output() -> None:
    evidence = _evidence()
    python = next(row for row in evidence if row.area == "PYTHON")
    evidence[evidence.index(python)] = replace(python, exit_code=None)
    result = certify_rc1(evidence)
    assert result["status"] == "NOT_READY"
    assert result["command_runner"]["PYTHON"] is False
    assert result["tag_recommendation"] is None


def test_rc1_a4_reports_and_reports_center_registration() -> None:
    certification = certify_rc1([])
    reports = build_rc1_report_suite(certification)
    assert set(reports) == set(RC1_REPORT_TITLES)
    assert len({report["report_id"] for report in reports.values()}) == len(reports)
    for report in reports.values():
        assert report["page_size"] == "A4"
        assert report["viewer_compatible"] is True
        assert report["tag_created"] is False
        assert report["execution_allowed"] is False
    assert set(RC1_REPORT_TITLES) <= registered_producer_codes()
    for report_code in RC1_REPORT_TITLES:
        definition = by_code(report_code)
        assert definition is not None
        assert definition.status == "AVAILABLE_WITH_LIMITATIONS"

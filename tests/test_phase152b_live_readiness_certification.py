from __future__ import annotations

import json

from fastapi.testclient import TestClient

from backend.validation.live_readiness_certification import (
    CHECK_SPECS,
    CHECK_PASS,
    CHECK_WARNING,
    DECISION_GO,
    DECISION_GO_WITH_CONDITIONS,
    DECISION_NO_GO,
    LiveReadinessCertificationEngine,
    write_live_readiness_report,
)
from dashboard.runtime.api_bridge import create_app
from dashboard.runtime.frontend_contract import build_frontend_payload
from dashboard.web.web_app import _live_readiness_certification_page
from dashboard.mobile import mobile_app
from launcher.css_mobile_launcher import get_launcher_live_readiness_certification_feed


def _all_pass_evidence() -> dict[str, object]:
    return {
        "software_version": "1.0-test",
        "commit": "abc1234",
        "git_tag": "v1.0.0-engineering-complete",
        "checks": {
            spec.key: {"status": CHECK_PASS, "reason": f"{spec.key}_verified"}
            for spec in CHECK_SPECS
        },
        "learning_system_status": {"status": CHECK_PASS, "reason": "learning_system_observed"},
    }


def test_phase152b_certification_passes_when_all_systems_pass() -> None:
    report = LiveReadinessCertificationEngine().certify(_all_pass_evidence())

    assert report["overall_certification_decision"] == DECISION_GO
    assert report["readiness_score"] == 100.0
    assert report["known_blockers"] == []
    assert report["execution_controls"]["live_execution_enabled"] is False
    assert report["execution_controls"]["dry_run_only"] is True


def test_phase152b_certification_fails_if_mandatory_gate_fails() -> None:
    evidence = _all_pass_evidence()
    evidence["checks"]["unified_trade_gate"] = {
        "status": "FAIL",
        "reason": "unified_trade_gate_rejected_validation",
    }

    report = LiveReadinessCertificationEngine().certify(evidence)

    assert report["overall_certification_decision"] == DECISION_NO_GO
    assert "unified_trade_gate_rejected_validation" in report["known_blockers"]


def test_phase152b_certification_reports_go_with_conditions() -> None:
    evidence = _all_pass_evidence()
    evidence["checks"]["artifact_freshness"] = {
        "status": CHECK_WARNING,
        "reason": "artifact_freshness_warning_only",
    }

    report = LiveReadinessCertificationEngine().certify(evidence)

    assert report["overall_certification_decision"] == DECISION_GO_WITH_CONDITIONS
    assert report["known_blockers"] == []
    assert "artifact_freshness_warning_only" in report["known_warnings"]


def test_phase152b_default_current_state_is_no_go_without_live_evidence() -> None:
    report = LiveReadinessCertificationEngine().certify({})

    assert report["overall_certification_decision"] == DECISION_NO_GO
    assert report["known_blockers"]
    assert report["audit"]["live_orders_submitted"] is False


def test_phase152b_cad20_governor_verification_is_explicit() -> None:
    report = LiveReadinessCertificationEngine().certify(_all_pass_evidence())
    governor_checks = {
        check["key"]: check for check in report["live_governor_verification"]["checks"]
    }

    assert governor_checks["cannot_exceed_cad_20"]["status"] == CHECK_PASS
    assert governor_checks["cannot_bypass_unified_trade_gate"]["status"] == CHECK_PASS
    assert governor_checks["cannot_bypass_margin_gate"]["status"] == CHECK_PASS
    assert governor_checks["cannot_bypass_antibleed_guard"]["status"] == CHECK_PASS
    assert governor_checks["cannot_bypass_capital_governor"]["status"] == CHECK_PASS
    assert governor_checks["cannot_bypass_broker_arming"]["status"] == CHECK_PASS
    assert governor_checks["cannot_bypass_rbac"]["status"] == CHECK_PASS
    assert governor_checks["fails_closed"]["status"] == CHECK_PASS


def test_phase152b_governor_status_reports_same_currency_only_policy() -> None:
    report = LiveReadinessCertificationEngine().certify({})
    phase152a = next(
        check for check in report["checks"] if check["key"] == "phase_152a_live_micro_pilot_governor"
    )
    evidence = phase152a["evidence"]

    assert phase152a["status"] == CHECK_PASS
    assert evidence["limit_currency"] == "CAD"
    assert evidence["fx_conversion_authorized"] is False
    assert evidence["identity_currency_only"] is True
    assert evidence["non_cad_live_exposure_allowed"] is False
    assert type(evidence["authoritative_exposure_currency_required"]) is bool
    assert evidence["authoritative_exposure_currency_required"] is True


def test_phase152b_report_generated_correctly(tmp_path) -> None:
    report = LiveReadinessCertificationEngine().certify(_all_pass_evidence())
    path = tmp_path / "phase152b_report.json"

    write_live_readiness_report(report, path)
    loaded = json.loads(path.read_text(encoding="utf-8"))

    assert loaded["payload_version"] == "css.phase152b.live_readiness_certification.v1"
    assert loaded["overall_readiness"] == "READY_FOR_CONTROLLED_CAD_20_VALIDATION"
    assert loaded["software_version"] == "1.0-test"
    assert loaded["commit"] == "abc1234"
    assert loaded["git_tag"] == "v1.0.0-engineering-complete"
    assert "risk_controls" in loaded
    assert "dashboard_controls" in loaded
    assert "operational_controls" in loaded


def test_phase152b_dashboard_contract_and_api_display_certification() -> None:
    payload = build_frontend_payload(
        {"live_readiness_certification": LiveReadinessCertificationEngine().certify(_all_pass_evidence())}
    )
    section = payload["sections"]["live_readiness_certification"]

    assert section["section_title"] == "Live Readiness Certification"
    assert section["go_no_go"] == DECISION_GO
    assert section["execution_allowed"] is False

    client = TestClient(create_app())
    response = client.get("/api/v1/live-readiness-certification")

    assert response.status_code == 200
    assert response.json()["section"] == "live_readiness_certification"


def test_phase152b_mobile_desktop_and_launcher_render_certification(monkeypatch) -> None:
    desktop = _live_readiness_certification_page()
    mobile = mobile_app._live_readiness_certification_page(
        {"user_id": "00017", "display_name": "CSS Trader", "role": "TRADER"},
        {"created": 1.0},
    )
    launcher = get_launcher_live_readiness_certification_feed()

    assert "Live Readiness Certification" in desktop
    assert "/api/v1/live-readiness-certification" in desktop
    assert "Live Readiness Certification" in mobile
    assert "GO / NO-GO" in mobile
    assert launcher["section_title"] == "Live Readiness Certification"


def test_phase152b_no_live_execution_and_paper_mode_unchanged() -> None:
    report = LiveReadinessCertificationEngine().certify(_all_pass_evidence())
    payload = build_frontend_payload({"resolved_mode": "paper", "live_readiness_certification": report})

    assert report["audit"]["live_orders_submitted"] is False
    assert report["audit"]["broker_permissions_modified"] is False
    assert report["audit"]["paper_mode_changed"] is False
    assert payload["resolved_mode"] == "DISABLED"
    assert payload["sections"]["runtime_status"]["degraded_reason"]
    assert payload["sections"]["live_readiness_certification"]["execution_allowed"] is False

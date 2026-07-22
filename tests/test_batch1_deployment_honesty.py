"""Batch 1 — Deployment readiness honesty (AR-016 / RB-011)."""

from __future__ import annotations

from pathlib import Path

from backend.product_honesty import deployment_honesty_status, product_honesty_bundle


ROOT = Path(__file__).resolve().parents[1]


def test_ar016_deployment_honesty_contract():
    status = deployment_honesty_status()
    assert status["automated_production_deploy"] is False
    assert status["ci_cd_automation_present"] is False
    assert status["cd_mode"] == "manual_with_approvals"
    assert status["execution_allowed"] is False
    assert "manual_with_approvals" in status["customer_banner"]
    bundle = product_honesty_bundle()
    assert bundle["deployment"]["cd_mode"] == "manual_with_approvals"


def test_ar016_gate2_ci_workflow_present_and_gated():
    path = ROOT / ".github" / "workflows" / "css_gate2_release_ci.yml"
    text = path.read_text(encoding="utf-8")
    assert path.is_file()
    assert "gate2-ci" in text
    assert "compileall" in text
    assert "pytest" in text
    assert "test_batch1_deployment_honesty.py" in text


def test_ar016_governance_workflow_no_false_success_without_tests():
    path = ROOT / ".github" / "workflows" / "css_governance.yml"
    text = path.read_text(encoding="utf-8")
    assert "PCNRASS STATUS: STABLE" not in text
    assert "pytest" in text
    assert "compileall" in text
    assert "'on':" not in text  # prior structurally broken form


def test_ar016_approval_framework_honesty():
    path = ROOT / "docs" / "governance" / "CSS_DEPLOYMENT_APPROVAL_FRAMEWORK.md"
    text = path.read_text(encoding="utf-8")
    assert "manual_with_approvals" in text
    assert "Automated pipeline deploys to production" not in text
    assert "NOT PRESENT" in text


def test_ar016_playbook_controlled_cd_path():
    path = ROOT / "docs" / "operations" / "CSS_PRODUCTION_DEPLOYMENT_PLAYBOOK.md"
    text = path.read_text(encoding="utf-8")
    assert "manual_with_approvals" in text
    assert "Controlled CD path" in text
    assert "does not automate production deployment" in text.lower()

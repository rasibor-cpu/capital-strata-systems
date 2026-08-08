"""ER-001 offline tests — endurance closeout plan and template invariants."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PLAN = REPO_ROOT / "docs" / "governance" / "ER_001_ENDURANCE_CLOSEOUT_AND_CERTIFICATION_PLAN.md"
TEMPLATE = REPO_ROOT / "docs" / "governance" / "ER_001_ENDURANCE_CERTIFICATION_TEMPLATE.md"
ACTIVE_HEAD = "66e11d4f83600a7765b4e55afa33d19e301dd70e"


def test_er001_plan_and_template_exist() -> None:
    assert PLAN.is_file()
    assert TEMPLATE.is_file()


def test_er001_plan_forbids_runtime_stop_and_ov002_auto_credit() -> None:
    text = PLAN.read_text(encoding="utf-8")
    assert "NO SHUTDOWN EXECUTED" in text
    assert ACTIVE_HEAD in text
    assert "OBSERVATIONAL_STABILITY" in text
    assert "OV-002_CERTIFICATION" in text
    assert "not automatic" in text.lower() or "NOT** automatic" in text or "does not certify OV-002" in text.lower() or "does not certify OV-002" in text
    assert "FUTURE_EXECUTION_COMMAND — DO NOT RUN" in text
    assert "PASS" in text and "FAIL" in text and "BLOCKED" in text


def test_er001_template_has_required_sections() -> None:
    text = TEMPLATE.read_text(encoding="utf-8")
    for heading in (
        "Executive Summary",
        "Runtime Statistics",
        "Health Summary",
        "Stability",
        "Memory",
        "CPU",
        "Restart History",
        "Failure History",
        "Portfolio",
        "Broker State",
        "Mission Control",
        "Decision Intelligence Status",
        "Evidence Inventory",
        "Known Limitations",
        "Certification Decision",
    ):
        assert heading in text


def test_er001_evidence_categories_documented() -> None:
    text = PLAN.read_text(encoding="utf-8")
    for category in (
        "Supervisor",
        "Mission Control",
        "Portfolio",
        "Runtime",
        "Alerts",
        "Logs",
        "Trade DNA",
        "Decision Intelligence",
        "Broker diagnostics",
        "Runtime reports",
        "Validation summaries",
        "Recovery snapshots",
        "Hashes",
        "Manifest",
    ):
        assert category in text


def test_er001_no_secret_markers_in_governance() -> None:
    forbidden = (
        "BEGIN PRIVATE KEY",
        "BEGIN RSA PRIVATE KEY",
        "Authorization: Bearer",
    )
    for path in (PLAN, TEMPLATE):
        body = path.read_text(encoding="utf-8")
        for marker in forbidden:
            assert marker not in body

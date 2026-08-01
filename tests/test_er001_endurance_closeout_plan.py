"""ER-001 offline tests — endurance closeout classifications and non-claims."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PLAN = REPO_ROOT / "docs" / "governance" / "ER_001_ENDURANCE_CLOSEOUT_AND_CERTIFICATION_PLAN.md"
TEMPLATE = REPO_ROOT / "docs" / "governance" / "ER_001_ENDURANCE_CERTIFICATION_TEMPLATE.md"
ACTIVE_HEAD = "66e11d4f83600a7765b4e55afa33d19e301dd70e"
EVIDENCE_PATH = "runtime_reports/operational_validation/er001_20260801T034921Z_closeout/"

REQUIRED_CLASSIFICATIONS = {
    "OBSERVATIONAL_STABILITY": "PASS",
    "FORMAL_48H_STABILITY": "PASS_WITH_LIMITATIONS",
    "OV_002_CERTIFICATION": "BLOCKED_NOT_CLAIMED",
    "GRACEFUL_SHUTDOWN": "PASS",
    "PROCESS_TERMINATION": "PASS",
    "PORT_RELEASE": "PASS",
    "EXECUTION_SAFETY": "PASS",
}


def test_er001_plan_and_template_exist() -> None:
    assert PLAN.is_file()
    assert TEMPLATE.is_file()


def test_er001_classifications_exact() -> None:
    plan = PLAN.read_text(encoding="utf-8")
    template = TEMPLATE.read_text(encoding="utf-8")
    assert ACTIVE_HEAD in plan
    assert "2026-07-30T03:17:57.105716+00:00" in plan
    assert "2026-08-01T03:41:27.715688+00:00" in plan
    assert "174210.609972" in plan
    for key, value in REQUIRED_CLASSIFICATIONS.items():
        assert f"{key} | `{value}`" in plan or f"{key} = {value}" in plan or f"{key} | {value}" in plan.replace("`", "")
        assert value in template
        assert key.replace("_", "_") in plan or key in plan


def test_er001_evidence_referenced_but_not_required_in_git() -> None:
    plan = PLAN.read_text(encoding="utf-8")
    template = TEMPLATE.read_text(encoding="utf-8")
    assert EVIDENCE_PATH in plan
    assert EVIDENCE_PATH in template
    assert "gitignored" in plan.lower() or "outside Git" in plan or "Not required" in template
    # Sealed package must not be present as a tracked requirement of this commit.
    assert not (REPO_ROOT / "runtime_reports" / "operational_validation" / "er001_20260801T034921Z_closeout" / "MANIFEST.json").exists()


def test_er001_does_not_claim_ov002_or_live_authorization() -> None:
    for path in (PLAN, TEMPLATE):
        body = path.read_text(encoding="utf-8")
        lower = body.lower()
        assert "BLOCKED_NOT_CLAIMED" in body
        assert "does not certify ov-002" in lower or "ov-002 claimed?" in lower
        assert "does not authorize live trading" in lower or "live authorization | **none**" in lower
        assert "live trading authorized" not in lower
        assert "ov-002 certification = pass" not in lower.replace("`", "")


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

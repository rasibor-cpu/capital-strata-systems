from pathlib import Path


DOCS = [
    "PHASE_150_FINAL_ENGINEERING_COMPLETION.md",
    "CSS_VERSION_1_ENGINEERING_COMPLETION_CHECKLIST.md",
    "CSS_MODULE_COMPLETION_REGISTER.md",
    "CSS_PRE_LIVE_READINESS_REPORT.md",
    "CSS_VERSION_1_RELEASE_NOTES.md",
]


def test_phase150_governance_documents_exist_and_preserve_live_boundary() -> None:
    root = Path(__file__).resolve().parents[1]
    docs_dir = root / "docs" / "governance"

    for name in DOCS:
        text = (docs_dir / name).read_text(encoding="utf-8")
        assert "Live broker validation" in text
        assert "Live micro-pilot" in text
        assert "Production operational certification" in text


def test_phase150_completion_report_keeps_safety_controls_fail_closed() -> None:
    root = Path(__file__).resolve().parents[1]
    text = (root / "docs" / "governance" / "PHASE_150_FINAL_ENGINEERING_COMPLETION.md").read_text(
        encoding="utf-8"
    )

    for control in [
        "Unified Trade Gate",
        "Margin Gate",
        "RBAC",
        "Capital Governor",
        "AntiBleedGuard",
    ]:
        assert control in text
    assert "fail-closed" in text
    assert "No Phase 150 work may enable live trading" in text

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_phase151_governance_documents_exist_and_preserve_live_boundary() -> None:
    docs = [
        REPO_ROOT / "docs" / "governance" / "PHASE_151_AUDIT_REMEDIATION_AND_CERTIFICATION_INTEGRITY.md",
        REPO_ROOT / "docs" / "governance" / "CSS_SECRET_SCAN_RUNBOOK.md",
        REPO_ROOT / "docs" / "governance" / "CSS_LEGACY_ARCHIVE_HYGIENE_RECOMMENDATIONS.md",
    ]

    for path in docs:
        text = path.read_text(encoding="utf-8")
        assert "Live broker validation" in text
        assert "Live micro-pilot" in text or path.name == "CSS_LEGACY_ARCHIVE_HYGIENE_RECOMMENDATIONS.md"
        assert "Production operational certification" in text


def test_phase151_python_code_has_no_deprecated_utc_clock_references() -> None:
    roots = ["backend", "engine", "dashboard", "launcher", "scripts", "tests"]
    deprecated_token = "utc" + "now"
    offenders: list[str] = []
    for root_name in roots:
        for path in (REPO_ROOT / root_name).rglob("*.py"):
            if ".pytest_cache" in path.parts:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            if deprecated_token in text:
                offenders.append(str(path.relative_to(REPO_ROOT)))

    assert offenders == []


def test_phase151_archive_candidates_are_not_imported_by_active_code() -> None:
    archive_terms = [
        "CSS-CLAUDE",
        "css-gemini",
        "chatgpt_legacy_backup",
        "archive/dashboard_versions",
    ]
    active_roots = ["backend", "dashboard", "engine", "launcher", "scripts"]
    offenders: list[str] = []

    for root_name in active_roots:
        for path in (REPO_ROOT / root_name).rglob("*"):
            if not path.is_file() or path.suffix not in {".py", ".bat", ".ps1", ".html", ".json"}:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            if any(term in text for term in archive_terms):
                offenders.append(str(path.relative_to(REPO_ROOT)))

    assert offenders == []

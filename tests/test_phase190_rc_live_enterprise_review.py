"""Phase 190 — RC-LIVE enterprise readiness review validation (offline)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "governance" / "PHASE_190_RC_LIVE_ENTERPRISE_REVIEW.md"

REQUIRED_SECTIONS = (
    "Architecture assessment",
    "Governance consistency report",
    "Safety assessment",
    "Broker assessment",
    "Asset assessment",
    "Code-health assessment",
    "Release-readiness matrix",
    "Remaining blockers",
    "Recommended sequence",
)

REQUIRED_RELEASE_ROWS = (
    "Internal freeze",
    "Controlled online certification",
    "Paper certification",
    "Pilot (live micro)",
    "Production",
)


def test_phase190_governance_doc_exists() -> None:
    assert DOC.is_file(), f"missing {DOC}"


def test_phase190_required_sections_present() -> None:
    text = DOC.read_text(encoding="utf-8")
    for section in REQUIRED_SECTIONS:
        assert section in text, f"missing section: {section}"


def test_phase190_safety_statement() -> None:
    text = DOC.read_text(encoding="utf-8")
    assert "NO RUNTIME" in text
    assert "NO BROKER AUTHENTICATION" in text
    assert "NO LIVE EXECUTION" in text
    assert "NO FREEZE SHA" in text


def test_phase190_release_readiness_explicit() -> None:
    text = DOC.read_text(encoding="utf-8")
    for row in REQUIRED_RELEASE_ROWS:
        assert row in text
    assert "NO-GO" in text
    assert "READY_AFTER_PRECHECK" in text
    assert "Internal freeze" in text and "NO-GO" in text
    # Live/production must remain NO-GO in this review.
    assert "Pilot (live micro)" in text and "NO-GO" in text
    assert "Production" in text


def test_phase190_rc004_gap_documented() -> None:
    text = DOC.read_text(encoding="utf-8")
    assert "RC-004" in text
    assert "MISSING" in text or "absent" in text.lower()


def test_phase190_broker_classifications_documented() -> None:
    text = DOC.read_text(encoding="utf-8")
    for broker in ("OANDA", "Coinbase", "IBKR", "Binance", "Questrade"):
        assert broker in text
    assert "BLOCKED" in text
    assert "PARTIAL" in text


def test_phase190_no_code_deletion_mandate() -> None:
    text = DOC.read_text(encoding="utf-8")
    assert "do not remove" in text.lower() or "Do not remove" in text or "do not delete" in text.lower()

"""Phase 192 — LDT governance refresh + RC-004 completion (offline)."""

from __future__ import annotations

import json
from pathlib import Path

from backend.app.brokers.multi_broker_readiness.rc004 import (
    RC004_EXPLICIT_STATEMENT,
    evaluate_rc004_readiness,
    rc004_signoff_artifact_present,
)
from backend.app.governance.enterprise_certification_registry import (
    RegistryQuery,
    assert_valid_certification_claim,
    seed_phase_registry,
)


ROOT = Path(__file__).resolve().parents[1]
PHASE_DOC = ROOT / "docs" / "governance" / "PHASE_192_LDT_REFRESH_AND_RC004.md"
RC004_DOC = ROOT / "docs" / "governance" / "RC_004_OPERATIONAL_POSTURE.md"
RC004_MATRIX = ROOT / "docs" / "governance" / "RC_004_POSTURE_MATRIX.json"
LDT192 = ROOT / "docs" / "governance" / "LDT_192_BLOCKER_MATRIX.json"
PHASE192_HEAD = "84a0e893385a624a8ebb5dfffd53f35ce4b30ba7"


def test_phase192_governance_artifacts_exist() -> None:
    for path in (PHASE_DOC, RC004_DOC, RC004_MATRIX, LDT192):
        assert path.is_file(), path


def test_phase192_rc004_explicit_live_not_authorized() -> None:
    text = RC004_DOC.read_text(encoding="utf-8")
    assert "LIVE_TRADING_NOT_AUTHORIZED" in text
    assert "execution_authority" in text.lower() or "execution authority" in text.lower()
    matrix = json.loads(RC004_MATRIX.read_text(encoding="utf-8"))
    assert matrix["live_trading_authorized"] is False
    assert matrix["execution_authority"] is False
    assert matrix["explicit_statement"] == "LIVE_TRADING_NOT_AUTHORIZED"
    assert matrix["freeze_sha_designated"] is False
    assert matrix["as_of_head"] == PHASE192_HEAD


def test_phase192_rc004_evaluator_detects_artifact() -> None:
    assert rc004_signoff_artifact_present(ROOT) is True
    rc = evaluate_rc004_readiness("OANDA", repo_root=ROOT)
    assert rc.signoff_artifact_present is True
    assert rc.live_trading_authorized is False
    assert rc.explicit_statement == RC004_EXPLICIT_STATEMENT
    assert rc.status == "PAPER_ONLY_NO_LIVE_UNLOCK"
    assert "BLK-RC004-LIVE-UNLOCK" in rc.remaining_blockers
    assert "BLK-RC004-ARTIFACT" not in rc.remaining_blockers
    assert rc.diagnostics["execution_authority"] is False
    assert rc.diagnostics["read_only_ttl_is_not_live_authority_ttl"] is True


def test_phase192_blocker_matrix_aggregate_no_go() -> None:
    data = json.loads(LDT192.read_text(encoding="utf-8"))
    assert data["charter_time_aggregate"] == "NO-GO"
    assert data["live_authorized"] is False
    assert data["freeze_sha_designated"] is False
    by_id = {b["id"]: b["classification"] for b in data["blockers"]}
    assert by_id["BLK-ANTIBLEED-CAD20"] == "RESOLVED"
    assert by_id["BLK-RC004-ARTIFACT"] == "RESOLVED"
    assert by_id["BLK-RC004-LIVE-UNLOCK"] == "BLOCKED"
    assert by_id["BLK-FX-CONVERSION"] == "BLOCKED"
    assert by_id["BLK-OANDA-LIVE"] == "BLOCKED"


def test_phase192_doc_release_readiness_and_ttl() -> None:
    text = PHASE_DOC.read_text(encoding="utf-8")
    for row in (
        "Internal Freeze",
        "Controlled Online Read-only",
        "Paper",
        "Pilot",
        "Production",
    ):
        assert row in text
    assert "NO-GO" in text
    assert "READY_AFTER_PRECHECK" in text
    assert "READ_ONLY_OPERATIONAL" in text or "read-only operational TTL" in text.lower()
    assert "LIVE_TRADING_NOT_AUTHORIZED" in text
    assert PHASE192_HEAD in text


def test_phase192_registry_alignment() -> None:
    repo = seed_phase_registry()
    query = RegistryQuery(repo)
    assert query.by_phase("192")
    rc004 = assert_valid_certification_claim(repo, registry_id="governance:RC004")
    assert rc004.live_status == "NOT_AUTHORIZED"
    assert rc004.execution_authority is False
    assert "LIVE_TRADING_NOT_AUTHORIZED" in rc004.blocker_list
    assert "no_committed_RC004_doc" not in rc004.blocker_list
    ldt = assert_valid_certification_claim(repo, registry_id="governance:LDT")
    assert ldt.live_status == "NOT_AUTHORIZED"
    assert ldt.certification_status == "BLOCKED"

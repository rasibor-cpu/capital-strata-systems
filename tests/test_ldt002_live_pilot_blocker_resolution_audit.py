"""LDT-002 offline tests — blocker audit classifications and lineage rules."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from backend.app.risk.anti_bleed_guard import AntiBleedGuard
from backend.app.risk.anti_bleed_policy import AntiBleedPolicyResolver
from backend.config.order_limit_config import DEFAULT_ORDER_LIMIT_CONFIG


REPO_ROOT = Path(__file__).resolve().parents[1]
GATE_MATRIX = REPO_ROOT / "docs" / "governance" / "LDT_001_PREFLIGHT_GATE_MATRIX.json"
LDT002 = REPO_ROOT / "docs" / "governance" / "LDT_002_LIVE_PILOT_BLOCKER_RESOLUTION_AUDIT.md"
LDT192_MATRIX = REPO_ROOT / "docs" / "governance" / "LDT_192_BLOCKER_MATRIX.json"
CHARTER = REPO_ROOT / "docs" / "governance" / "LDT_001_CONTROLLED_LIVE_DEPLOYMENT_TEST_CHARTER.md"
RC004_DOC = REPO_ROOT / "docs" / "governance" / "RC_004_OPERATIONAL_POSTURE.md"
MAINT_TIP = "9a9263c185680353fac9319577b4a1f82d3311dd"
UNIFIED_HEAD = "66e11d4f83600a7765b4e55afa33d19e301dd70e"
MR003G_HEAD = "fa35bb4f4b8f96b4b77bb74217b0fb0f35cf2204"
PHASE192_HEAD = "84a0e893385a624a8ebb5dfffd53f35ce4b30ba7"
MI_TIP = "81d48bfc0e65274c77e28d25047b04d4617d8919"
MERGE_BASE = "b0703f36096bf183514293ef9b83b6e7849bd087"


def _matrix() -> dict:
    return json.loads(GATE_MATRIX.read_text(encoding="utf-8"))


def _gate(gate_id: str) -> dict:
    return next(g for g in _matrix()["gates"] if g["id"] == gate_id)


def _git(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def test_ldt002_audit_document_exists_and_forbids_live_authorization() -> None:
    text = LDT002.read_text(encoding="utf-8")
    assert "NO LIVE TEST AUTHORIZED" in text
    assert "genuinely contradictory" in text.lower() or "Genuinely contradictory" in text
    assert "PARTIALLY_SUPPORTED" in text
    assert "css-v1.0.1-maintenance" in text
    assert UNIFIED_HEAD in text
    assert MR003G_HEAD in text
    assert PHASE192_HEAD in text
    assert "RESOLVED_ON_CANDIDATE" in text
    assert "BLK-ANTIBLEED-CAD20" in text and "RESOLVED" in text
    assert "LIVE_TRADING_NOT_AUTHORIZED" in RC004_DOC.read_text(encoding="utf-8")
    assert "does not authorize live trading" in text.lower() or "does **not** authorize live trading" in text


def test_ldt002_candidate_lineage_resolved() -> None:
    assert _matrix()["lineage_blocker_status"] == "RESOLVED_ON_CANDIDATE"
    assert "RESOLVED_ON_CANDIDATE" in LDT002.read_text(encoding="utf-8")

    for tip in (MAINT_TIP, UNIFIED_HEAD, MI_TIP):
        result = subprocess.run(
            ["git", "merge-base", "--is-ancestor", tip, "HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, tip

    for rel in (
        "docs/governance/CSS_V1_0_1_MAINTENANCE_001_RESIDUAL_RISK_AUDIT.md",
        "docs/governance/DIP_006_CERTIFICATION_MANIFEST.json",
        "backend/intelligence/external_events/constants.py",
    ):
        present = subprocess.run(
            ["git", "cat-file", "-e", f"HEAD:{rel}"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert present.returncode == 0, rel

    assert _git("merge-base", UNIFIED_HEAD, "origin/css-v1.0.1-maintenance") == MERGE_BASE


def test_ldt002_unresolved_blockers_force_no_go() -> None:
    assert _matrix()["charter_time_aggregate"] == "NO-GO"
    assert _matrix()["freeze_sha_designated"] is False
    assert _matrix()["live_authorized"] is False
    assert _gate("E5")["classification"] == "PASS"
    assert _gate("D3")["classification"] == "BLOCKED"
    assert _gate("C8")["classification"] == "BLOCKED"
    assert _gate("A1")["classification"] == "NOT_TESTED"

    cad20 = float(DEFAULT_ORDER_LIMIT_CONFIG.live_pilot_max_position_cad)
    standard = AntiBleedGuard()
    assert cad20 < standard.minimum_profitable_trade_size
    rejected = standard.evaluate(
        symbol="EUR_USD",
        trade_size=cad20,
        expected_move_bps=50.0,
        fee_bps=1.0,
        spread_bps=1.0,
        slippage_bps=1.0,
    )
    assert rejected["approved"] is False
    assert rejected["reason"] == "trade_size_too_small"

    micro = AntiBleedGuard(policy=AntiBleedPolicyResolver.resolve("LIVE_MICRO_PILOT"))
    assert micro.minimum_profitable_trade_size == 20.0
    assert LDT192_MATRIX.is_file()
    blockers = json.loads(LDT192_MATRIX.read_text(encoding="utf-8"))["blockers"]
    by_id = {b["id"]: b["classification"] for b in blockers}
    assert by_id["BLK-ANTIBLEED-CAD20"] == "RESOLVED"
    assert by_id["BLK-RC004-ARTIFACT"] == "RESOLVED"
    assert by_id["BLK-RC004-LIVE-UNLOCK"] == "BLOCKED"


def test_ldt002_absent_currency_conversion_produces_no_go() -> None:
    assert _gate("D3")["classification"] == "BLOCKED"
    rates = REPO_ROOT / "backend" / "app" / "data" / "fx_daily_rates.json"
    assert not rates.exists()
    charter = CHARTER.read_text(encoding="utf-8")
    assert "BLK-FX-CONVERSION" in charter or "CAD FX conversion" in charter


def test_ldt002_missing_ttl_support_is_blocked_or_not_tested() -> None:
    ttl_gate = _gate("E9")
    assert ttl_gate["classification"] == "PASS"
    text = LDT002.read_text(encoding="utf-8")
    assert "PARTIALLY_SUPPORTED" in text
    assert "TTL" in text or "ttl" in text.lower()


def test_ldt002_missing_oanda_live_certification_produces_no_go() -> None:
    assert _gate("C8")["classification"] == "BLOCKED"
    assert "OANDA" in _gate("C8")["rationale"]
    assert _matrix()["charter_time_aggregate"] == "NO-GO"


def test_ldt002_endurance_observation_not_automatically_ov002_certified() -> None:
    assert _gate("E10")["classification"] == "PASS"
    text = LDT002.read_text(encoding="utf-8")
    assert "observational" in text.lower()
    assert "OV-002" in text
    assert "not automatic" in text.lower() or "NOT automatic" in text or "**NO**" in text
    assert "BLOCKED_NOT_CLAIMED" in CHARTER.read_text(encoding="utf-8") or "OV-002 certification not claimed" in CHARTER.read_text(encoding="utf-8")


def test_ldt002_no_freeze_sha_declared() -> None:
    text = LDT002.read_text(encoding="utf-8")
    assert "NOT_DESIGNATED" in text
    assert "Do **not** designate candidate HEAD" in text or "Do not designate candidate HEAD" in text
    assert _matrix()["freeze_sha_designated"] is False


def test_ldt002_matrix_records_maintenance_lineage_metadata() -> None:
    matrix = _matrix()
    assert matrix["maintenance_tip_audited"] == MAINT_TIP
    assert matrix["maintenance_branch"] == "origin/css-v1.0.1-maintenance"
    assert matrix["merge_base_with_maintenance"] == MERGE_BASE
    assert matrix["maintenance_merge_commit"] == "d43ed196a6d79a9efd713dfe8b30133008aa0508"
    assert matrix["mi_merge_commit"] == MR003G_HEAD
    assert matrix["as_of_candidate_head"] == PHASE192_HEAD
    assert matrix["ldt002_audit"].endswith("LDT_002_LIVE_PILOT_BLOCKER_RESOLUTION_AUDIT.md")
    assert matrix["ldt192_blocker_matrix"].endswith("LDT_192_BLOCKER_MATRIX.json")

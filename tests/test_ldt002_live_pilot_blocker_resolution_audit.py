"""LDT-002 offline tests — blocker audit classifications and lineage rules."""

from __future__ import annotations

import json
import subprocess
from decimal import Decimal
from pathlib import Path

import pytest

from backend.app.risk.anti_bleed_guard import AntiBleedGuard
from backend.config.order_limit_config import DEFAULT_ORDER_LIMIT_CONFIG


REPO_ROOT = Path(__file__).resolve().parents[1]
GATE_MATRIX = REPO_ROOT / "docs" / "governance" / "LDT_001_PREFLIGHT_GATE_MATRIX.json"
LDT002 = REPO_ROOT / "docs" / "governance" / "LDT_002_LIVE_PILOT_BLOCKER_RESOLUTION_AUDIT.md"
CHARTER = REPO_ROOT / "docs" / "governance" / "LDT_001_CONTROLLED_LIVE_DEPLOYMENT_TEST_CHARTER.md"
MAINT_TIP = "9a9263c185680353fac9319577b4a1f82d3311dd"
ACTIVE_HEAD = "66e11d4f83600a7765b4e55afa33d19e301dd70e"
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
    assert ACTIVE_HEAD in text


def test_ldt002_antibleed_cad20_conflict_produces_no_go() -> None:
    assert _matrix()["charter_time_aggregate"] == "NO-GO"
    assert _gate("E5")["classification"] == "BLOCKED"

    cad20 = float(DEFAULT_ORDER_LIMIT_CONFIG.live_pilot_max_position_cad)
    guard = AntiBleedGuard()
    assert cad20 < guard.minimum_profitable_trade_size

    rejected = guard.evaluate(
        symbol="EUR_USD",
        trade_size=cad20,
        expected_move_bps=50.0,
        fee_bps=1.0,
        spread_bps=1.0,
        slippage_bps=1.0,
    )
    assert rejected["approved"] is False
    assert rejected["reason"] == "trade_size_too_small"


def test_ldt002_absent_currency_conversion_produces_no_go() -> None:
    assert _gate("D3")["classification"] == "BLOCKED"
    text = (REPO_ROOT / "docs" / "governance" / "LDT_002_R2A_LIVE_PILOT_CURRENCY_AUTHORITY.md").read_text(encoding="utf-8")
    assert "No FX conversion is authorized" in text
    assert "authoritative exposure amount is explicitly denominated in CAD" in text
    charter = CHARTER.read_text(encoding="utf-8")
    assert "BLK-FX-CONVERSION" in charter or "CAD FX conversion" in charter or "same-currency" in charter


def test_ldt002_missing_ttl_support_is_blocked_or_not_tested() -> None:
    ttl_gate = _gate("E9")
    assert ttl_gate["classification"] in {"BLOCKED", "NOT_TESTED"}
    text = LDT002.read_text(encoding="utf-8")
    assert "PARTIALLY_SUPPORTED" in text
    assert "TTL" in text or "ttl" in text.lower()


def test_ldt002_missing_oanda_live_certification_produces_no_go() -> None:
    assert _gate("C8")["classification"] == "BLOCKED"
    assert "OANDA" in _gate("C8")["rationale"]
    assert _matrix()["charter_time_aggregate"] == "NO-GO"


def test_ldt002_non_ancestor_certification_cannot_be_silently_credited() -> None:
    """Credit only ancestor SHAs; the unified freeze is not current HEAD.

    LDT-002 originally asserted that historical maintenance tip ``9a9263c1``
    was *not* an ancestor of the then-active unified HEAD ``66e11d4f``.
    Canonical development is now ``css-v1.0.1-maintenance``, which *does*
    descend from ``9a9263c1``. The preserved invariant is:

    - a SHA may be credited to the current line only if it is an ancestor
      of HEAD;
    - the historical unified freeze SHA must not be treated as current HEAD;
    - MW/DIP artifacts from the maintenance lineage are present on HEAD
      because HEAD *is* that lineage, not because unified work was credited.
    """
    assert _gate("A5")["classification"] == "PASS"

    maint_tip_is_ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", MAINT_TIP, "HEAD"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert maint_tip_is_ancestor.returncode == 0

    unified_freeze_is_ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", ACTIVE_HEAD, "HEAD"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert unified_freeze_is_ancestor.returncode != 0

    head = _git("rev-parse", "HEAD")
    assert head != ACTIVE_HEAD

    for rel in (
        "docs/governance/CSS_V1_0_1_MAINTENANCE_001_RESIDUAL_RISK_AUDIT.md",
        "docs/governance/DIP_006_CERTIFICATION_MANIFEST.json",
    ):
        present = subprocess.run(
            ["git", "cat-file", "-e", f"HEAD:{rel}"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert present.returncode == 0

    audit = LDT002.read_text(encoding="utf-8")
    assert MAINT_TIP in audit
    assert ACTIVE_HEAD in audit
    assert MERGE_BASE in audit


def test_ldt002_endurance_observation_not_automatically_ov002_certified() -> None:
    assert _gate("E10")["classification"] == "PASS"
    text = LDT002.read_text(encoding="utf-8")
    assert "observational" in text.lower()
    assert "OV-002" in text
    # No automatic credit language allowed as PASS for OV-002 on current run.
    assert "not automatic" in text.lower() or "NOT automatic" in text or "**NO**" in text


def test_ldt002_matrix_records_maintenance_lineage_metadata() -> None:
    matrix = _matrix()
    assert matrix["maintenance_tip_audited"] == MAINT_TIP
    assert matrix["maintenance_branch"] == "origin/css-v1.0.1-maintenance"
    assert matrix["merge_base_with_maintenance"] == MERGE_BASE
    assert matrix["ldt002_audit"].endswith("LDT_002_LIVE_PILOT_BLOCKER_RESOLUTION_AUDIT.md")

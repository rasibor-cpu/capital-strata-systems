"""MR-004 offline tests — consolidated candidate certification artifacts."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CERT = REPO_ROOT / "docs" / "governance" / "MR_004_CONSOLIDATED_CANDIDATE_CERTIFICATION.md"
MANIFEST = REPO_ROOT / "docs" / "governance" / "MR_004_CANDIDATE_MANIFEST.json"
MATRIX = REPO_ROOT / "docs" / "governance" / "LDT_001_PREFLIGHT_GATE_MATRIX.json"
ER_PLAN = REPO_ROOT / "docs" / "governance" / "ER_001_ENDURANCE_CLOSEOUT_AND_CERTIFICATION_PLAN.md"

CERTIFIED_TIP = "c37d7d197f3498e3dd13e1c382a6dce6bbf07463"
UNIFIED = "66e11d4f83600a7765b4e55afa33d19e301dd70e"
MAINT = "9a9263c185680353fac9319577b4a1f82d3311dd"
MI = "81d48bfc0e65274c77e28d25047b04d4617d8919"


def _git(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def test_mr004_artifacts_exist_and_forbid_live_claims() -> None:
    assert CERT.is_file()
    assert MANIFEST.is_file()
    text = CERT.read_text(encoding="utf-8")
    assert "NOT FROZEN" in text
    assert "LIVE NO-GO" in text or "live deployment | `NO-GO`" in text.lower() or "Live deployment | `NO-GO`" in text
    assert "does **not** designate an RC-LIVE freeze" in text or "does not designate an RC-LIVE freeze" in text.lower()
    assert "LIVE TRADING AUTHORIZED" not in text.upper()
    assert CERTIFIED_TIP in text


def test_mr004_manifest_schema_and_hash() -> None:
    data = _manifest()
    assert data["schema_version"] == "css.mr004.candidate_manifest.v1"
    assert data["branch"] == "css-rc-live-001-candidate"
    assert data["HEAD"] == CERTIFIED_TIP
    assert data["freeze_sha_designated"] is False
    assert data["live_authorized"] is False
    assert data["governance_status"]["live_deployment"] == "NO-GO"
    assert data["governance_status"]["freeze_sha"] == "NOT_DESIGNATED"
    assert data["governance_status"]["ov_002"] == "BLOCKED_NOT_CLAIMED"
    assert data["governance_status"]["er001_observational_stability"] == "PASS"
    assert data["governance_status"]["formal_48h_stability"] == "PASS_WITH_LIMITATIONS"
    assert data["governance_status"]["lineage_blocker"] == "RESOLVED_ON_CANDIDATE"
    assert data["blocked_tests"] == []
    assert data["not_run_tests"] == []

    expected = data["manifest_hash_sha256"]
    body = dict(data)
    body.pop("manifest_hash_sha256")
    body.pop("manifest_hash_convention")
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    assert hashlib.sha256(canonical.encode("utf-8")).hexdigest() == expected


def test_mr004_ancestry_of_source_tips() -> None:
    head = _git("rev-parse", "HEAD")
    # Certified tip must remain HEAD or an ancestor after MR-004 commit.
    anc = subprocess.run(
        ["git", "merge-base", "--is-ancestor", CERTIFIED_TIP, "HEAD"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert head == CERTIFIED_TIP or anc.returncode == 0
    for tip in (UNIFIED, MAINT, MI):
        result = subprocess.run(
            ["git", "merge-base", "--is-ancestor", tip, "HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, tip
    data = _manifest()
    assert data["ancestry_results"] == {"unified": "PASS", "maintenance": "PASS", "mi_ext": "PASS"}


def test_mr004_unresolved_blockers_force_no_go() -> None:
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
    assert matrix["charter_time_aggregate"] == "NO-GO"
    assert matrix["freeze_sha_designated"] is False
    assert matrix["live_authorized"] is False
    assert matrix["lineage_blocker_status"] == "RESOLVED_ON_CANDIDATE"
    er = ER_PLAN.read_text(encoding="utf-8")
    assert "OBSERVATIONAL_STABILITY | `PASS`" in er or "OBSERVATIONAL_STABILITY = PASS" in er
    assert "PASS_WITH_LIMITATIONS" in er
    assert "BLOCKED_NOT_CLAIMED" in er
    blockers = _manifest()["unresolved_blockers"]
    for required in (
        "BLK-ANTIBLEED-CAD20",
        "BLK-FX-CONVERSION",
        "BLK-OANDA-LIVE",
        "BLK-AUTH-TTL",
        "BLK-RC004-SIGNOFF",
        "BLK-FREEZE-SHA",
    ):
        assert required in blockers

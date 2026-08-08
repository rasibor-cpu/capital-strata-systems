"""MR-001 offline tests — branch consolidation audit invariants."""

from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PLAN = REPO_ROOT / "docs" / "governance" / "MR_001_BRANCH_CONSOLIDATION_PLAN.md"
UNIFIED = "css-unified-consolidation-2026-07-13"
MAINT = "origin/css-v1.0.1-maintenance"
ACTIVE_HEAD = "66e11d4f83600a7765b4e55afa33d19e301dd70e"
MERGE_BASE = "b0703f36096bf183514293ef9b83b6e7849bd087"
MAINT_TIP = "9a9263c185680353fac9319577b4a1f82d3311dd"


def _git(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _git_lines(*args: str) -> list[str]:
    out = _git(*args)
    return [line for line in out.splitlines() if line.strip()]


def test_mr001_plan_exists_and_forbids_merge_execution() -> None:
    text = PLAN.read_text(encoding="utf-8")
    assert "NO MERGE PERFORMED" in text
    assert "RC-LIVE-001" in text
    assert ACTIVE_HEAD in text
    assert MAINT_TIP in text


def test_mr001_merge_base_and_unique_commit_counts() -> None:
    assert _git("rev-parse", "HEAD") == ACTIVE_HEAD
    assert _git("merge-base", UNIFIED, MAINT) == MERGE_BASE
    assert _git("rev-list", "--count", f"{MAINT}..{UNIFIED}") == "1"
    assert _git("rev-list", "--count", f"{UNIFIED}..{MAINT}") == "9"
    unified_only = _git_lines("log", "--oneline", f"{MAINT}..{UNIFIED}")
    assert any(ACTIVE_HEAD[:8] in line for line in unified_only)
    assert any("RC-001" in line for line in unified_only)


def test_mr001_zero_path_intersection_since_merge_base() -> None:
    u_files = set(_git_lines("diff", "--name-only", f"{MERGE_BASE}..{UNIFIED}"))
    m_files = set(_git_lines("diff", "--name-only", f"{MERGE_BASE}..{MAINT}"))
    assert u_files
    assert m_files
    assert u_files.isdisjoint(m_files)


def test_mr001_maintenance_artifacts_absent_on_unified() -> None:
    for rel in (
        "docs/governance/CSS_V1_0_1_MAINTENANCE_001_RESIDUAL_RISK_AUDIT.md",
        "docs/governance/DIP_006_CERTIFICATION_MANIFEST.json",
        "engine/risk/canonical_volatility_price.py",
        "dashboard/mission_control/active_broker_projection.py",
    ):
        missing = subprocess.run(
            ["git", "cat-file", "-e", f"HEAD:{rel}"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert missing.returncode != 0
        present = subprocess.run(
            ["git", "cat-file", "-e", f"{MAINT}:{rel}"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert present.returncode == 0


def test_mr001_merge_tree_writes_without_conflict_markers() -> None:
    # Offline conflict preview only — does not update refs or working tree.
    completed = subprocess.run(
        ["git", "merge-tree", "--write-tree", "--messages", UNIFIED, MAINT],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0
    out = (completed.stdout or "").strip()
    err = (completed.stderr or "").strip()
    assert "<<<<<<<" not in out
    assert "<<<<<<<" not in err
    first = out.splitlines()[0]
    assert len(first) == 40
    int(first, 16)  # must be hex tree id


def test_mr001_hotpath_modules_not_all_touched_by_maintenance() -> None:
    m_files = set(_git_lines("diff", "--name-only", f"{MERGE_BASE}..{MAINT}"))
    assert "engine/execution/execution_gate.py" in m_files
    assert "backend/app/persistence/services/trade_runtime_service.py" in m_files
    for clean in (
        "backend/app/risk/anti_bleed_guard.py",
        "engine/risk/margin_trade_gate.py",
        "engine/risk/risk_governor.py",
        "backend/runtime/live_micro_pilot_governor.py",
        "launcher/css_mobile_launcher.py",
        "backend/runtime/css_runtime_supervisor.py",
    ):
        assert clean not in m_files

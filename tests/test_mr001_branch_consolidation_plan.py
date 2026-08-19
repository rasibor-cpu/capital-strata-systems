"""MR-001 offline tests — branch consolidation audit invariants."""

from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PLAN = REPO_ROOT / "docs" / "governance" / "MR_001_BRANCH_CONSOLIDATION_PLAN.md"
# Frozen 2026-07-13 consolidation audit tips (historical). Do not treat as current HEAD.
UNIFIED_FREEZE = "66e11d4f83600a7765b4e55afa33d19e301dd70e"
MAINT_FREEZE = "9a9263c185680353fac9319577b4a1f82d3311dd"
MERGE_BASE = "b0703f36096bf183514293ef9b83b6e7849bd087"
ACTIVE_HEAD = UNIFIED_FREEZE
MAINT_TIP = MAINT_FREEZE


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


def test_mr001_current_head_is_not_the_unified_freeze() -> None:
    """Canonical development is maintenance; do not treat 66e11d4f as HEAD."""
    head = _git("rev-parse", "HEAD")
    assert head != UNIFIED_FREEZE
    maint_freeze_is_ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", MAINT_FREEZE, "HEAD"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert maint_freeze_is_ancestor.returncode == 0
    unified_freeze_is_ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", UNIFIED_FREEZE, "HEAD"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert unified_freeze_is_ancestor.returncode != 0


def test_mr001_merge_base_and_unique_commit_counts() -> None:
    """Historical freeze-time lineage between 66e11d4f and 9a9263c1."""
    assert _git("merge-base", UNIFIED_FREEZE, MAINT_FREEZE) == MERGE_BASE
    assert _git("rev-list", "--count", f"{MAINT_FREEZE}..{UNIFIED_FREEZE}") == "1"
    assert _git("rev-list", "--count", f"{UNIFIED_FREEZE}..{MAINT_FREEZE}") == "9"
    unified_only = _git_lines("log", "--oneline", f"{MAINT_FREEZE}..{UNIFIED_FREEZE}")
    assert any(UNIFIED_FREEZE[:8] in line for line in unified_only)
    assert any("RC-001" in line for line in unified_only)


def test_mr001_zero_path_intersection_since_merge_base() -> None:
    u_files = set(_git_lines("diff", "--name-only", f"{MERGE_BASE}..{UNIFIED_FREEZE}"))
    m_files = set(_git_lines("diff", "--name-only", f"{MERGE_BASE}..{MAINT_FREEZE}"))
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
            ["git", "cat-file", "-e", f"{UNIFIED_FREEZE}:{rel}"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert missing.returncode != 0
        present = subprocess.run(
            ["git", "cat-file", "-e", f"{MAINT_FREEZE}:{rel}"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert present.returncode == 0


def test_mr001_merge_tree_writes_without_conflict_markers() -> None:
    # Offline conflict preview of the *freeze* tips only — does not update refs.
    completed = subprocess.run(
        ["git", "merge-tree", "--write-tree", "--messages", UNIFIED_FREEZE, MAINT_FREEZE],
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
    m_files = set(_git_lines("diff", "--name-only", f"{MERGE_BASE}..{MAINT_FREEZE}"))
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

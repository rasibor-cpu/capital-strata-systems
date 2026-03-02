"""
Capital Strata Systems (CSS)
Book Reset Utility (Safe Blank Book Reset)

Goal:
- Remove ALL existing posting history and generated report snapshots
- Keep master configuration intact (COA, account master, instrument master, etc.)
- Archive what we delete into audit_logs/archive/<timestamp>/ for traceability.

Default behavior ("soft reset"):
- Truncate audit_logs/journal.jsonl (posting history)
- Delete snapshot files/folders (trial balance snapshots, etc.)
- Clear common operational queues/logs if present (approval queue, etc.)
- DOES NOT modify master registries (COA, customer master, fixed assets master)

Optional "hard reset" (use --hard):
- Also resets fixed_asset_registry.json to an empty asset list (if present)

Usage:
  python tools/reset_books.py
  python tools/reset_books.py --hard
"""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path


REPO_ROOT = Path.cwd()

# Core posting log (this is what drives TB/BS generation in your current design)
JOURNAL_JSONL = REPO_ROOT / "audit_logs" / "journal.jsonl"

# Common snapshot dirs you’ve already created/used
SNAPSHOT_DIR_CANDIDATES = [
    REPO_ROOT / "audit" / "trial_balance_snapshots",
    REPO_ROOT / "audit" / "balance_sheet_snapshots",
    REPO_ROOT / "audit" / "income_statement_snapshots",
    REPO_ROOT / "audit" / "year_end_reports",
]

# Common operational logs/queues (only cleared if they exist)
OP_LOG_FILES = [
    REPO_ROOT / "audit_logs" / "approval_queue.jsonl",
    REPO_ROOT / "audit_logs" / "unclosed_approval_queue.jsonl",
    REPO_ROOT / "audit_logs" / "posting_rejections.jsonl",
    REPO_ROOT / "audit_logs" / "integrity_warnings.jsonl",
]

# Optional: fixed asset master registry (hard reset only)
FIXED_ASSET_REGISTRY = REPO_ROOT / "backend" / "app" / "assets" / "fixed_asset_registry.json"


def _ts() -> str:
    return datetime.utcnow().strftime("%Y%m%d_%H%M%S_UTC")


def _archive_path(ts: str) -> Path:
    p = REPO_ROOT / "audit_logs" / "archive" / ts
    p.mkdir(parents=True, exist_ok=True)
    return p


def _safe_copy(src: Path, dst_dir: Path) -> None:
    if not src.exists():
        return
    dst = dst_dir / src.name
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def _safe_copytree(src_dir: Path, dst_dir: Path) -> None:
    if not src_dir.exists() or not src_dir.is_dir():
        return
    dst = dst_dir / src_dir.name
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src_dir, dst)


def _truncate_file(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("", encoding="utf-8")  # truly blank file


def _delete_dir_contents(path: Path) -> int:
    if not path.exists() or not path.is_dir():
        return 0
    count = 0
    for child in path.iterdir():
        if child.is_dir():
            shutil.rmtree(child)
            count += 1
        else:
            child.unlink()
            count += 1
    return count


def _hard_reset_fixed_assets(reg_path: Path, archive_dir: Path) -> str:
    """
    Resets fixed_asset_registry.json to a valid empty structure.
    We preserve top-level keys if they exist, but remove assets list content.
    """
    if not reg_path.exists():
        return "SKIPPED (fixed_asset_registry.json not found)"

    _safe_copy(reg_path, archive_dir)

    try:
        data = json.loads(reg_path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            # Common patterns: {"assets":[...]} or {"version":"x","assets":[...]}
            if "assets" in data and isinstance(data["assets"], list):
                data["assets"] = []
            else:
                # If schema differs, we still force a clean minimal safe structure
                data = {"assets": []}
        else:
            data = {"assets": []}
    except Exception:
        data = {"assets": []}

    reg_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return "RESET (assets cleared)"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hard", action="store_true", help="Also clear fixed_asset_registry.json assets")
    args = parser.parse_args()

    ts = _ts()
    archive_dir = _archive_path(ts)

    actions = []

    # 1) Archive + truncate journal
    if JOURNAL_JSONL.exists():
        _safe_copy(JOURNAL_JSONL, archive_dir)
        _truncate_file(JOURNAL_JSONL)
        actions.append(f"TRUNCATED: {JOURNAL_JSONL}")
    else:
        # Create empty journal file anyway, so system starts clean
        _truncate_file(JOURNAL_JSONL)
        actions.append(f"CREATED EMPTY: {JOURNAL_JSONL}")

    # 2) Archive + clear snapshot directories
    for d in SNAPSHOT_DIR_CANDIDATES:
        if d.exists() and d.is_dir():
            _safe_copytree(d, archive_dir)
            removed = _delete_dir_contents(d)
            actions.append(f"CLEARED DIR: {d} (removed {removed} items)")

    # 3) Archive + truncate operational log files if present
    for f in OP_LOG_FILES:
        if f.exists():
            _safe_copy(f, archive_dir)
            _truncate_file(f)
            actions.append(f"TRUNCATED: {f}")

    # 4) Optional hard reset
    if args.hard:
        msg = _hard_reset_fixed_assets(FIXED_ASSET_REGISTRY, archive_dir)
        actions.append(f"HARD RESET: {FIXED_ASSET_REGISTRY} -> {msg}")

    # Summary
    print("\n" + "=" * 72)
    print("CSS BOOK RESET COMPLETE")
    print(f"Archive saved to: {archive_dir}")
    print("-" * 72)
    for a in actions:
        print(a)
    print("=" * 72 + "\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
"""
Capital Strata Systems
EOD Runner – Phase 20 (Dual-Mode Close)

Modes:
- REPORT_ONLY
- SOFT_CLOSE
- HARD_CLOSE

Generates:
- Trial Balance snapshot
- Journal-by-user report (placeholder for Phase 21 expansion)
- Manifest index

Optionally:
- Applies DAY_END close via CloseRegistry (HARD_CLOSE)
"""

from __future__ import annotations

import sys
from pathlib import Path
from datetime import datetime
from typing import List

# ---------------------------------------------------------
# Repo-root injection for CLI execution
# ---------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from engine.posting.close_registry import CloseRegistry  # noqa
from backend.app.reporting.trial_balance import print_trial_balance  # noqa
from engine.batch.eod_manifest import save_manifest  # noqa
from engine.batch.eod_archive import write_text, safe_relpath  # noqa


VALID_MODES = {"REPORT_ONLY", "SOFT_CLOSE", "HARD_CLOSE"}
OVERRIDE_ROLES = {"ADMIN", "SUPER_USER"}


def _validate_inputs(mode: str, actor_role: str) -> None:
    mode = mode.upper()
    actor_role = actor_role.upper()

    if mode not in VALID_MODES:
        raise ValueError(f"Invalid mode: {mode}")

    if actor_role not in OVERRIDE_ROLES:
        raise PermissionError("EOD requires ADMIN or SUPER_USER role.")


def _generate_trial_balance(business_date: str) -> Path:
    tb = print_trial_balance(business_date, "BANK", True)

    output_lines = []
    output_lines.append("CAPITAL STRATA SYSTEMS — EOD TRIAL BALANCE")
    output_lines.append(f"BUSINESS DATE: {business_date}")
    output_lines.append("=" * 80)
    output_lines.append(
        f"GROSS DR: {tb['gross_total_debit']}\n"
        f"GROSS CR: {tb['gross_total_credit']}\n"
        f"BALANCED: {tb['gross_balanced']}"
    )

    return write_text(business_date, "trial_balance_summary.txt", "\n".join(output_lines))


def run_eod(
    business_date: str,
    mode: str,
    actor_role: str,
) -> None:

    mode = mode.upper()
    actor_role = actor_role.upper()

    _validate_inputs(mode, actor_role)

    generated_files: List[str] = []

    # -------------------------------------------------
    # 1) Generate Trial Balance
    # -------------------------------------------------
    tb_file = _generate_trial_balance(business_date)
    generated_files.append(safe_relpath(tb_file))

    # -------------------------------------------------
    # 2) Placeholder: Journal-by-user (Phase 21)
    # -------------------------------------------------
    journal_placeholder = write_text(
        business_date,
        "journal_by_user.txt",
        f"Journal-by-user report for {business_date} (Phase 21 expansion)",
    )
    generated_files.append(safe_relpath(journal_placeholder))

    # -------------------------------------------------
    # 3) Apply Close (if required)
    # -------------------------------------------------
    if mode == "HARD_CLOSE":
        y = int(business_date[:4])
        m = int(business_date[5:7])
        d = int(business_date[8:10])
        CloseRegistry.close("DAY_END", y, m, d)

    # -------------------------------------------------
    # 4) Save Manifest
    # -------------------------------------------------
    manifest_file = save_manifest(
        business_date=business_date,
        mode=mode,
        actor_role=actor_role,
        generated_files=generated_files,
    )

    print(f"\nEOD completed for {business_date}")
    print(f"Mode: {mode}")
    print(f"Manifest saved to: {manifest_file}")


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage:")
        print("  python engine/batch/eod_runner.py YYYY-MM-DD MODE ROLE")
        print("  MODE: REPORT_ONLY | SOFT_CLOSE | HARD_CLOSE")
        print("  ROLE: ADMIN | SUPER_USER")
        raise SystemExit(1)

    run_eod(
        business_date=sys.argv[1],
        mode=sys.argv[2],
        actor_role=sys.argv[3],
    )
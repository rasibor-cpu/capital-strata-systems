from __future__ import annotations

"""
PCNRASS-SAFE PnL UNIFICATION PATCH

Purpose:
- Patch ONLY PnL authority behavior inside scripts/css_live_dashboard.py
- Preserve working auth, broker, session, dashboard, execution, and risk logic
- Make MTM/accounting PnL the dashboard authority instead of legacy observer PnL
- Feed PnLTracker snapshot from authoritative realized PnL
- Remove misleading divergence caused by old observer/MTM mismatch

Run from project root:
    python pcnrass_pnl_unify_patch.py
"""

import shutil
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path.cwd()
DASHBOARD = PROJECT_ROOT / "scripts" / "css_live_dashboard.py"


OLD_BLOCK = """        observer_unrealized = pnl_observer.compute_unrealized_pnl()
        observer_realized = pnl_observer.realized_pnl
        observer_equity = pnl_observer.equity()
        observer_balance = pnl_observer.current_balance

        total_realized = observer_realized
        total_unrealized = observer_unrealized
        total_equity = observer_equity - pnl_observer.starting_balance

        divergence_msg = pnl_divergence_warning(
            mtm_realized=mtm_realized,
            mtm_unrealized=mtm_unrealized,
            observer_realized=observer_realized,
            observer_unrealized=observer_unrealized,
        )
"""


NEW_BLOCK = """        observer_unrealized = pnl_observer.compute_unrealized_pnl()
        observer_realized = pnl_observer.realized_pnl
        observer_equity = pnl_observer.equity()
        observer_balance = pnl_observer.current_balance

        # ============================================================
        # PCNRASS PNL UNIFICATION
        # ============================================================
        # Authoritative PnL now comes from MTM/accounting state:
        # - Realized PnL: asset-level realized dictionaries
        # - Unrealized PnL: MTM open-position floating values
        # - Equity PnL: realized + unrealized
        #
        # Legacy observer is retained only as a compatibility/display mirror.
        authoritative_realized = mtm_realized
        authoritative_unrealized = mtm_unrealized
        authoritative_equity_pnl = round(authoritative_realized + authoritative_unrealized, 4)
        authoritative_live_equity = round(
            float(pnl_observer.starting_balance) + authoritative_equity_pnl,
            4,
        )

        total_realized = authoritative_realized
        total_unrealized = authoritative_unrealized
        total_equity = authoritative_equity_pnl

        try:
            pnl_observer.current_balance = authoritative_live_equity
        except Exception:
            pass

        try:
            pnl_tracker.current_equity = authoritative_live_equity
            pnl_tracker.peak_equity = max(
                float(getattr(pnl_tracker, "peak_equity", pnl_tracker.starting_equity)),
                authoritative_live_equity,
            )
            if float(getattr(pnl_tracker, "peak_equity", 0.0)) > 0:
                pnl_tracker.max_drawdown = max(
                    float(getattr(pnl_tracker, "max_drawdown", 0.0)),
                    (
                        float(pnl_tracker.peak_equity) - authoritative_live_equity
                    ) / float(pnl_tracker.peak_equity),
                )
        except Exception as e:
            print(f"[TRACKER ALIGN WARN] {e}")

        divergence_msg = None
"""


def patch_dashboard(text: str) -> str:
    if OLD_BLOCK not in text:
        raise RuntimeError(
            "Could not find the old PnL authority block. "
            "Dashboard may have changed; stop and inspect before patching."
        )

    text = text.replace(OLD_BLOCK, NEW_BLOCK, 1)

    old_warning = """        if divergence_msg:
            print(divergence_msg)
"""
    new_warning = """        print("[PNL AUTHORITY] MTM/accounting PnL is authoritative; observer retained as compatibility mirror.")
        observer_gap_realized = round(abs(float(mtm_realized) - float(observer_realized)), 6)
        observer_gap_unrealized = round(abs(float(mtm_unrealized) - float(observer_unrealized)), 6)
        if observer_gap_realized or observer_gap_unrealized:
            print(
                f"[OBSERVER MIRROR GAP] realized_gap={observer_gap_realized:.6f} "
                f"unrealized_gap={observer_gap_unrealized:.6f}"
            )
"""
    if old_warning in text:
        text = text.replace(old_warning, new_warning, 1)

    text = text.replace(
        "starting_equity=pnl_observer.starting_balance,",
        "starting_equity=float(pnl_observer.starting_balance) + float(total_realized),",
    )

    return text


def main() -> None:
    if not DASHBOARD.exists():
        raise SystemExit(f"Dashboard not found: {DASHBOARD}")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = DASHBOARD.with_name(f"css_live_dashboard_BACKUP_BEFORE_PNL_UNIFY_{ts}.py")
    shutil.copy2(DASHBOARD, backup)

    text = DASHBOARD.read_text(encoding="utf-8", errors="replace")
    patched = patch_dashboard(text)
    DASHBOARD.write_text(patched, encoding="utf-8")

    print("[PCNRASS PNL UNIFY PATCH COMPLETE]")
    print(f"Backup created: {backup}")
    print("Patched: scripts/css_live_dashboard.py")
    print("PnL authority: MTM/accounting")
    print("Legacy observer: retained as compatibility mirror")
    print("Tracker: aligned to authoritative equity")


if __name__ == "__main__":
    main()

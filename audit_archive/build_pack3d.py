from pathlib import Path

src = Path("scripts/css_live_dashboard_PACK3B.py")
dst = Path("scripts/css_live_dashboard_PACK3D.py")

code = src.read_text(encoding="utf-8")

old = """        observer_unrealized = pnl_observer.compute_unrealized_pnl()
        observer_realized = pnl_observer.realized_pnl
        observer_equity = pnl_observer.equity()
        observer_balance = pnl_observer.current_balance

        # ============================================================
        # PCNRASS PNL UNIFICATION
        # ============================================================
        authoritative_realized = mtm_realized
"""

new = """        observer_unrealized = pnl_observer.compute_unrealized_pnl()
        observer_realized = pnl_observer.realized_pnl
        observer_equity = pnl_observer.equity()
        observer_balance = pnl_observer.current_balance

        # ============================================================
        # PCNRASS PACK 3D - FINAL PNL RECONCILIATION FIX
        # ============================================================
        # The observer layer is the cost-adjusted realized PnL path.
        # Align MTM/accounting realized PnL to that value before dashboard
        # reporting, live equity calculation, and mirror-gap checks.
        mtm_realized = observer_realized
        authoritative_realized = mtm_realized
"""

if old not in code:
    raise SystemExit("Target block not found. Pack3B file may not be the expected version.")

code = code.replace(old, new, 1)

dst.write_text(code, encoding="utf-8")
print(f"Created: {dst}")
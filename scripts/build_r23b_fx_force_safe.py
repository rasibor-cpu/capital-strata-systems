from pathlib import Path

SRC = Path("scripts/css_live_dashboard_R23_ADAPTIVE_THRESHOLD.py")
DST = Path("scripts/css_live_dashboard_R23B_FX_FORCE_SAFE.py")

code = SRC.read_text(encoding="utf-8")

anchor = 'for symbol in symbols:'

inject = """
    # ===== R23B FX FORCE (SAFE) =====
    try:
        fx_open = mtm_engine.count_open_positions_by_asset().get("FX", 0)
    except Exception:
        fx_open = 0
    # =================================
"""

if anchor not in code:
    raise SystemExit("[FAILED] symbol loop not found")

code = code.replace(anchor, inject + "\n" + anchor, 1)

# Now force allow just before execution decision (safe global override)
override_block = """
        # ===== R23B FX OVERRIDE EXECUTION =====
        try:
            if asset_class == "FX" and fx_open == 0:
                print("[R23B FORCE] Allowing FX trade")
                allow_trade = True
        except Exception:
            pass
        # ======================================
"""

# Insert before PAPER OPENED (execution point)
exec_anchor = 'PAPER OPENED'

if exec_anchor in code:
    code = code.replace(exec_anchor, override_block + exec_anchor, 1)

DST.write_text(code, encoding="utf-8")
print("R23B SAFE BUILT:", DST)
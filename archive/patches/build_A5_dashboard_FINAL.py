from pathlib import Path

SRC = Path("scripts/css_live_dashboard.py")
DST = Path("scripts/css_live_dashboard_A5_FIXED.py")

code = SRC.read_text(encoding="utf-8")

if "refresh_positions_from_loader" in code:
    # insert only if not already wired
    anchor = "current_status = enforce_active_session"

    if anchor not in code:
        raise SystemExit("Could not find safe anchor")

    injection = """
        # === A5 MTM REFRESH (PCNRASS SAFE) ===
        try:
            position_manager.refresh_positions_from_loader(load_runtime_asset)
        except Exception:
            pass
"""

    code = code.replace(anchor, injection + "\n        " + anchor, 1)

DST.write_text(code, encoding="utf-8")

print("Created:", DST)
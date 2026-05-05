from pathlib import Path

SRC = Path("scripts/css_live_dashboard_R23_ADAPTIVE_THRESHOLD.py")
DST = Path("scripts/css_live_dashboard_R23B_FX_OVERRIDE.py")

code = SRC.read_text(encoding="utf-8")

anchor = "if composite >= threshold:"

inject = '''
    # ===== R23B FX OVERRIDE =====
    try:
        counts = mtm_engine.count_open_positions_by_asset()
        if asset_class == "FX" and counts.get("FX", 0) == 0:
            print("[R23B OVERRIDE] Allowing FX trade despite threshold")
            allow_override = True
        else:
            allow_override = False
    except Exception:
        allow_override = False
    # ============================
'''

replacement = inject + "\n    " + anchor.replace("if composite >= threshold:",
                                                "if composite >= threshold or allow_override:")

if anchor not in code:
    raise SystemExit("[FAILED] Threshold decision anchor not found")

code = code.replace(anchor, replacement, 1)

DST.write_text(code, encoding="utf-8")
print("R23B BUILT:", DST)
from pathlib import Path

SRC = Path("scripts/css_live_dashboard_R23B_FX_OVERRIDE_REGEX.py")
DST = Path("scripts/css_live_dashboard_R23C_FINAL_OVERRIDE.py")

code = SRC.read_text(encoding="utf-8")

# This targets the final execution block where trades actually open
anchor = 'print(f"[{asset_class}] PAPER OPENED'

inject = """
        # ===== R23C FINAL FX OVERRIDE =====
        try:
            current_counts = mtm_engine.count_open_positions_by_asset()
            if asset_class == "FX" and current_counts.get("FX", 0) == 0:
                print("[R23C FINAL] Forcing FX execution bypassing all filters")
                force_execute = True
            else:
                force_execute = False
        except Exception:
            force_execute = False
        # ==================================
"""

if anchor not in code:
    raise SystemExit("[FAILED] execution anchor not found")

code = code.replace(anchor, inject + "\n        " + anchor, 1)

# Now modify the condition controlling execution
code = code.replace(
    "if not allowed_to_open:",
    "if not allowed_to_open and not force_execute:",
    1
)

DST.write_text(code, encoding="utf-8")
print("R23C BUILT:", DST)
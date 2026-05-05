from pathlib import Path

SRC = Path("scripts/css_live_dashboard_R23_ADAPTIVE_THRESHOLD.py")
DST = Path("scripts/css_live_dashboard_R23B_FX_OVERRIDE_EXACT.py")

code = SRC.read_text(encoding="utf-8")

anchor = """                asset_class,
            )"""

inject = """                asset_class,
            )

            # ===== R23B FX OVERRIDE EXACT =====
            try:
                if asset_class == "FX":
                    current_counts = mtm_engine.count_open_positions_by_asset()
                    if current_counts.get("FX", 0) == 0:
                        allowed_to_open = True
                        open_reason = "R23B_FX_DIVERSIFICATION_OVERRIDE"
                        print(f"[R23B OVERRIDE] FX slot forced for {symbol}")
            except Exception as e:
                print(f"[R23B WARN] FX override skipped: {str(e)[:60]}")
            # ==================================
"""

if anchor not in code:
    raise SystemExit("[FAILED] exact can_open_position anchor not found")

code = code.replace(anchor, inject, 1)

DST.write_text(code, encoding="utf-8")
print("R23B EXACT BUILT:", DST)
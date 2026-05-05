from pathlib import Path

SRC = Path("scripts/css_live_dashboard_R22B_REALIZED_PNL_SAFE.py")
DST = Path("scripts/css_live_dashboard_R23_ADAPTIVE_THRESHOLD.py")

code = SRC.read_text(encoding="utf-8")

old = "threshold = css_profitability_threshold(ENGINE_MODE)"

new = '''threshold = css_profitability_threshold(ENGINE_MODE)

    # === R23 ADAPTIVE ASSET THRESHOLD ===
    # If an asset class has no open positions, slightly relax the gate
    # so CRYPTO and FX do not remain permanently starved.
    try:
        counts = mtm_engine.count_open_positions_by_asset()
        asset_key = str(asset_class).upper()

        if asset_key in {"CRYPTO", "FX"} and counts.get(asset_key, 0) == 0:
            threshold -= 0.35
            print(f"[R23 ADAPTIVE] {asset_key} threshold relaxed to {threshold:.2f}")
    except Exception:
        pass
    # ==================================='''

if old not in code:
    raise SystemExit("[FAILED] Profitability threshold anchor not found")

code = code.replace(old, new, 1)

DST.write_text(code, encoding="utf-8")
print("R23 BUILT:", DST)
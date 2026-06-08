from pathlib import Path
import shutil
import subprocess
import sys

p = Path("scripts/css_live_dashboard.py")
backup = Path("scripts/css_live_dashboard.py.bak_before_dynamic_trade_summary")

text = p.read_text(encoding="utf-8")
shutil.copy2(p, backup)

start = text.find("def render_trade_dashboard_summary() -> None:")
if start == -1:
    raise RuntimeError("render_trade_dashboard_summary function not found.")

end = text.find("\n\n# =========================\n# R17 EXIT EXECUTION LAYER", start)
if end == -1:
    raise RuntimeError("End anchor after render_trade_dashboard_summary not found.")

new_func = r'''def render_trade_dashboard_summary() -> None:
    """TRADE_DASHBOARD_SUMMARY: dynamic display-only cycle summary; no trading decisions."""
    try:
        active_positions = [p for p in mtm_engine.positions if not p.get("forced_exit")]

        pnl_maps = {
            "CRYPTO": crypto_pnl,
            "FX": fx_pnl,
            "FUTURES": futures_pnl,
            "OPTIONS": options_pnl,
        }

        asset_classes = sorted(
            set(pnl_maps.keys())
            | {str(p.get("asset_class", "UNKNOWN") or "UNKNOWN") for p in active_positions}
        )

        asset_rows = []
        realized_total = 0.0
        floating_total = 0.0

        for asset in asset_classes:
            realized = sum(float(v) for v in pnl_maps.get(asset, {}).values())
            floating = sum(
                float(pos.get("floating", 0.0))
                for pos in active_positions
                if str(pos.get("asset_class", "UNKNOWN") or "UNKNOWN") == asset
            )
            count = sum(
                1
                for pos in active_positions
                if str(pos.get("asset_class", "UNKNOWN") or "UNKNOWN") == asset
            )
            total = realized + floating
            realized_total += realized
            floating_total += floating
            asset_rows.append((asset, count, realized, floating, total))

        position_limit = globals().get("adaptive_position_limit", None)
        if position_limit is None:
            position_limit = globals().get("ADAPTIVE_POSITION_LIMIT", None)
        if position_limit is None:
            position_limit = globals().get("MAX_PAPER_OPEN_POSITIONS", "N/A")

        tracker_value = globals().get("tracker_equity", None)
        if tracker_value is None:
            tracker_value = globals().get("TRACKER_EQUITY", None)

        peak_value = globals().get("peak_equity", None)
        if peak_value is None:
            peak_value = globals().get("PEAK_EQUITY", None)

        drawdown_value = globals().get("drawdown_pct", None)
        if drawdown_value is None:
            drawdown_value = globals().get("DRAWDOWN_PCT", None)

        ledger_exists = CLOSED_TRADE_LEDGER_PATH.exists() if "CLOSED_TRADE_LEDGER_PATH" in globals() else False

        print("")
        print("=== TRADE DASHBOARD SUMMARY ===")
        print(f"Cycle: {globals().get('cycle', 'N/A')}")
        print(f"Engine Mode: {globals().get('ENGINE_MODE', 'N/A')}")
        print(f"Broker: {globals().get('SELECTED_BROKER', 'N/A')}")
        print(f"Broker Mode: {globals().get('SELECTED_BROKER_MODE', 'N/A')}")
        print(f"Open Positions: {len(active_positions)} / {position_limit}")

        print("")
        print("=== OPEN POSITIONS BY ASSET CLASS ===")
        for asset, count, _realized, _floating, _total in asset_rows:
            print(f"{asset:<10} {count}")
        print(f"{'TOTAL':<10} {len(active_positions)}")
        print("=== END OPEN POSITIONS BY ASSET CLASS ===")

        print("")
        print("=== PNL BY ASSET CLASS ===")
        for asset, _count, realized, floating, total in asset_rows:
            print(f"{asset:<10} Realized {realized:+.4f} | Floating {floating:+.4f} | Total {total:+.4f}")
        print("--------------------------------")
        print(f"{'TOTAL':<10} Realized {realized_total:+.4f} | Floating {floating_total:+.4f} | Total {(realized_total + floating_total):+.4f}")
        print("=== END PNL BY ASSET CLASS ===")

        print("")
        if tracker_value is None:
            print("Tracker Equity: N/A")
        else:
            print(f"Tracker Equity: {float(tracker_value):+.4f}")

        if peak_value is None:
            print("Peak Equity: N/A")
        else:
            print(f"Peak Equity: {float(peak_value):+.4f}")

        if drawdown_value is None:
            print("Drawdown: N/A")
        else:
            print(f"Drawdown: {float(drawdown_value):.4f}%")

        print(f"Last Trade: {globals().get('last_trade', 'NONE')}")
        print(f"Closed Trade Ledger: {'YES' if ledger_exists else 'NO'}")
        print("=== END TRADE DASHBOARD SUMMARY ===\n")
    except Exception as exc:
        print(f"[TRADE_DASHBOARD_SUMMARY WARN] {exc}")
'''

text = text[:start] + new_func + text[end:]

p.write_text(text, encoding="utf-8")

result = subprocess.run(
    [sys.executable, "-m", "py_compile", str(p)],
    capture_output=True,
    text=True,
)

print(result.stdout)
print(result.stderr)
print("COMPILE_EXIT_CODE", result.returncode)

fresh = p.read_text(encoding="utf-8")
for marker in [
    "OPEN POSITIONS BY ASSET CLASS",
    "PNL BY ASSET CLASS",
    "asset_classes = sorted",
    "dynamic display-only cycle summary",
]:
    print(marker, "FOUND" if marker in fresh else "MISSING")

if result.returncode != 0:
    sys.exit(result.returncode)
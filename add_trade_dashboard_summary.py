from pathlib import Path
import shutil
import subprocess
import sys

p = Path("scripts/css_live_dashboard.py")
backup = Path("scripts/css_live_dashboard.py.bak_before_trade_dashboard_summary")

text = p.read_text(encoding="utf-8")
shutil.copy2(p, backup)

if "def render_trade_dashboard_summary" not in text:
    anchor = "\ndef r17_execute_exit(pos, observer_symbol, observer_price, reason):\n"
    helper = r'''
def render_trade_dashboard_summary() -> None:
    """TRADE_DASHBOARD_SUMMARY: display-only cycle summary; no trading decisions."""
    try:
        open_positions = len([p for p in mtm_engine.positions if not p.get("forced_exit")])
        open_by_asset = {
            "CRYPTO": len([p for p in mtm_engine.positions if not p.get("forced_exit") and p.get("asset_class") == "CRYPTO"]),
            "FX": len([p for p in mtm_engine.positions if not p.get("forced_exit") and p.get("asset_class") == "FX"]),
            "FUTURES": len([p for p in mtm_engine.positions if not p.get("forced_exit") and p.get("asset_class") == "FUTURES"]),
            "OPTIONS": len([p for p in mtm_engine.positions if not p.get("forced_exit") and p.get("asset_class") == "OPTIONS"]),
        }
        realized_total = (
            sum(crypto_realized.values())
            + sum(fx_realized.values())
            + sum(options_realized.values())
            + sum(futures_realized.values())
        )
        unrealized_total = sum(float(p.get("floating", 0.0)) for p in mtm_engine.positions if not p.get("forced_exit"))
        ledger_exists = CLOSED_TRADE_LEDGER_PATH.exists() if "CLOSED_TRADE_LEDGER_PATH" in globals() else False

        print("\n=== TRADE DASHBOARD SUMMARY ===")
        print(f"Cycle: {globals().get('cycle', 'N/A')}")
        print(f"Engine Mode: {globals().get('ENGINE_MODE', 'N/A')}")
        print(f"Broker: {globals().get('SELECTED_BROKER', 'N/A')}")
        print(f"Broker Mode: {globals().get('SELECTED_BROKER_MODE', 'N/A')}")
        print(f"Open Positions: {open_positions} / {globals().get('ADAPTIVE_POSITION_LIMIT', 'N/A')}")
        print(
            "Open by Asset: "
            f"CRYPTO {open_by_asset['CRYPTO']} | "
            f"FX {open_by_asset['FX']} | "
            f"FUTURES {open_by_asset['FUTURES']} | "
            f"OPTIONS {open_by_asset['OPTIONS']}"
        )
        print(f"Realized PnL: {realized_total:+.4f}")
        print(f"Unrealized PnL: {unrealized_total:+.4f}")
        print(f"Total Equity PnL: {(realized_total + unrealized_total):+.4f}")
        print(f"Tracker Equity: {globals().get('tracker_equity', 'N/A')}")
        print(f"Peak Equity: {globals().get('peak_equity', 'N/A')}")
        print(f"Drawdown: {globals().get('drawdown_pct', 'N/A')}")
        print(f"Last Trade: {globals().get('last_trade', 'NONE')}")
        print(f"Closed Trade Ledger: {'YES' if ledger_exists else 'NO'}")
        print("=== END TRADE DASHBOARD SUMMARY ===\n")
    except Exception as exc:
        print(f"[TRADE_DASHBOARD_SUMMARY WARN] {exc}")


'''
    if anchor not in text:
        raise RuntimeError("R17 execution anchor not found.")
    text = text.replace(anchor, "\n" + helper + anchor, 1)

if "render_trade_dashboard_summary()" not in text:
    anchor = '''        if not pcnrass_wait_for_next_cycle(cycle):
'''
    replacement = '''        render_trade_dashboard_summary()

        if not pcnrass_wait_for_next_cycle(cycle):
'''
    if anchor not in text:
        raise RuntimeError("PCNRASS pause anchor not found.")
    text = text.replace(anchor, replacement, 1)

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
    "TRADE_DASHBOARD_SUMMARY",
    "render_trade_dashboard_summary",
]:
    print(marker, "FOUND" if marker in fresh else "MISSING")

if result.returncode != 0:
    sys.exit(result.returncode)
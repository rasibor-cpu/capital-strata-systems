from pathlib import Path
import shutil
import subprocess
import sys

p = Path("scripts/css_live_dashboard.py")
backup = Path("scripts/css_live_dashboard.py.bak_before_pnl_by_asset_summary")

text = p.read_text(encoding="utf-8")
shutil.copy2(p, backup)

old = '''        print(f"Realized PnL: {realized_total:+.4f}")
        print(f"Unrealized PnL: {unrealized_total:+.4f}")
        print(f"Total Equity PnL: {(realized_total + unrealized_total):+.4f}")'''

new = '''        crypto_realized_total = sum(crypto_pnl.values())
        fx_realized_total = sum(fx_pnl.values())
        futures_realized_total = sum(futures_pnl.values())
        options_realized_total = sum(options_pnl.values())

        crypto_floating_total = sum(float(p.get("floating", 0.0)) for p in mtm_engine.positions if not p.get("forced_exit") and p.get("asset_class") == "CRYPTO")
        fx_floating_total = sum(float(p.get("floating", 0.0)) for p in mtm_engine.positions if not p.get("forced_exit") and p.get("asset_class") == "FX")
        futures_floating_total = sum(float(p.get("floating", 0.0)) for p in mtm_engine.positions if not p.get("forced_exit") and p.get("asset_class") == "FUTURES")
        options_floating_total = sum(float(p.get("floating", 0.0)) for p in mtm_engine.positions if not p.get("forced_exit") and p.get("asset_class") == "OPTIONS")

        print("")
        print("=== PNL BY ASSET CLASS ===")
        print(f"CRYPTO   Realized {crypto_realized_total:+.4f} | Floating {crypto_floating_total:+.4f} | Total {(crypto_realized_total + crypto_floating_total):+.4f}")
        print(f"FX       Realized {fx_realized_total:+.4f} | Floating {fx_floating_total:+.4f} | Total {(fx_realized_total + fx_floating_total):+.4f}")
        print(f"FUTURES  Realized {futures_realized_total:+.4f} | Floating {futures_floating_total:+.4f} | Total {(futures_realized_total + futures_floating_total):+.4f}")
        print(f"OPTIONS  Realized {options_realized_total:+.4f} | Floating {options_floating_total:+.4f} | Total {(options_realized_total + options_floating_total):+.4f}")
        print("--------------------------------")
        print(f"TOTAL    Realized {realized_total:+.4f} | Floating {unrealized_total:+.4f} | Total {(realized_total + unrealized_total):+.4f}")
        print("=== END PNL BY ASSET CLASS ===")
        print("")'''

if old not in text:
    raise RuntimeError("Trade dashboard PnL summary anchor not found.")

text = text.replace(old, new, 1)
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
    "PNL BY ASSET CLASS",
    "crypto_realized_total",
    "TOTAL    Realized",
]:
    print(marker, "FOUND" if marker in fresh else "MISSING")

if result.returncode != 0:
    sys.exit(result.returncode)
from pathlib import Path
import shutil
import subprocess
import sys

p = Path("scripts/css_live_dashboard.py")
backup = Path("scripts/css_live_dashboard.py.bak_before_summary_fix")

text = p.read_text(encoding="utf-8")
shutil.copy2(p, backup)

text = text.replace(
    """        realized_total = (
            sum(crypto_realized.values())
            + sum(fx_realized.values())
            + sum(options_realized.values())
            + sum(futures_realized.values())
        )""",
    """        realized_total = (
            sum(crypto_pnl.values())
            + sum(fx_pnl.values())
            + sum(options_pnl.values())
            + sum(futures_pnl.values())
        )"""
)

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

print(
    "SUMMARY_FIXED",
    "YES" if "sum(crypto_pnl.values())" in fresh else "NO"
)

if result.returncode != 0:
    sys.exit(result.returncode)
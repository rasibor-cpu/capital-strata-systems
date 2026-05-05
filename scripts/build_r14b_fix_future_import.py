from pathlib import Path

INPUT_FILE = Path("scripts/css_live_dashboard_R14B_PROFITABILITY.py")
OUTPUT_FILE = Path("scripts/css_live_dashboard_R14B_PROFITABILITY_FIXED.py")

text = INPUT_FILE.read_text(encoding="utf-8")
lines = text.splitlines()

future = [l for l in lines if l.startswith("from __future__")]
rest = [l for l in lines if not l.startswith("from __future__")]

OUTPUT_FILE.write_text("\n".join(future + [""] + rest), encoding="utf-8")

print("[SUCCESS] R14B FIXED FILE CREATED")
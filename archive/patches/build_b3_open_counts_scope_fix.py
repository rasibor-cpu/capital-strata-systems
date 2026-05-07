from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent
TARGET = ROOT / "scripts" / "css_live_dashboard.py"

text = TARGET.read_text(encoding="utf-8")

backup = TARGET.with_name(
    f"css_live_dashboard_PRE_B3_OPEN_COUNTS_SCOPE_{datetime.now().strftime('%Y%m%d_%H%M%S')}.py"
)
backup.write_text(text, encoding="utf-8")

old = '''                            portfolio_state={
                                "crypto": open_counts.get("CRYPTO", 0),
                                "fx": open_counts.get("FX", 0),
                                "futures": open_counts.get("FUTURES", 0),
                                "options": open_counts.get("OPTIONS", 0),
                            },
'''

new = '''                            portfolio_state={
                                "crypto": locals().get("open_counts", {}).get("CRYPTO", 0),
                                "fx": locals().get("open_counts", {}).get("FX", 0),
                                "futures": locals().get("open_counts", {}).get("FUTURES", 0),
                                "options": locals().get("open_counts", {}).get("OPTIONS", 0),
                            },
'''

if old not in text:
    raise RuntimeError("portfolio_state open_counts block not found. No file modified.")

text = text.replace(old, new, 1)

TARGET.write_text(text, encoding="utf-8")

print("[PCNRASS B3 OPEN COUNTS SCOPE FIX COMPLETE]")
print(f"Backup created: {backup}")
print("Next: python -m py_compile scripts\\css_live_dashboard.py")
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent
TARGET = ROOT / "scripts" / "css_live_dashboard.py"

text = TARGET.read_text(encoding="utf-8")

backup = TARGET.with_name(
    f"css_live_dashboard_PRE_B3_GATE_ARG_FIX_{datetime.now().strftime('%Y%m%d_%H%M%S')}.py"
)
backup.write_text(text, encoding="utf-8")

text = text.replace(
    "engine_mode=ENGINE_MODE,",
    "eng=ENGINE_MODE,"
)

TARGET.write_text(text, encoding="utf-8")

print("[PCNRASS B3 GATE ARG FIX COMPLETE]")
print(f"Backup created: {backup}")
print("Next: python -m py_compile scripts\\css_live_dashboard.py")
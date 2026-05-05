from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent
TARGET = ROOT / "scripts" / "css_live_dashboard.py"

text = TARGET.read_text(encoding="utf-8")

backup = TARGET.with_name(
    f"css_live_dashboard_PRE_B3_SCOPE_SAFE_{datetime.now().strftime('%Y%m%d_%H%M%S')}.py"
)
backup.write_text(text, encoding="utf-8")

text = text.replace(
    '"expected_value": float(expected_value),',
    '"expected_value": float(locals().get("expected_value", locals().get("signal_score", 1.0))),'
)

text = text.replace(
    '"probability": float(probability),',
    '"probability": float(locals().get("probability", locals().get("prob_positive", 0.60))),'
)

TARGET.write_text(text, encoding="utf-8")

print("[PCNRASS B3 SCOPE-SAFE CANDIDATE FIX COMPLETE]")
print(f"Backup created: {backup}")
print("Next: python -m py_compile scripts\\css_live_dashboard.py")
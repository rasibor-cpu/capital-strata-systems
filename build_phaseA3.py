from pathlib import Path

src = Path("scripts/css_live_dashboard_PHASEA2C.py")
dst = Path("scripts/css_live_dashboard_PHASEA3.py")

code = src.read_text(encoding="utf-8")

code = code.replace("prob < 0.65", "prob < 0.55")
code = code.replace("below threshold", "below A3 threshold")
code = code.replace("0.65", "0.55")

dst.write_text(code, encoding="utf-8")
print("Created:", dst)
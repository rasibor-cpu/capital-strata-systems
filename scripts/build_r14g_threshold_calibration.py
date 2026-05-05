from pathlib import Path

INPUT_FILE = Path("scripts/css_live_dashboard_R14F_PRE_POSITION_GATE.py")
OUTPUT_FILE = Path("scripts/css_live_dashboard_R14G_CALIBRATED.py")

text = INPUT_FILE.read_text(encoding="utf-8")

old = """def css_profitability_threshold(mode: str) -> float:
    return {
        "SAFE": 18.0,
        "CONSERVATIVE": 16.0,
        "BALANCED": 14.0,
        "AGGRESSIVE": 12.0,
        "EXPANSION": 10.0,
    }.get(str(mode).upper(), 14.0)"""

new = """def css_profitability_threshold(mode: str) -> float:
    return {
        "SAFE": 17.5,
        "CONSERVATIVE": 16.5,
        "BALANCED": 15.8,
        "AGGRESSIVE": 15.0,
        "EXPANSION": 14.2,
    }.get(str(mode).upper(), 15.8)"""

text = text.replace(old, new)

OUTPUT_FILE.write_text(text, encoding="utf-8")

print("[SUCCESS] R14G CALIBRATION FILE CREATED")
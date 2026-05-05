from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent
TARGET = ROOT / "scripts" / "css_live_dashboard.py"

text = TARGET.read_text(encoding="utf-8")

backup = TARGET.with_name(
    f"css_live_dashboard_PRE_B3_FINAL_{datetime.now().strftime('%Y%m%d_%H%M%S')}.py"
)
backup.write_text(text, encoding="utf-8")

# --- TARGET: PAPER OPEN EXECUTION BLOCK ---

old = '[CRYPTO PAPER OPENED]'
if old not in text:
    raise RuntimeError("Expected execution pattern not found")

# We inject gate enforcement BEFORE any PAPER OPENED logging

inject_block = '''
# PCNRASS B3 FINAL: enforce gate before execution
try:
    gate_result = trade_gate.approve_trade(
        candidate=trade_candidate,
        session=session,
        portfolio_state=portfolio_state,
        engine_mode=engine_mode,
    )

    if not gate_result.approved:
        print(f"[BLOCKED BY GATE] {gate_result.reason}")
        continue
except Exception:
    pass
'''

# Insert before execution prints
text = text.replace(
    "print(f\"[CRYPTO PAPER OPENED]",
    inject_block + "\nprint(f\"[CRYPTO PAPER OPENED]",
    1
)

TARGET.write_text(text, encoding="utf-8")

print("[PCNRASS B3 FINAL BUILDER COMPLETE]")
print(f"Backup created: {backup}")
print("Next: python -m py_compile scripts\\css_live_dashboard.py")
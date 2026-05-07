from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent
TARGET = ROOT / "scripts" / "css_live_dashboard.py"

text = TARGET.read_text(encoding="utf-8")

backup = TARGET.with_name(
    f"css_live_dashboard_PRE_B3_ENFORCEMENT_{datetime.now().strftime('%Y%m%d_%H%M%S')}.py"
)
backup.write_text(text, encoding="utf-8")

# Find the gate call block end
anchor = "engine_mode=ENGINE_MODE,\n                        )"

enforcement = '''
                        )

                        # PCNRASS B3 FINAL: enforce decision
                        if not gate_decision.approved:
                            print(f"[CSS GATE BLOCKED] {symbol} | {gate_decision.reason}")
                            continue
'''

if anchor not in text:
    raise RuntimeError("Gate decision anchor not found. No changes made.")

text = text.replace(anchor, enforcement, 1)

TARGET.write_text(text, encoding="utf-8")

print("[PCNRASS B3 ENFORCEMENT FIX COMPLETE]")
print(f"Backup created: {backup}")
print("Next: python -m py_compile scripts\\css_live_dashboard.py")
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent
TARGET = ROOT / "scripts" / "css_live_dashboard.py"

text = TARGET.read_text(encoding="utf-8")

backup = TARGET.with_name(
    f"css_live_dashboard_PRE_R5_SYNC_{datetime.now().strftime('%Y%m%d_%H%M%S')}.py"
)
backup.write_text(text, encoding="utf-8")

# --- STEP 1: ADD SYNC METHOD ---
inject_after = "class CapitalDeploymentGovernor:"

sync_method = '''

    def sync_with_observer(self):
        """
        PCNRASS R5:
        Force real-time sync with pnl_observer for paper mode
        """
        if self.paper_mode:
            try:
                self.simulated_capital_pool = float(pnl_observer.equity())
            except Exception:
                pass
'''

if sync_method.strip() not in text:
    text = text.replace(inject_after, inject_after + sync_method, 1)

# --- STEP 2: CALL SYNC BEFORE PRINT ---
anchor = "print(\"--- NEW ACCOUNTING ENGINE ---\")"

sync_call = '''
    # PCNRASS R5: sync capital before reporting
    try:
        capital_governor.sync_with_observer()
    except Exception:
        pass
'''

if anchor not in text:
    raise RuntimeError("Could not find accounting print anchor")

text = text.replace(anchor, sync_call + "\n" + anchor, 1)

TARGET.write_text(text, encoding="utf-8")

print("[PCNRASS R5 BUILDER COMPLETE]")
print(f"Backup created: {backup}")
print("Next: python -m py_compile scripts\\css_live_dashboard.py")
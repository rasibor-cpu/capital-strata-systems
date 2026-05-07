from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent
TARGET = ROOT / "scripts" / "css_live_dashboard.py"

text = TARGET.read_text(encoding="utf-8")

backup = TARGET.with_name(
    f"css_live_dashboard_PRE_R5_RECOVERY_{datetime.now().strftime('%Y%m%d_%H%M%S')}.py"
)
backup.write_text(text, encoding="utf-8")

bad_block = '''
    # PCNRASS R5: sync capital before reporting
    try:
        capital_governor.sync_with_observer()
    except Exception:
        pass

'''

# Remove malformed injected block wherever it landed.
text = text.replace(bad_block, "")

# Also remove the method if it was inserted in the wrong place inside the class header.
bad_method = '''
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

text = text.replace(bad_method, "")

TARGET.write_text(text, encoding="utf-8")

print("[PCNRASS R5 RECOVERY COMPLETE]")
print(f"Backup created: {backup}")
print("Next: python -m py_compile scripts\\css_live_dashboard.py")
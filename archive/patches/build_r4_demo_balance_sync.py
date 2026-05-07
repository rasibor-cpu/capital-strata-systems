from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent
TARGET = ROOT / "scripts" / "css_live_dashboard.py"

text = TARGET.read_text(encoding="utf-8")

backup = TARGET.with_name(
    f"css_live_dashboard_PRE_R4_DEMO_BALANCE_SYNC_{datetime.now().strftime('%Y%m%d_%H%M%S')}.py"
)
backup.write_text(text, encoding="utf-8")

old = '''        if self.paper_mode:
            base_capital = float(self.simulated_capital_pool)
        else:
            base_capital = float(self.real_balance)

        return round(base_capital - allocated, 4)
'''

new = '''        if self.paper_mode:
            try:
                base_capital = float(pnl_observer.equity())
            except Exception:
                try:
                    base_capital = float(pnl_observer.current_balance)
                except Exception:
                    base_capital = float(self.simulated_capital_pool)
        else:
            base_capital = float(self.real_balance)

        return round(base_capital - allocated, 4)
'''

if old not in text:
    raise RuntimeError("available_capital block not found. No file modified.")

text = text.replace(old, new, 1)

TARGET.write_text(text, encoding="utf-8")

print("[PCNRASS R4 BUILDER COMPLETE]")
print(f"Backup created: {backup}")
print("Next: python -m py_compile scripts\\css_live_dashboard.py")
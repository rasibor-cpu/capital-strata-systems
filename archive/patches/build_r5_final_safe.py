from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent
TARGET = ROOT / "scripts" / "css_live_dashboard.py"

text = TARGET.read_text(encoding="utf-8")

backup = TARGET.with_name(
    f"css_live_dashboard_PRE_R5_FINAL_{datetime.now().strftime('%Y%m%d_%H%M%S')}.py"
)
backup.write_text(text, encoding="utf-8")

# --- TARGET: available_capital METHOD ONLY ---

old_block = '''    def available_capital(self) -> float:
        allocated = sum(self.active_test_allocations.values())

        if self.paper_mode:
            base_capital = float(self.simulated_capital_pool)
        else:
            base_capital = float(self.real_balance)

        return round(base_capital - allocated, 4)
'''

new_block = '''    def available_capital(self) -> float:
        allocated = sum(self.active_test_allocations.values())

        if self.paper_mode:
            try:
                # Use observer equity as real-time source
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

if old_block not in text:
    raise RuntimeError("available_capital block not found EXACT match. No change applied.")

text = text.replace(old_block, new_block, 1)

TARGET.write_text(text, encoding="utf-8")

print("[PCNRASS R5 FINAL BUILDER COMPLETE]")
print(f"Backup created: {backup}")
print("Next: python -m py_compile scripts\\css_live_dashboard.py")
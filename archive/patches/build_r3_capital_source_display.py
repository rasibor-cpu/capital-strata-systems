from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent
TARGET = ROOT / "scripts" / "css_live_dashboard.py"

if not TARGET.exists():
    raise FileNotFoundError(f"Dashboard file not found: {TARGET}")

text = TARGET.read_text(encoding="utf-8")

backup = TARGET.with_name(
    f"css_live_dashboard_PRE_R3_CAPITAL_SOURCE_{datetime.now().strftime('%Y%m%d_%H%M%S')}.py"
)
backup.write_text(text, encoding="utf-8")

# Remove early activation if inserted before broker adapters are ready.
early_activation = '''
# PCNRASS R1: activate correct capital source after broker/mode selection.
if str(SELECTED_BROKER_MODE).lower() == "live":
    capital_governor.set_live_mode()
else:
    capital_governor.set_paper_mode()

'''
text = text.replace(early_activation, "")

# Insert activation AFTER broker adapters are initialized.
anchor = "initialize_selected_coinbase()\n"
activation = '''
# PCNRASS R3: activate correct capital source after broker adapters are initialized.
def pcnrass_activate_capital_source() -> None:
    if str(SELECTED_BROKER_MODE).lower() == "live":
        capital_governor.set_live_mode()
    else:
        capital_governor.set_paper_mode()

    base_capital = capital_governor.available_capital() + capital_governor.funded_amount()

    try:
        pnl_observer.starting_balance = float(base_capital)
        pnl_observer.current_balance = float(base_capital)
    except Exception as e:
        print(f"[CAPITAL SYNC WARN] pnl_observer sync failed: {str(e)[:60]}")

    print(
        f"[CAPITAL SOURCE ACTIVE] source={capital_governor.capital_source_label()} "
        f"mode={SELECTED_BROKER_MODE} available=${capital_governor.available_capital():,.2f}"
    )


pcnrass_activate_capital_source()
'''

if activation.strip() not in text:
    if anchor not in text:
        raise RuntimeError("Could not find initialize_selected_coinbase() anchor.")
    text = text.replace(anchor, anchor + activation + "\n", 1)

old_print = '''        print(
            f"SIMULATED CAPITAL DEPLOYED: "
            f"${capital_governor.funded_amount():.2f}"
        )
        print(
            f"SIMULATED CAPITAL AVAILABLE: "
            f"${capital_governor.available_capital():.2f}"
        )
'''

new_print = '''        capital_source = capital_governor.capital_source_label()
        print(
            f"{capital_source} CAPITAL DEPLOYED: "
            f"${capital_governor.funded_amount():.2f}"
        )
        print(
            f"{capital_source} CAPITAL AVAILABLE: "
            f"${capital_governor.available_capital():.2f}"
        )
'''

if old_print not in text:
    raise RuntimeError("Capital print block not found. No file modified.")

text = text.replace(old_print, new_print, 1)

TARGET.write_text(text, encoding="utf-8")

print("[PCNRASS R3 BUILDER COMPLETE]")
print(f"Target updated: {TARGET}")
print(f"Backup created: {backup}")
print("Next: python -m py_compile scripts\\css_live_dashboard.py")
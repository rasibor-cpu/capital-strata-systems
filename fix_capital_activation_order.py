from pathlib import Path

p = Path("scripts/css_live_dashboard.py")
text = p.read_text(encoding="utf-8")

old = '''print(
    f"[CAPITAL SOURCE ACTIVE] source={capital_governor.capital_source_label()} "
    f"mode={SELECTED_BROKER_MODE} available=${capital_governor.available_capital():,.2f}"
)


enforce_mode_dominance()
pcnrass_activate_capital_source()
enforce_execution_boundary()
'''

new = '''print(
    f"[CAPITAL SOURCE ACTIVE] source={capital_governor.capital_source_label()} "
    f"mode={SELECTED_BROKER_MODE} available=${capital_governor.available_capital():,.2f}"
)


enforce_mode_dominance()
enforce_execution_boundary()
'''

if old not in text:
    raise SystemExit("Target bottom activation block not found")

text = text.replace(old, new)

anchor = '''    # === R11 CAPITAL HARD LOCK ===
if str(SELECTED_BROKER_MODE).lower() == "live":
'''

replacement = '''    # === R11 CAPITAL HARD LOCK ===
pcnrass_activate_capital_source()

if str(SELECTED_BROKER_MODE).lower() == "live":
'''

if anchor not in text:
    raise SystemExit("R11 hard lock anchor not found")

text = text.replace(anchor, replacement, 1)

p.write_text(text, encoding="utf-8")
print("OK: moved capital activation before R11 live-capital hard lock")
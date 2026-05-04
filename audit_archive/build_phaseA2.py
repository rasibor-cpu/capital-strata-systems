from pathlib import Path

src = Path("scripts/css_live_dashboard_PHASEA1.py")
dst = Path("scripts/css_live_dashboard_PHASEA2.py")

code = src.read_text(encoding="utf-8")

# Insert probability gate AFTER decision scoring print
marker = "[DECISION]"

insert_block = """
    # ==============================
    # PHASE A2 — PROBABILITY FILTER
    # ==============================
    if prob < 0.65:
        print(f"[PHASE A2 FILTER] {symbol} blocked: prob={prob:.3f} < 0.65")
        continue
"""

# Inject after decision block
lines = code.splitlines()
new_lines = []

for i, line in enumerate(lines):
    new_lines.append(line)

    if marker in line:
        # insert after this line
        new_lines.append(insert_block)

code = "\n".join(new_lines)

dst.write_text(code, encoding="utf-8")

print("Created:", dst)
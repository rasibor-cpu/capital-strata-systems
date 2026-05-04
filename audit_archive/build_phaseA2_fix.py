from pathlib import Path

src = Path("scripts/css_live_dashboard_PHASEA1.py")
dst = Path("scripts/css_live_dashboard_PHASEA2B.py")

code = src.read_text(encoding="utf-8")

lines = code.splitlines()
new_lines = []

for i, line in enumerate(lines):
    new_lines.append(line)

    # detect decision line BEFORE execution happens
    if "[DECISION]" in line and "prob=" in line:
        indent = line[:len(line) - len(line.lstrip())]

        new_lines.append(f"{indent}# ==============================")
        new_lines.append(f"{indent}# PHASE A2B — PROBABILITY GATE")
        new_lines.append(f"{indent}# ==============================")
        new_lines.append(f"{indent}if prob < 0.65:")
        new_lines.append(f'{indent}    print(f"[PHASE A2 BLOCK] {{symbol}} prob={{prob:.3f}} below threshold")')
        new_lines.append(f"{indent}    continue")

code = "\n".join(new_lines)

dst.write_text(code, encoding="utf-8")

print("Created:", dst)

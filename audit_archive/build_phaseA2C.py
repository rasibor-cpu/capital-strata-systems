from pathlib import Path

src = Path("scripts/css_live_dashboard_PHASEA1.py")
dst = Path("scripts/css_live_dashboard_PHASEA2C.py")

code = src.read_text(encoding="utf-8")

lines = code.splitlines()
new_lines = []

injected = False

for line in lines:
    new_lines.append(line)

    # Insert AFTER __future__ import
    if not injected and "from __future__ import" in line:
        new_lines.append("")
        new_lines.append("# ============================================================")
        new_lines.append("# PHASE A2C — GLOBAL EXECUTION PROBABILITY GATE")
        new_lines.append("# ============================================================")
        new_lines.append("def phase_a2_allow_trade(prob):")
        new_lines.append("    if prob < 0.65:")
        new_lines.append('        print(f"[PHASE A2C BLOCK] prob={prob:.3f} below threshold")')
        new_lines.append("        return False")
        new_lines.append("    return True")
        new_lines.append("")
        injected = True

code = "\n".join(new_lines)

# Patch execution calls
code = code.replace(
    "attempt_coinbase_crypto_execution(",
    "attempt_coinbase_crypto_execution("  # leave intact for now
)

# Instead wrap BEFORE execution trigger (safer)
code = code.replace(
    "if decision:",
    "if decision and phase_a2_allow_trade(prob):"
)

dst.write_text(code, encoding="utf-8")

print("Created:", dst)
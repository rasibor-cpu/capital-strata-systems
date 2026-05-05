from pathlib import Path

SRC = Path("scripts/css_live_dashboard.py")
DST = Path("scripts/css_live_dashboard_R20_MTM_CAPITAL.py")

code = SRC.read_text(encoding="utf-8")

# === R20 MTM CAPITAL BLOCK ===
inject = """

# ===== R20 MTM CAPITAL ENGINE =====
try:
    open_positions = mtm_engine.count_open_positions()
except Exception:
    open_positions = 0

CAPITAL_PER_TRADE = 20.0
TOTAL_CAPITAL = 200.0

capital_deployed = open_positions * CAPITAL_PER_TRADE
capital_available = TOTAL_CAPITAL - capital_deployed

print(f"[R20 CAPITAL] Positions={open_positions} | Deployed=${capital_deployed:.2f} | Available=${capital_available:.2f}")
# =================================
"""

# Inject right before dashboard summary block
code = code.replace(
    'print(f"OPEN POSITIONS: {open_positions}',
    inject + '\nprint(f"OPEN POSITIONS: {open_positions}'
)

# Replace static capital display
code = code.replace(
    "SIMULATED CAPITAL DEPLOYED: $0.00",
    'SIMULATED CAPITAL DEPLOYED: ${:.2f}".format(capital_deployed)'
)

code = code.replace(
    "SIMULATED CAPITAL AVAILABLE: $200.00",
    'SIMULATED CAPITAL AVAILABLE: ${:.2f}".format(capital_available)'
)

DST.write_text(code, encoding="utf-8")

print("R20 BUILT:", DST)
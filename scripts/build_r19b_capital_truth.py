from pathlib import Path

SRC = Path("scripts/css_live_dashboard.py")
DST = Path("scripts/css_live_dashboard_R19B.py")

code = SRC.read_text(encoding="utf-8")

inject = """

# === R19B CAPITAL (TRUTH-BASED) ===
try:
    open_count = len(pnl_observer.positions)
except:
    open_count = 0

CAPITAL_PER_TRADE = 20.0

capital_deployed = open_count * CAPITAL_PER_TRADE
capital_available = 200.0 - capital_deployed

print(f"[CAPITAL] Positions={open_count} | Deployed=${capital_deployed:.2f} | Available=${capital_available:.2f}")
"""

# inject before dashboard summary
code = code.replace(
    "SIMULATED CAPITAL DEPLOYED:",
    inject + "\nSIMULATED CAPITAL DEPLOYED:"
)

# dynamic replacement
code = code.replace(
    "SIMULATED CAPITAL DEPLOYED: $0.00",
    "SIMULATED CAPITAL DEPLOYED: ${capital_deployed:.2f}"
)

code = code.replace(
    "SIMULATED CAPITAL AVAILABLE: $200.00",
    "SIMULATED CAPITAL AVAILABLE: ${capital_available:.2f}"
)

DST.write_text(code, encoding="utf-8")

print("R19B BUILT:", DST)
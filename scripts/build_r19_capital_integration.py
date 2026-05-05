from pathlib import Path

SRC = Path("scripts/css_live_dashboard.py")
DST = Path("scripts/css_live_dashboard_R19.py")

code = SRC.read_text(encoding="utf-8")

# === R19 CAPITAL HOOK INSERT ===
hook = """
# === R19 CAPITAL EXECUTION HOOK ===
if capital_governor.paper_mode:
    allocation = capital_governor.max_capital_per_trade
    available = capital_governor.available_capital()

    if available < allocation:
        print("[CAPITAL BLOCK] insufficient capital")
        continue

    position_id = f"{asset_class}_{symbol}_{int(time.time()*1000)}"
    capital_governor.active_test_allocations[position_id] = allocation

    print(
        f"[CAPITAL] Allocated ${allocation:.2f} | "
        f"Deployed=${capital_governor.funded_amount():.2f} | "
        f"Available=${capital_governor.available_capital():.2f}"
    )
"""

# inject before add_position
code = code.replace(
    "pnl_observer.add_position(position)",
    hook + "\n    pnl_observer.add_position(position)"
)

# fix dashboard display
code = code.replace(
    "SIMULATED CAPITAL DEPLOYED: $0.00",
    "SIMULATED CAPITAL DEPLOYED: ${capital_governor.funded_amount():.2f}"
)

code = code.replace(
    "SIMULATED CAPITAL AVAILABLE: $200.00",
    "SIMULATED CAPITAL AVAILABLE: ${capital_governor.available_capital():.2f}"
)

DST.write_text(code, encoding="utf-8")

print("R19 BUILT:", DST)
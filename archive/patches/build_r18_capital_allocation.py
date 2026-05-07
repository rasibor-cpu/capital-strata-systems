from pathlib import Path

SOURCE = Path(r"scripts/css_live_dashboard.py")
TARGET = Path(r"scripts/css_live_dashboard_R18_CAPITAL_ALLOC.py")

code = SOURCE.read_text()

# --------------------------------------------------
# 1. Inject Capital Engine (only if not already present)
# --------------------------------------------------
if "CAPITAL ALLOCATION ENGINE (R18)" not in code:

    capital_block = """

# ==================================================
# --- CAPITAL ALLOCATION ENGINE (R18) ---
# ==================================================

TOTAL_CAPITAL = 200.0
MAX_POSITIONS = 10
ALLOCATION_PER_TRADE = TOTAL_CAPITAL / MAX_POSITIONS

capital_state = {
    "total": TOTAL_CAPITAL,
    "allocated": 0.0,
    "available": TOTAL_CAPITAL
}

def allocate_capital():
    if capital_state["available"] >= ALLOCATION_PER_TRADE:
        capital_state["allocated"] += ALLOCATION_PER_TRADE
        capital_state["available"] -= ALLOCATION_PER_TRADE
        return ALLOCATION_PER_TRADE
    return 0.0

def release_capital():
    capital_state["allocated"] -= ALLOCATION_PER_TRADE
    capital_state["available"] += ALLOCATION_PER_TRADE

# ==================================================
"""

    # Insert near top after imports
    insert_point = code.find("\n", code.find("import"))
    code = code[:insert_point] + capital_block + code[insert_point:]


# --------------------------------------------------
# 2. Inject allocation into trade open logic
# --------------------------------------------------
if "[CAPITAL] Allocated" not in code:

    code = code.replace(
        "[OPTIONS PAPER OPENED]",
        """allocation = allocate_capital()
if allocation > 0:
    print(f"[CAPITAL] Allocated: ${allocation:.2f}")
    print("[OPTIONS PAPER OPENED]")
else:
    print("[CAPITAL BLOCK] No capital available")
"""
    )

    code = code.replace(
        "[FUTURES PAPER OPENED]",
        """allocation = allocate_capital()
if allocation > 0:
    print(f"[CAPITAL] Allocated: ${allocation:.2f}")
    print("[FUTURES PAPER OPENED]")
else:
    print("[CAPITAL BLOCK] No capital available")
"""
    )


# --------------------------------------------------
# 3. Fix Dashboard Capital Display
# --------------------------------------------------
code = code.replace(
    "SIMULATED CAPITAL DEPLOYED: $0.00",
    "SIMULATED CAPITAL DEPLOYED: ${:.2f}".format(0.0)
)

# Inject dynamic display if print block exists
if "SIMULATED CAPITAL AVAILABLE" in code:
    code = code.replace(
        "SIMULATED CAPITAL AVAILABLE:",
        "SIMULATED CAPITAL AVAILABLE:"
    )

# Add runtime print override (safe append)
if "[CAPITAL DASHBOARD]" not in code:
    dashboard_block = """

print(f"[CAPITAL DASHBOARD] DEPLOYED: ${capital_state['allocated']:.2f} | AVAILABLE: ${capital_state['available']:.2f}")

"""
    code += dashboard_block


# --------------------------------------------------
# WRITE FILE
# --------------------------------------------------
TARGET.write_text(code)

print("[SUCCESS] R18 Capital Allocation File Created:", TARGET)
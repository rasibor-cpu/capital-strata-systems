from pathlib import Path

SOURCE = Path(r"scripts/css_live_dashboard_R18_CAPITAL_ALLOC.py")
TARGET = Path(r"scripts/css_live_dashboard_R18B_CAPITAL_HOOK.py")

code = SOURCE.read_text()


# ==================================================
# 1. Ensure Capital Engine Exists (safe check)
# ==================================================
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

    insert_point = code.find("\n", code.find("import"))
    code = code[:insert_point] + capital_block + code[insert_point:]


# ==================================================
# 2. Hook into REAL POSITION CREATION
# ==================================================

# We look for position manager add/open calls
# This is the REAL execution point

patterns = [
    "position_manager.open_position(",
    "pm.open_position(",
    "options_position_manager.open_position(",
    "futures_position_manager.open_position("
]

hook_inserted = False

for pattern in patterns:
    if pattern in code:
        code = code.replace(
            pattern,
            f"""
allocation = allocate_capital()
if allocation <= 0:
    print("[CAPITAL BLOCK] No capital available - trade skipped")
else:
    print(f"[CAPITAL] Allocated: ${{allocation:.2f}}")

{pattern}
"""
        )
        hook_inserted = True


# ==================================================
# 3. Improve Dashboard Display (force dynamic)
# ==================================================

if "SIMULATED CAPITAL DEPLOYED" in code:

    code = code.replace(
        "SIMULATED CAPITAL DEPLOYED:",
        'SIMULATED CAPITAL DEPLOYED: ${:.2f}".format(capital_state["allocated"])  #'
    )

if "SIMULATED CAPITAL AVAILABLE" in code:

    code = code.replace(
        "SIMULATED CAPITAL AVAILABLE:",
        'SIMULATED CAPITAL AVAILABLE: ${:.2f}".format(capital_state["available"])  #'
    )


# ==================================================
# 4. Add Explicit Runtime Print (guaranteed visibility)
# ==================================================

if "[CAPITAL STATE]" not in code:

    code += """

print("\\n[CAPITAL STATE]")
print(f"DEPLOYED: ${capital_state['allocated']:.2f}")
print(f"AVAILABLE: ${capital_state['available']:.2f}")
print("-" * 40)

"""


# ==================================================
# WRITE FILE
# ==================================================

TARGET.write_text(code)

if hook_inserted:
    print("[SUCCESS] R18B Capital Hook Applied:", TARGET)
else:
    print("[WARNING] No position hook found — manual inspection needed:", TARGET)
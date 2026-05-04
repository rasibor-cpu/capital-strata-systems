import shutil

src = r"scripts\css_live_dashboard.py"
dst = r"scripts\css_live_dashboard_PACK3B.py"

with open(src, "r", encoding="utf-8") as f:
    code = f.read()

# --- APPLY TRUE PNL ENGINE FIX ---

# Replace MTM realized PnL calculation block
code = code.replace(
    "mtm_realized = 0.0",
    "mtm_realized = observer_realized  # PACK3B: align MTM with cost-adjusted observer"
)

# Ensure observer realized already has cost (already working in your system)
# Now MTM becomes authoritative with same value

with open(dst, "w", encoding="utf-8") as f:
    f.write(code)

print("PACK 3B file created:", dst)
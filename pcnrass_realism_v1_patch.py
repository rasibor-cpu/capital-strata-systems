from pathlib import Path

p = Path("scripts/css_live_dashboard.py")
s = p.read_text()

# --- REALISM CONFIG ---
REALISM_BLOCK = '''
# ===== PCNRASS REALISM LAYER v1 =====
import random

def apply_realism_adjustment(pnl, asset_class, signal_score):
    # Base spread/slippage per asset class
    spread_map = {
        "FX": 0.0003,
        "CRYPTO": 0.0008,
        "FUTURES": 0.0005,
        "OPTIONS": 0.0012,
    }

    base_cost = spread_map.get(asset_class, 0.0005)

    # Volatility scaling (simulated)
    volatility_factor = random.uniform(0.8, 1.5)

    # Signal quality dampener
    if signal_score < 12:
        quality_factor = 1.15  # worse fills
    elif signal_score > 15:
        quality_factor = 0.85  # better fills
    else:
        quality_factor = 1.0

    # Combined cost impact
    cost = base_cost * volatility_factor * quality_factor

    # Apply cost (reduce pnl)
    adjusted_pnl = pnl - abs(pnl) * cost

    return round(adjusted_pnl, 4)
'''

if "PCNRASS REALISM LAYER v1" not in s:
    s = REALISM_BLOCK + "\n" + s

# --- INTEGRATE INTO EXECUTION ---
s = s.replace(
    "pnl = round(random.uniform",
    "pnl = round(random.uniform"
)

s = s.replace(
    "last_trade = f\"{symbol} {pnl:+.4f}\"",
    '''
pnl = apply_realism_adjustment(pnl, asset_class, signal_score)
last_trade = f"{symbol} {pnl:+.4f}"
'''
)

p.write_text(s)
print("REALISM LAYER v1 APPLIED")
from pathlib import Path

p = Path("scripts/css_live_dashboard.py")
s = p.read_text()

OLD = "pnl = round(random.uniform"

NEW = '''
# ===== PCNRASS REALISM v2 =====
def generate_realistic_pnl(signal_score, asset_class):
    import random

    # Base edge
    if signal_score > 15:
        base = random.uniform(1.5, 4.0)
    elif signal_score > 12:
        base = random.uniform(0.5, 2.5)
    else:
        base = random.uniform(-2.5, 1.0)

    # Loss bias (real markets lose often)
    if random.random() < 0.55:
        base *= -0.6

    # Asset scaling
    scale = {
        "FX": 1.0,
        "CRYPTO": 1.2,
        "FUTURES": 1.5,
        "OPTIONS": 1.8
    }.get(asset_class, 1.0)

    pnl = base * scale

    # Friction
    pnl -= abs(pnl) * random.uniform(0.05, 0.15)

    return round(pnl, 4)

pnl = generate_realistic_pnl(signal_score, asset_class)
'''

s = s.replace(OLD, NEW)

p.write_text(s)
print("REALISM v2 APPLIED")
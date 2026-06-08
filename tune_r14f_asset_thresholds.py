from pathlib import Path

p = Path("scripts/css_live_dashboard.py")
text = p.read_text(encoding="utf-8")

old = '''    threshold = css_profitability_threshold(ENGINE_MODE)

    composite = signal_score + (probability * 5.0)
'''

new = '''    threshold = css_profitability_threshold(ENGINE_MODE)

    # R14F asset-aware tuning:
    # Preserve the base mode threshold for FUTURES/OPTIONS.
    # Slightly relax FX/CRYPTO so near-miss opportunities can enter controlled testing.
    asset_key = str(asset_class or "").upper()
    if asset_key == "CRYPTO":
        threshold -= 0.30
    elif asset_key == "FX":
        threshold -= 0.90

    composite = signal_score + (probability * 5.0)
'''

if old not in text:
    raise SystemExit("Target R14F threshold block not found")

text = text.replace(old, new, 1)
p.write_text(text, encoding="utf-8")
print("OK: applied asset-aware R14F threshold tuning")
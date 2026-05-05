from pathlib import Path

SRC = Path("scripts/css_live_dashboard.py")
DST = Path("scripts/css_live_dashboard_R20B_MTM_CAPITAL_SAFE.py")

code = SRC.read_text(encoding="utf-8")

old = 'print(f"OPEN POSITIONS: {open_positions} / {hard_position_limit()}")'

new = '''print(f"OPEN POSITIONS: {open_positions} / {hard_position_limit()}")
        r20_capital_deployed = float(open_positions) * 20.0
        r20_capital_available = 200.0 - r20_capital_deployed
        print(f"[R20 CAPITAL] Positions={open_positions} | Deployed=${r20_capital_deployed:.2f} | Available=${r20_capital_available:.2f}")'''

if old not in code:
    raise SystemExit("[FAILED] OPEN POSITIONS print anchor not found")

code = code.replace(old, new, 1)

DST.write_text(code, encoding="utf-8")
print("R20B BUILT:", DST)
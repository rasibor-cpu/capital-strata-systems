from pathlib import Path

SRC = Path("scripts/css_live_dashboard_R20B_MTM_CAPITAL_SAFE.py")
DST = Path("scripts/css_live_dashboard_R21C_EXIT_AFTER_R20.py")

code = SRC.read_text(encoding="utf-8")

old = '        print(f"[R20 CAPITAL] Positions={open_positions} | Deployed=${r20_capital_deployed:.2f} | Available=${r20_capital_available:.2f}")'

new = old + '''
        # ===== R21C EXIT ENGINE =====
        remaining_positions = []
        closed = 0

        for p in mtm_engine.positions:
            try:
                p["age"] = int(p.get("age", 0)) + 1
                pnl = float(p.get("floating_pnl", 0.0) or 0.0)

                if p["age"] >= 3:
                    print(f"[R21C EXIT] {p.get('symbol','?')} | TIME_EXIT | pnl={pnl:+.4f}")
                    closed += 1
                else:
                    remaining_positions.append(p)
            except Exception:
                remaining_positions.append(p)

        mtm_engine.positions = remaining_positions

        if closed:
            print(f"[R21C] Closed {closed} position(s)")
        # ============================'''

if old not in code:
    raise SystemExit("[FAILED] Exact R20 capital print line not found")

code = code.replace(old, new, 1)

DST.write_text(code, encoding="utf-8")
print("R21C BUILT:", DST)
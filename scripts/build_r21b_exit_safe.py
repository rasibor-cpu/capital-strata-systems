from pathlib import Path

SRC = Path("scripts/css_live_dashboard_R20B_MTM_CAPITAL_SAFE.py")
DST = Path("scripts/css_live_dashboard_R21B_EXIT_SAFE.py")

code = SRC.read_text(encoding="utf-8")

anchor = 'print(f"[R20 CAPITAL] Positions={open_positions}'

if anchor not in code:
    raise SystemExit("Anchor not found — R20 capital line missing")

inject = """
        # ===== R21 EXIT ENGINE (SAFE) =====
        remaining_positions = []
        closed = 0

        for p in mtm_engine.positions:
            try:
                age = p.get("age", 0)
                pnl = p.get("floating_pnl", 0.0)

                p["age"] = age + 1

                if p["age"] >= 3:
                    print(f"[R21 EXIT] {p.get('symbol','?')} | TIME_EXIT | pnl={pnl:+.4f}")
                    closed += 1
                else:
                    remaining_positions.append(p)

            except Exception:
                remaining_positions.append(p)

        mtm_engine.positions = remaining_positions

        if closed:
            print(f"[R21] Closed {closed} position(s)")
        # ==================================
"""

code = code.replace(anchor, anchor + inject, 1)

DST.write_text(code, encoding="utf-8")

print("R21B BUILT:", DST)
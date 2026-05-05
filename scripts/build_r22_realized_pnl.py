from pathlib import Path

SRC = Path("scripts/css_live_dashboard_R21C_EXIT_AFTER_R20.py")
DST = Path("scripts/css_live_dashboard_R22_REALIZED_PNL.py")

code = SRC.read_text(encoding="utf-8")

anchor = '[R21C EXIT]'

if anchor not in code:
    raise SystemExit("R21C EXIT anchor not found")

inject = """
                # ===== R22 REALIZED PnL =====
                try:
                    entry = float(p.get("entry_price", p.get("entry", 0.0)) or 0.0)
                    current = float(p.get("current_price", p.get("price", entry)) or entry)
                    qty = float(p.get("quantity", 1.0) or 1.0)
                    side = p.get("side", "BUY")

                    if side == "BUY":
                        realized_pnl = (current - entry) * qty
                    else:
                        realized_pnl = (entry - current) * qty

                except Exception:
                    realized_pnl = 0.0

                print(f"[R22 REALIZED] pnl={realized_pnl:+.4f}")

                try:
                    pnl_engine.record_trade(
                        symbol=p.get("symbol","?"),
                        side=side,
                        entry=entry,
                        exit=current,
                        qty=qty,
                        fees=0.0
                    )
                except Exception as e:
                    print(f"[R22 WARN] pnl_engine failed: {e}")
                # ============================
"""

# inject AFTER R21 EXIT print
code = code.replace(
    'print(f"[R21C EXIT]',
    'print(f"[R21C EXIT]' + inject,
    1
)

DST.write_text(code, encoding="utf-8")

print("R22 BUILT:", DST)
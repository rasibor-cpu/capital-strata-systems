from pathlib import Path

SRC = Path("scripts/css_live_dashboard_R21C_EXIT_AFTER_R20.py")
DST = Path("scripts/css_live_dashboard_R22B_REALIZED_PNL_SAFE.py")

code = SRC.read_text(encoding="utf-8")

old = '                    print(f"[R21C EXIT] {p.get(\'symbol\',\'?\')} | TIME_EXIT | pnl={pnl:+.4f}")'

new = '''                    try:
                        entry = float(p.get("entry_price", p.get("entry", 0.0)) or 0.0)
                        current = float(p.get("current_price", p.get("price", entry)) or entry)
                        qty = float(p.get("quantity", 1.0) or 1.0)
                        side = str(p.get("side", "BUY")).upper()

                        if side in {"BUY", "LONG"}:
                            realized_pnl = (current - entry) * qty
                        else:
                            realized_pnl = (entry - current) * qty
                    except Exception:
                        realized_pnl = float(pnl or 0.0)

                    print(f"[R21C EXIT] {p.get('symbol','?')} | TIME_EXIT | pnl={pnl:+.4f}")
                    print(f"[R22 REALIZED] {p.get('symbol','?')} | realized_pnl={realized_pnl:+.4f}")'''

if old not in code:
    raise SystemExit("[FAILED] Exact R21C exit print line not found")

code = code.replace(old, new, 1)

DST.write_text(code, encoding="utf-8")
print("R22B BUILT:", DST)
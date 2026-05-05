from pathlib import Path

INPUT = Path("scripts/css_live_dashboard.py")
OUTPUT = Path("scripts/css_live_dashboard_R17_EXIT_EXECUTION.py")

text = INPUT.read_text(encoding="utf-8")

# ============================================================
# R17 EXIT EXECUTION WRAPPER
# ============================================================

injection = '''
# =========================
# R17 EXIT EXECUTION LAYER
# =========================
def r17_execute_exit(pos, observer_symbol, observer_price, reason):
    """
    Institutional exit execution pipeline:
    - Ensures capital, PnL, and lifecycle stay in sync
    """
    try:
        if pos.get("forced_exit"):
            return

        # 1. Book exit (authoritative)
        book_position_exit(pos, reason)

        # 2. Close observer position (PnL)
        try:
            pnl_observer.close_position(observer_symbol, observer_price)
        except Exception as e:
            print(f"[R17 WARN] Observer close failed: {str(e)[:60]}")

        # 3. Ensure capital release safety (idempotent)
        try:
            if pos.get("broker_tested", False):
                capital_governor.release_trade(pos["position_id"])
        except Exception as e:
            print(f"[R17 WARN] Capital release failed: {str(e)[:60]}")

    except Exception as e:
        print(f"[R17 ERROR] Exit execution failure: {str(e)[:80]}")
'''

# Insert after book_position_exit definition
anchor = "def book_position_exit(pos: dict, reason: str) -> None:"
idx = text.find(anchor)

if idx == -1:
    raise RuntimeError("book_position_exit anchor not found")

# Insert after function block (safe: append near usage instead)
text = text.replace(anchor, injection + "\n" + anchor, 1)

# ============================================================
# REPLACE EXIT CALLS
# ============================================================

replacements = [
    ("book_position_exit(pos, \"FAST_STOP\")\n                pnl_observer.close_position(observer_symbol, observer_price)",
     "r17_execute_exit(pos, observer_symbol, observer_price, \"FAST_STOP\")"),

    ("book_position_exit(pos, \"STOP\")\n                pnl_observer.close_position(observer_symbol, observer_price)",
     "r17_execute_exit(pos, observer_symbol, observer_price, \"STOP\")"),

    ("book_position_exit(pos, \"TAKE_PROFIT\")\n                    pnl_observer.close_position(observer_symbol, observer_price)",
     "r17_execute_exit(pos, observer_symbol, observer_price, \"TAKE_PROFIT\")"),

    ("book_position_exit(pos, \"TIME_EXIT\")\n                    pnl_observer.close_position(observer_symbol, observer_price)",
     "r17_execute_exit(pos, observer_symbol, observer_price, \"TIME_EXIT\")"),
]

for old, new in replacements:
    text = text.replace(old, new)

OUTPUT.write_text(text, encoding="utf-8")

print("[SUCCESS] R17 EXIT EXECUTION FILE CREATED")
print(f"Output: {OUTPUT}")
from pathlib import Path

SRC = Path("scripts/css_live_dashboard_R20B_MTM_CAPITAL_SAFE.py")
DST = Path("scripts/css_live_dashboard_R21_EXIT_ENGINE.py")

code = SRC.read_text(encoding="utf-8")

# ---- 1) Add cycle counter (once) ----
cycle_block = """
# ===== R21 CYCLE TRACKER =====
try:
    R21_CYCLE
except NameError:
    R21_CYCLE = 0

R21_CYCLE += 1
# =============================
"""

if "R21 CYCLE TRACKER" not in code:
    # place near top after imports
    code = code.replace("from __future__ import annotations",
                        "from __future__ import annotations\n" + cycle_block, 1)

# ---- 2) Ensure each new position gets an 'opened_cycle' ----
# We hook right after PAPER OPENED print (safe anchor already in your file)
anchor_open = 'print(f"[{asset_class}] PAPER OPENED'
if anchor_open in code:
    code = code.replace(
        anchor_open,
        'print(f"[{asset_class}] PAPER OPENED'
        '\n            try:\n'
        '                position["opened_cycle"] = R21_CYCLE\n'
        '            except Exception:\n'
        '                pass',
        1
    )

# ---- 3) Insert exit engine AFTER MTM positions are available ----
# Safe anchor: where you iterate or have access to mtm_engine.positions
exit_block = """
# ===== R21 EXIT ENGINE =====
R21_MAX_HOLD_CYCLES = 3        # you can tune
R21_TAKE_PROFIT = 1.0          # currency units (paper)
R21_STOP_LOSS = -1.0           # currency units (paper)

closed = 0
remaining = []

for p in mtm_engine.positions:
    try:
        age = R21_CYCLE - p.get("opened_cycle", R21_CYCLE)
        pnl = p.get("floating_pnl", 0.0)

        exit_reason = None
        if age >= R21_MAX_HOLD_CYCLES:
            exit_reason = "TIME_EXIT"
        elif pnl >= R21_TAKE_PROFIT:
            exit_reason = "TAKE_PROFIT"
        elif pnl <= R21_STOP_LOSS:
            exit_reason = "STOP_LOSS"

        if exit_reason:
            closed += 1
            sym = p.get("symbol", "?")
            print(f"[R21 EXIT] {sym} | reason={exit_reason} | pnl={pnl:+.4f}")
        else:
            remaining.append(p)

    except Exception:
        remaining.append(p)

# Apply the close (authoritative for R20 capital since it uses mtm count)
mtm_engine.positions = remaining

if closed:
    print(f"[R21] Closed {closed} position(s) this cycle")
# ============================
"""

# Place exit block right after you compute open_positions (same anchor used earlier)
anchor_pos = 'open_positions = mtm_engine.count_open_positions()'
if anchor_pos in code and "R21 EXIT ENGINE" not in code:
    code = code.replace(anchor_pos, anchor_pos + "\n" + exit_block, 1)

# ---- 4) Keep your R20 capital display (already correct) ----

DST.write_text(code, encoding="utf-8")
print("R21 BUILT:", DST)